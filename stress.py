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
    answers: List[int]  # List of answers (1-5 scale for each question)
    share_with_supervisor: bool = False
    share_with_hr: bool = False

class StressScoreResponse(BaseModel):
    id: int
    score: int
    level: str
    share_with_supervisor: bool
    share_with_hr: bool
    created_at: datetime
    updated_at: datetime
    employee_name: str

class UpdateSharingRequest(BaseModel):
    share_with_supervisor: Optional[bool] = None
    share_with_hr: Optional[bool] = None

# Stress assessment questions (PSS - Perceived Stress Scale)
STRESS_QUESTIONS = [
    "In the last month, how often have you been upset because of something that happened unexpectedly?",
    "In the last month, how often have you felt that you were unable to control the important things in your life?",
    "In the last month, how often have you felt nervous and 'stressed'?",
    "In the last month, how often have you felt confident about your ability to handle your personal problems?",
    "In the last month, how often have you felt that things were going your way?",
    "In the last month, how often have you found that you could not cope with all the things that you had to do?",
    "In the last month, how often have you been able to control irritations in your life?",
    "In the last month, how often have you felt that you were on top of things?",
    "In the last month, how often have you been angered because of things that happened that were outside of your control?",
    "In the last month, how often have you felt difficulties were piling up so high that you could not overcome them?"
]

def calculate_stress_score(answers: List[int]) -> tuple[int, str]:
    """
    Calculate stress score based on PSS (Perceived Stress Scale)
    Reverse scoring for questions 4, 5, 7, 8 (positive questions)
    """
    if len(answers) != 10:
        raise HTTPException(status_code=400, detail="Must provide exactly 10 answers")
    
    # Validate answers (1-5 scale)
    for answer in answers:
        if not (1 <= answer <= 5):
            raise HTTPException(status_code=400, detail="Answers must be between 1 and 5")
    
    # Reverse scoring for positive questions (4, 5, 7, 8)
    positive_questions = [3, 4, 6, 7]  # 0-indexed
    total_score = 0
    
    for i, answer in enumerate(answers):
        if i in positive_questions:
            # Reverse scoring: 1->5, 2->4, 3->3, 4->2, 5->1
            total_score += (6 - answer)
        else:
            total_score += answer
    
    # Determine stress level
    if total_score <= 13:
        level = "low"
    elif total_score <= 26:
        level = "medium"
    else:
        level = "high"
    
    return total_score, level

@router.get("/questions")
def get_stress_questions():
    """Get stress assessment questions"""
    return {
        "questions": STRESS_QUESTIONS,
        "instructions": "Rate how often you have felt or thought a certain way in the last month: 1=Never, 2=Almost Never, 3=Sometimes, 4=Fairly Often, 5=Very Often"
    }

@router.post("/submit-assessment")
def submit_stress_assessment(
    request: StressAssessmentRequest,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Submit stress assessment and calculate score"""
    try:
        score, level = calculate_stress_score(request.answers)
        
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
            setattr(existing_score, 'score', score)
            setattr(existing_score, 'level', level)
            setattr(existing_score, 'share_with_supervisor', request.share_with_supervisor)
            setattr(existing_score, 'share_with_hr', request.share_with_hr)
            setattr(existing_score, 'updated_at', datetime.now())
            db.commit()
            db.refresh(existing_score)
            
            return {
                "message": "Stress assessment updated successfully",
                "score": score,
                "level": level,
                "id": existing_score.id
            }
        else:
            # Create new stress score
            stress_score = StressScore(
                employee_id=current_user.id,
                score=score,
                level=level,
                share_with_supervisor=request.share_with_supervisor,
                share_with_hr=request.share_with_hr
            )
            db.add(stress_score)
            db.commit()
            db.refresh(stress_score)
            
            return {
                "message": "Stress assessment submitted successfully",
                "score": score,
                "level": level,
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
        "share_with_supervisor": stress_score.share_with_supervisor,
        "share_with_hr": stress_score.share_with_hr,
        "created_at": stress_score.created_at,
        "updated_at": stress_score.updated_at
    }

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