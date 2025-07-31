from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
from dependencies import get_current_user, require_role, get_db
from models import User, UserRole, StressScore, DailyWorkload, WorkAssignment, Consultant, ConsultantBooking
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

# Simple HR dashboard test endpoint
@router.get("/hr/test")
def hr_dashboard_test(current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    """Simple test endpoint for HR dashboard"""
    try:
        return {
            "user": current_user.username,
            "role": current_user.role.value,
            "message": "HR dashboard test successful"
        }
    except Exception as e:
        print(f"Error in HR dashboard test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"HR dashboard test failed: {str(e)}")

# HR Manager dashboard
@router.get("/hr")
def hr_dashboard(current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    try:
        # Get all employees and supervisors
        employees = db.query(User).filter(User.role == UserRole.employee).all()
        supervisors = db.query(User).filter(User.role == UserRole.supervisor).all()
        psychiatrists = db.query(User).filter(User.role == UserRole.psychiatrist).all()
        
        # Get stress scores shared with HR
        stress_scores_shared_with_hr = db.query(StressScore).filter(
            StressScore.share_with_hr == True
        ).all()
        
        # Get HR's own workloads
        hr_workloads = db.query(DailyWorkload).filter(DailyWorkload.employee_id == current_user.id).all()
        
        # Get HR's own stress score
        hr_stress_score = db.query(StressScore).filter(StressScore.employee_id == current_user.id).first()
        
        # Get available consultants
        available_consultants = db.query(Consultant).all()
        
        # Get HR's own consultant bookings
        hr_bookings = db.query(ConsultantBooking).filter(ConsultantBooking.employee_id == current_user.id).all()
        
        return {
            "user": current_user.username,
            "employees": [e.username for e in employees],
            "supervisors": [s.username for s in supervisors],
            "psychiatrists": [p.username for p in psychiatrists],
            "stress_scores_shared_with_hr": [
                {
                    "employee_id": s.employee_id,
                    "employee_name": s.employee.name if s.employee else "Unknown",
                    "score": s.score,
                    "level": s.level,
                    "share_with_supervisor": s.share_with_supervisor,
                    "share_with_hr": s.share_with_hr,
                    "updated_at": s.updated_at
                } for s in stress_scores_shared_with_hr
            ],
            "hr_workloads": [
                {
                    "id": w.id,
                    "description": w.description,
                    "date": w.date
                } for w in hr_workloads
            ],
            "hr_stress_score": {
                "score": hr_stress_score.score if hr_stress_score else None,
                "level": hr_stress_score.level if hr_stress_score else None,
                "updated_at": hr_stress_score.updated_at if hr_stress_score else None
            },
            "available_psychiatrists": [
                {
                    "id": c.id,
                    "name": c.name,
                    "specialization": c.specialization,
                    "hospital": c.hospital
                } for c in available_consultants
            ],
            "hr_bookings": [
                {
                    "id": b.id,
                    "consultant_name": b.consultant.name if b.consultant else "Unknown",
                    "booking_date": b.booking_date,
                    "status": b.status.value,
                    "duration_minutes": b.duration_minutes
                } for b in hr_bookings
            ],
            "total_employees": len(employees),
            "total_supervisors": len(supervisors),
            "total_shared_stress_scores": len(stress_scores_shared_with_hr),
            "total_hr_workloads": len(hr_workloads),
            "total_hr_bookings": len(hr_bookings)
        }
    except Exception as e:
        print(f"Error in HR dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load HR dashboard data: {str(e)}")

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

# HR Manager views all employees' workloads
@router.get("/hr/workloads")
def get_hr_workloads(current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    workloads = db.query(DailyWorkload).all()
    return [
        {"id": w.id, "employee_id": w.employee_id, "description": w.description, "date": w.date}
        for w in workloads
    ]

# HR Manager adds their own daily workload
@router.post("/hr/workload")
def add_hr_workload(request: DailyWorkloadRequest, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    workload = DailyWorkload(
        description=request.description,
        date=request.date,
        employee_id=current_user.id
    )
    db.add(workload)
    db.commit()
    db.refresh(workload)
    return {"message": "Daily workload added", "id": workload.id}

# HR Manager views their own workloads
@router.get("/hr/my-workloads")
def get_hr_my_workloads(current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    workloads = db.query(DailyWorkload).filter(DailyWorkload.employee_id == current_user.id).order_by(DailyWorkload.date.desc()).all()
    return [{"id": w.id, "description": w.description, "date": w.date} for w in workloads]

# HR Manager books consultant for themselves
@router.post("/hr/book-consultant")
def hr_book_consultant(request: dict, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    from models import ConsultantBooking, BookingStatus
    from datetime import datetime
    
    # Parse booking date - frontend now sends local time directly
    booking_datetime = datetime.fromisoformat(request['booking_date'])
    
    booking = ConsultantBooking(
        consultant_id=request['consultant_id'],
        employee_id=current_user.id,
        booked_by_id=current_user.id,
        booking_date=booking_datetime,
        duration_minutes=request.get('duration_minutes', 30),
        status=BookingStatus.pending,
        notes=request.get('notes', '')
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"message": "Consultant booked successfully", "id": booking.id}

# HR Manager books psychiatrist for themselves
@router.post("/hr/book-psychiatrist")
def hr_book_psychiatrist(request: dict, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    from models import ConsultantBooking, BookingStatus
    from datetime import datetime
    
    # Parse booking date - frontend now sends local time directly
    booking_datetime = datetime.fromisoformat(request['booking_date'])
    
    # Check if booking is in the past
    current_datetime = datetime.now()
    if booking_datetime <= current_datetime:
        raise HTTPException(status_code=400, detail="Cannot book sessions in the past or current time")
    
    booking = ConsultantBooking(
        consultant_id=request['psychiatrist_id'],
        employee_id=current_user.id,
        booked_by_id=current_user.id,
        booking_date=booking_datetime,
        duration_minutes=request.get('duration_minutes', 30),
        status=BookingStatus.pending,
        notes=request.get('notes', '')
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"message": "Psychiatrist booked successfully", "id": booking.id}

# HR Manager views their consultant bookings
@router.get("/hr/my-bookings")
def get_hr_my_bookings(current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    from models import ConsultantBooking
    bookings = db.query(ConsultantBooking).filter(ConsultantBooking.employee_id == current_user.id).all()
    return [
        {
            "id": b.id,
            "consultant_name": b.consultant.name if b.consultant else "Unknown",
            "booking_date": b.booking_date,
            "status": b.status.value,
            "duration_minutes": b.duration_minutes,
            "notes": b.notes
        } for b in bookings
    ]

# HR Manager books consultant for an employee
@router.post("/hr/book-for-employee")
def hr_book_for_employee(request: dict, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    from models import ConsultantBooking, BookingStatus
    from datetime import datetime
    
    # Parse booking date - frontend now sends local time directly
    booking_datetime = datetime.fromisoformat(request['booking_date'])
    
    # Check if booking is in the past
    current_datetime = datetime.now()
    if booking_datetime <= current_datetime:
        raise HTTPException(status_code=400, detail="Cannot book sessions in the past or current time")
    
    booking = ConsultantBooking(
        consultant_id=request['consultant_id'],
        employee_id=request['employee_id'],
        booked_by_id=current_user.id,
        booking_date=booking_datetime,
        duration_minutes=request.get('duration_minutes', 30),
        status=BookingStatus.pending,
        notes=request.get('notes', '')
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"message": "Consultant booked for employee successfully", "id": booking.id}

# HR Manager books psychiatrist for an employee
@router.post("/hr/book-psychiatrist-for-employee")
def hr_book_psychiatrist_for_employee(request: dict, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    from models import ConsultantBooking, BookingStatus
    from datetime import datetime
    
    # Parse booking date - frontend now sends local time directly
    booking_datetime = datetime.fromisoformat(request['booking_date'])
    
    # Check if booking is in the past
    current_datetime = datetime.now()
    if booking_datetime <= current_datetime:
        raise HTTPException(status_code=400, detail="Cannot book sessions in the past or current time")
    
    booking = ConsultantBooking(
        consultant_id=request['psychiatrist_id'],
        employee_id=request['employee_id'],
        booked_by_id=current_user.id,
        booking_date=booking_datetime,
        duration_minutes=request.get('duration_minutes', 30),
        status=BookingStatus.pending,
        notes=request.get('notes', '')
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"message": "Psychiatrist booked for employee successfully", "id": booking.id}

# Database check endpoint
@router.get("/db-check")
def database_check(db: Session = Depends(get_db)):
    """Check if all required database tables exist"""
    try:
        # Check if tables exist by trying to query them
        user_count = db.query(User).count()
        consultant_count = db.query(Consultant).count()
        stress_count = db.query(StressScore).count()
        workload_count = db.query(DailyWorkload).count()
        booking_count = db.query(ConsultantBooking).count()
        
        return {
            "status": "success",
            "tables": {
                "users": user_count,
                "consultants": consultant_count,
                "stress_scores": stress_count,
                "daily_workloads": workload_count,
                "consultant_bookings": booking_count
            }
        }
    except Exception as e:
        print(f"Database check error: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        } 