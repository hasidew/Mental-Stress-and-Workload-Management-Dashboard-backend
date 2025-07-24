from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from dependencies import get_current_user, require_role, get_db
from models import User, UserRole, StressScore, DailyWorkload, WorkAssignment
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

class DailyWorkloadRequest(BaseModel):
    description: str
    date: datetime

# Employee dashboard
@router.get("/employee")
def employee_dashboard(current_user: User = Depends(require_role(UserRole.employee)), db: Session = Depends(get_db)):
    stress_scores = db.query(StressScore).filter(StressScore.employee_id == current_user.id).all()
    workloads = db.query(DailyWorkload).filter(DailyWorkload.employee_id == current_user.id).all()
    assignments = db.query(WorkAssignment).filter(WorkAssignment.employee_id == current_user.id).all()
    return {
        "user": current_user.username,
        "stress_scores": [s.score for s in stress_scores],
        "workloads": [w.description for w in workloads],
        "assignments": [a.work_description for a in assignments]
    }

# Supervisor dashboard
@router.get("/supervisor")
def supervisor_dashboard(current_user: User = Depends(require_role(UserRole.supervisor)), db: Session = Depends(get_db)):
    # Get team members
    team_members = db.query(User).filter(
        User.team_id == current_user.team_id,
        User.role == UserRole.employee
    ).all()
    
    # Get team member IDs
    team_member_ids = [member.id for member in team_members]
    
    # Get tasks for team members
    from models import Task
    team_tasks = db.query(Task).filter(Task.employee_id.in_(team_member_ids)).all()
    
    # Get work assignments
    assignments = db.query(WorkAssignment).filter(WorkAssignment.supervisor_id == current_user.id).all()
    
    # Get stress scores for team members
    stress_scores = db.query(StressScore).filter(
        StressScore.employee_id.in_(team_member_ids),
        StressScore.share_with_supervisor == True
    ).all()
    
    return {
        "user": current_user.username,
        "team_members": len(team_members),
        "team_tasks": len(team_tasks),
        "active_workloads": len(assignments),
        "pending_reviews": len([t for t in team_tasks if t.status.value == 'pending']),
        "employees": [e.username for e in team_members],
        "assignments": [a.work_description for a in assignments],
        "stress_scores": [{"employee": s.employee_id, "score": s.score} for s in stress_scores]
    }

# Psychiatrist dashboard
@router.get("/psychiatrist")
def psychiatrist_dashboard(current_user: User = Depends(require_role(UserRole.psychiatrist)), db: Session = Depends(get_db)):
    employees = db.query(User).filter(User.role == UserRole.employee).all()
    stress = db.query(StressScore).all()
    return {
        "user": current_user.username,
        "patients": [e.username for e in employees],
        "stress_scores": [{"employee": s.employee_id, "score": s.score} for s in stress]
    }

# HR Manager dashboard
@router.get("/hr")
def hr_dashboard(current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    employees = db.query(User).filter(User.role == UserRole.employee).all()
    supervisors = db.query(User).filter(User.role == UserRole.supervisor).all()
    psychiatrists = db.query(User).filter(User.role == UserRole.psychiatrist).all()
    stress = db.query(StressScore).all()
    return {
        "user": current_user.username,
        "employees": [e.username for e in employees],
        "supervisors": [s.username for s in supervisors],
        "psychiatrists": [p.username for p in psychiatrists],
        "stress_scores": [{"employee": s.employee_id, "score": s.score} for s in stress]
    }

# Employee adds daily workload
@router.post("/employee/workload")
def add_daily_workload(request: DailyWorkloadRequest, current_user: User = Depends(require_role(UserRole.employee)), db: Session = Depends(get_db)):
    workload = DailyWorkload(
        description=request.description,
        date=request.date,
        employee_id=current_user.id
    )
    db.add(workload)
    db.commit()
    db.refresh(workload)
    return {"message": "Daily workload added", "id": workload.id}

# Employee views their daily workloads (detailed)
@router.get("/employee/workloads")
def get_my_workloads(current_user: User = Depends(require_role(UserRole.employee)), db: Session = Depends(get_db)):
    workloads = db.query(DailyWorkload).filter(DailyWorkload.employee_id == current_user.id).order_by(DailyWorkload.date.desc()).all()
    return [{"id": w.id, "description": w.description, "date": w.date} for w in workloads]

# Supervisor views all employees' workloads
@router.get("/supervisor/workloads")
def get_all_workloads(current_user: User = Depends(require_role(UserRole.supervisor)), db: Session = Depends(get_db)):
    workloads = db.query(DailyWorkload).all()
    return [
        {"id": w.id, "employee_id": w.employee_id, "description": w.description, "date": w.date}
        for w in workloads
    ] 