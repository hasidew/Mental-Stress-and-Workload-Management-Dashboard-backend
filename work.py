from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from dependencies import get_db, require_role
from models import User, UserRole, WorkAssignment
from pydantic import BaseModel

router = APIRouter(prefix="/work", tags=["work"])

# Supervisor assigns work to employee
class WorkAssignRequest(BaseModel):
    employee_id: int
    work_description: str

@router.post("/assign")
def assign_work(request: WorkAssignRequest, current_user: User = Depends(require_role(UserRole.supervisor)), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == request.employee_id, User.role == UserRole.employee).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    assignment = WorkAssignment(
        work_description=request.work_description,
        assigned_at=datetime.now(),
        employee_id=employee.id,
        supervisor_id=current_user.id
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return {"message": "Work assigned successfully", "assignment_id": assignment.id}

# Employee views their assigned work
@router.get("/my")
def my_work(current_user: User = Depends(require_role(UserRole.employee)), db: Session = Depends(get_db)):
    assignments = db.query(WorkAssignment).filter(WorkAssignment.employee_id == current_user.id).all()
    return [{"id": a.id, "description": a.work_description, "assigned_at": a.assigned_at} for a in assignments] 