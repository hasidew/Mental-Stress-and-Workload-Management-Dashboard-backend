from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from dependencies import get_db, require_role, require_roles
from models import User, UserRole, StressScore
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/stress", tags=["stress"])

# Pydantic models
class StressAssessmentRequest(BaseModel):
    answers: List[int]  # List of answers (0-4 scale for each question)
    share_with_supervisor: bool = False
    share_with_hr: bool = False

class StressScoreResponse(BaseModel):
    id: int
    score: float
    level: str
    pss_score: float
    normalized_pss: float
    workload_stress_score: float
    total_hours_worked: float
    share_with_supervisor: bool
    share_with_hr: bool
    created_at: datetime
    updated_at: datetime
    employee_name: str

class UpdateSharingRequest(BaseModel):
    share_with_supervisor: Optional[bool] = None
    share_with_hr: Optional[bool] = None

# Stress assessment questions (PSS-10 - Perceived Stress Scale)
# Updated for 24-hour timeframe and 0-4 scale
STRESS_QUESTIONS = [
    "During the past 24 hours, how often did you feel like this? Something happened that surprised or upset you.",
    "During the past 24 hours, how often did you feel like this? You felt like you couldn't control important things in your life.",
    "During the past 24 hours, how often did you feel like this? You felt nervous or stressed.",
    "During the past 24 hours, how often did you feel like this? You felt sure you could solve your problems.",
    "During the past 24 hours, how often did you feel like this? Things were going well for you.",
    "During the past 24 hours, how often did you feel like this? You had too many things to do and felt you couldn't manage.",
    "During the past 24 hours, how often did you feel like this? You were able to stay calm when something annoyed you.",
    "During the past 24 hours, how often did you feel like this? You felt in control of your day.",
    "During the past 24 hours, how often did you feel like this? You got angry about things you couldn't control.",
    "During the past 24 hours, how often did you feel like this? You felt like problems were too much for you."
]

def calculate_pss_score(answers: List[int]) -> tuple[float, float]:
    """
    Calculate PSS score based on PSS-10 (Perceived Stress Scale)
    Reverse scoring for questions 4, 5, 7, 8 (positive questions)
    Scale: 0 = Never → 4 = Very Often
    """
    if len(answers) != 10:
        raise HTTPException(status_code=400, detail="Must provide exactly 10 answers")
    
    # Validate answers (0-4 scale)
    for answer in answers:
        if not (0 <= answer <= 4):
            raise HTTPException(status_code=400, detail="Answers must be between 0 and 4")
    
    # Reverse scoring for positive questions (4, 5, 7, 8) - 0-indexed
    positive_questions = [3, 4, 6, 7]  # Q4, Q5, Q7, Q8
    total_score = 0
    
    for i, answer in enumerate(answers):
        if i in positive_questions:
            # Reverse scoring: 0->4, 1->3, 2->2, 3->1, 4->0
            reversed_score = 4 - answer
            total_score += reversed_score
        else:
            total_score += answer
    
    # Normalize to 0-10 scale
    normalized_pss = (total_score / 40) * 10
    
    return total_score, normalized_pss

def calculate_workload_stress(db: Session, employee_id: int) -> tuple[float, float, dict]:
    """
    Calculate workload stress based on FTE method and task analysis
    Returns: (normalized_workload_stress, total_hours_worked, workload_details)
    """
    from datetime import datetime, timedelta
    from models import Task
    
    # Get tasks from the past 24 hours
    yesterday = datetime.now() - timedelta(days=1)
    
    # Get all tasks for the employee from the past 24 hours
    tasks = db.query(Task).filter(
        Task.employee_id == employee_id,
        Task.created_at >= yesterday
    ).all()
    
    total_hours_worked = 0.0
    high_priority_tasks = 0
    overdue_tasks = 0
    pending_tasks = 0
    total_tasks = len(tasks)
    
    for task in tasks:
        # Calculate hours worked from task duration
        if task.duration:
            # Convert minutes to hours
            total_hours_worked += task.duration / 60
        
        # Count high priority tasks
        if task.priority == "high":
            high_priority_tasks += 1
        
        # Count pending tasks
        if task.status.value == "pending":
            pending_tasks += 1
        
        # Check for overdue tasks (due_date < now and status is pending)
        if task.due_date and task.due_date < datetime.now() and task.status.value == "pending":
            overdue_tasks += 1
    
    # FTE standard is 7.22 hours
    fte_standard = 7.22
    
    # Base workload stress score based on hours worked
    if total_hours_worked < 7.22:
        raw_workload_score = 0.0
    elif total_hours_worked >= 7.23 and total_hours_worked <= 9.0:
        raw_workload_score = 0.5
    elif total_hours_worked >= 9.01 and total_hours_worked <= 11.99:
        raw_workload_score = 1.0
    else:  # >= 12.0
        raw_workload_score = 2.0
    
    # Additional stress factors
    priority_stress = min(high_priority_tasks * 0.1, 0.5)  # Max 0.5 for high priority tasks
    overdue_stress = min(overdue_tasks * 0.2, 0.5)  # Max 0.5 for overdue tasks
    pending_stress = min(pending_tasks * 0.05, 0.3)  # Max 0.3 for pending tasks
    
    # Calculate total workload stress (capped at 2.0)
    total_workload_stress = min(raw_workload_score + priority_stress + overdue_stress + pending_stress, 2.0)
    
    # Normalize workload stress to 0-10 scale
    normalized_workload_stress = (total_workload_stress / 2.0) * 10
    
    # Prepare workload details for display
    workload_details = {
        "total_tasks": total_tasks,
        "high_priority_tasks": high_priority_tasks,
        "overdue_tasks": overdue_tasks,
        "pending_tasks": pending_tasks,
        "completed_tasks": total_tasks - pending_tasks,
        "fte_standard": fte_standard,
        "raw_workload_score": raw_workload_score,
        "priority_stress": priority_stress,
        "overdue_stress": overdue_stress,
        "pending_stress": pending_stress,
        "total_workload_stress": total_workload_stress,
        "normalized_workload_stress": normalized_workload_stress
    }
    
    return normalized_workload_stress, total_hours_worked, workload_details

def calculate_final_stress_score(normalized_pss: float, normalized_workload: float) -> tuple[float, str]:
    """
    Calculate final work stress score using the updated formula:
    final_stress_score = (normalized_pss × 0.7) + (normalized_workload × 0.3)
    """
    final_stress_score = (normalized_pss * 0.7) + (normalized_workload * 0.3)
    
    # Determine stress level based on thresholds
    if final_stress_score <= 3.0:
        level = "low"
    elif final_stress_score <= 6.0:
        level = "moderate"
    elif final_stress_score <= 8.5:
        level = "high"
    else:
        level = "critical"
    
    return final_stress_score, level

@router.get("/questions")
def get_stress_questions():
    """Get stress assessment questions"""
    return {
        "questions": STRESS_QUESTIONS,
        "instructions": "Rate how often you have felt or thought a certain way during the past 24 hours: 0=Never, 1=Almost Never, 2=Sometimes, 3=Often, 4=Very Often"
    }

@router.post("/submit-assessment")
def submit_stress_assessment(
    request: StressAssessmentRequest,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Submit stress assessment and calculate score using new Work Stress Calculation method"""
    try:
        # Calculate PSS score
        pss_score, normalized_pss = calculate_pss_score(request.answers)
        
        # Calculate workload stress
        normalized_workload_stress, total_hours_worked, workload_details = calculate_workload_stress(db, current_user.id)
        
        # Calculate final stress score
        final_score, level = calculate_final_stress_score(normalized_pss, normalized_workload_stress)
        
        # For supervisors, force share_with_supervisor to False
        if current_user.role == UserRole.supervisor:
            request.share_with_supervisor = False
        
        # For HR managers, force both sharing options to False (no sharing for HR)
        if current_user.role == UserRole.hr_manager:
            request.share_with_supervisor = False
            request.share_with_hr = False
        
        # Check if user already has a stress score
        existing_score = db.query(StressScore).filter(StressScore.employee_id == current_user.id).first()
        
        if existing_score:
            # Update existing score
            setattr(existing_score, 'score', final_score)
            setattr(existing_score, 'level', level)
            setattr(existing_score, 'pss_score', pss_score)
            setattr(existing_score, 'normalized_pss', normalized_pss)
            setattr(existing_score, 'workload_stress_score', normalized_workload_stress)
            setattr(existing_score, 'total_hours_worked', total_hours_worked)
            setattr(existing_score, 'share_with_supervisor', request.share_with_supervisor)
            setattr(existing_score, 'share_with_hr', request.share_with_hr)
            setattr(existing_score, 'updated_at', datetime.now())
            db.commit()
            db.refresh(existing_score)
            
            return {
                "message": "Stress assessment updated successfully",
                "score": final_score,
                "level": level,
                "pss_score": pss_score,
                "normalized_pss": normalized_pss,
                "workload_stress_score": normalized_workload_stress,
                "total_hours_worked": total_hours_worked,
                "id": existing_score.id
            }
        else:
            # Create new stress score
            stress_score = StressScore(
                employee_id=current_user.id,
                score=final_score,
                level=level,
                pss_score=pss_score,
                normalized_pss=normalized_pss,
                workload_stress_score=normalized_workload_stress,
                total_hours_worked=total_hours_worked,
                share_with_supervisor=request.share_with_supervisor,
                share_with_hr=request.share_with_hr
            )
            db.add(stress_score)
            db.commit()
            db.refresh(stress_score)
            
            return {
                "message": "Stress assessment submitted successfully",
                "score": final_score,
                "level": level,
                "pss_score": pss_score,
                "normalized_pss": normalized_pss,
                "workload_stress_score": normalized_workload_stress,
                "total_hours_worked": total_hours_worked,
                "id": stress_score.id
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing assessment: {str(e)}")

@router.get("/my-score")
def get_my_stress_score(
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Get current user's stress score"""
    stress_score = db.query(StressScore).filter(StressScore.employee_id == current_user.id).first()
    
    if not stress_score:
        return {"message": "No stress assessment completed yet"}
    
    return {
        "id": stress_score.id,
        "score": stress_score.score,
        "level": stress_score.level,
        "pss_score": stress_score.pss_score,
        "normalized_pss": stress_score.normalized_pss,
        "workload_stress_score": stress_score.workload_stress_score,
        "total_hours_worked": stress_score.total_hours_worked,
        "share_with_supervisor": stress_score.share_with_supervisor,
        "share_with_hr": stress_score.share_with_hr,
        "created_at": stress_score.created_at,
        "updated_at": stress_score.updated_at
    }

@router.get("/workload-details")
def get_workload_details(
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Get detailed workload information for current user"""
    try:
        _, _, workload_details = calculate_workload_stress(db, current_user.id)
        return workload_details
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating workload: {str(e)}")

@router.put("/update-sharing")
def update_sharing_preferences(
    request: UpdateSharingRequest,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Update sharing preferences for stress score"""
    stress_score = db.query(StressScore).filter(StressScore.employee_id == current_user.id).first()
    
    if not stress_score:
        raise HTTPException(status_code=404, detail="No stress assessment found")
    
    # For supervisors, prevent sharing with supervisor
    if current_user.role == UserRole.supervisor:
        request.share_with_supervisor = False
    
    # For HR managers, prevent all sharing
    if current_user.role == UserRole.hr_manager:
        request.share_with_supervisor = False
        request.share_with_hr = False
    
    setattr(stress_score, 'share_with_supervisor', request.share_with_supervisor)
    setattr(stress_score, 'share_with_hr', request.share_with_hr)
    setattr(stress_score, 'updated_at', datetime.now())
    db.commit()
    db.refresh(stress_score)
    
    return {
        "message": "Sharing preferences updated successfully",
        "share_with_supervisor": stress_score.share_with_supervisor,
        "share_with_hr": stress_score.share_with_hr
    }

@router.get("/team-scores")
def get_team_stress_scores(
    current_user: User = Depends(require_roles([UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Get stress scores for team members (supervisor/HR only)"""
    if current_user.role == UserRole.supervisor:
        # Get employees supervised by current user
        team_members = db.query(User).filter(
            User.team_id == current_user.team_id,
            User.role == UserRole.employee
        ).all()
    else:  # HR manager
        # Get all employees
        team_members = db.query(User).filter(User.role == UserRole.employee).all()
    
    scores = []
    for member in team_members:
        stress_score = db.query(StressScore).filter(StressScore.employee_id == member.id).first()
        
        if stress_score is not None:
            # Check sharing permissions
            can_view = False
            if current_user.role == UserRole.supervisor:
                can_view = bool(getattr(stress_score, 'share_with_supervisor', False))
            elif current_user.role == UserRole.hr_manager:
                can_view = bool(getattr(stress_score, 'share_with_hr', False))
            
            if can_view:
                scores.append({
                    "employee_id": member.id,
                    "employee_name": member.name or member.username,
                    "score": stress_score.score,
                    "level": stress_score.level,
                    "updated_at": stress_score.updated_at
                })
    
    return {
        "team_scores": scores,
        "total_members": len(team_members),
        "shared_scores": len(scores)
    }

@router.get("/my-history")
def get_stress_history(
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Get stress score history for current user"""
    stress_score = db.query(StressScore).filter(StressScore.employee_id == current_user.id).first()
    
    if not stress_score:
        return {"message": "No stress assessment completed yet"}
    
    return {
        "current_score": {
            "score": stress_score.score,
            "level": stress_score.level,
            "share_with_supervisor": stress_score.share_with_supervisor,
            "share_with_hr": stress_score.share_with_hr,
            "created_at": stress_score.created_at,
            "updated_at": stress_score.updated_at
        },
        "assessment_count": 1  # Since we only keep the latest score
    } 