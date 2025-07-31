from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import SessionLocal
from models import User, UserRole, Task, TaskStatus
from dependencies import get_current_user, require_role, require_roles, get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Pydantic models
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"  # low, medium, high
    due_date: Optional[datetime] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # pending, completed
    priority: Optional[str] = None  # low, medium, high
    due_date: Optional[datetime] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    employee_id: int
    employee_name: str
    assigned_by_id: Optional[int] = None
    assigned_by_name: Optional[str] = None

# Employee/Supervisor creates their own task
@router.post("/", response_model=TaskResponse)
def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    # Create task for the current user
    task = Task(
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        due_date=task_data.due_date,
        employee_id=current_user.id,
        assigned_by_id=current_user.id  # Self-assigned
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "priority": task.priority,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "employee_id": task.employee_id,
        "employee_name": current_user.name or current_user.username,
        "assigned_by_id": task.assigned_by_id,
        "assigned_by_name": current_user.name or current_user.username
    }

# Employee/Supervisor gets their own tasks
@router.get("/my", response_model=List[TaskResponse])
def get_my_tasks(
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    tasks = db.query(Task).filter(Task.employee_id == current_user.id).order_by(Task.created_at.desc()).all()
    
    return [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority,
            "due_date": task.due_date,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "employee_id": task.employee_id,
            "employee_name": current_user.name or current_user.username,
            "assigned_by_id": task.assigned_by_id,
            "assigned_by_name": task.assigned_by.name if task.assigned_by else None
        }
        for task in tasks
    ]

# Employee/Supervisor updates their own task
@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.employee_id == current_user.id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update fields if provided
    if task_data.title is not None:
        setattr(task, 'title', task_data.title)
    if task_data.description is not None:
        setattr(task, 'description', task_data.description)
    if task_data.status is not None:
        setattr(task, 'status', TaskStatus(task_data.status))
    if task_data.priority is not None:
        setattr(task, 'priority', task_data.priority)
    if task_data.due_date is not None:
        setattr(task, 'due_date', task_data.due_date)
    
    setattr(task, 'updated_at', datetime.now())
    db.commit()
    db.refresh(task)
    
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "priority": task.priority,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "employee_id": task.employee_id,
        "employee_name": current_user.name or current_user.username,
        "assigned_by_id": task.assigned_by_id,
        "assigned_by_name": task.assigned_by.name if task.assigned_by else None
    }

# Employee/Supervisor deletes their own task
@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.employee_id == current_user.id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    
    return {"message": "Task deleted successfully"}

# Employee/Supervisor marks task as completed/pending
@router.patch("/{task_id}/status")
def update_task_status(
    task_id: int,
    status: str,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.employee_id == current_user.id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if status not in ["pending", "completed"]:
        raise HTTPException(status_code=400, detail="Status must be 'pending' or 'completed'")
    
    setattr(task, 'status', TaskStatus(status))
    setattr(task, 'updated_at', datetime.now())
    db.commit()
    
    return {"message": f"Task status updated to {status}"}

# Get specific task
@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.employee_id == current_user.id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "priority": task.priority,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "employee_id": task.employee_id,
        "employee_name": current_user.name or current_user.username,
        "assigned_by_id": task.assigned_by_id,
        "assigned_by_name": task.assigned_by.name if task.assigned_by else None
    } 

# ===== SUPERVISOR ENDPOINTS =====

# Supervisor creates task for team member
@router.post("/supervisor/assign", response_model=TaskResponse)
def supervisor_create_task(
    task_data: TaskCreate,
    employee_id: int,
    current_user: User = Depends(require_role(UserRole.supervisor)),
    db: Session = Depends(get_db)
):
    # Check if employee exists and is in supervisor's team
    employee = db.query(User).filter(
        User.id == employee_id,
        User.role == UserRole.employee,
        User.team_id == current_user.team_id
    ).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found in your team")
    
    # Create task for the employee
    task = Task(
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        due_date=task_data.due_date,
        employee_id=employee_id,
        assigned_by_id=current_user.id  # Assigned by supervisor
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "priority": task.priority,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "employee_id": task.employee_id,
        "employee_name": employee.name or employee.username,
        "assigned_by_id": task.assigned_by_id,
        "assigned_by_name": current_user.name or current_user.username
    }

# Supervisor gets team members' tasks
@router.get("/supervisor/team", response_model=List[TaskResponse])
def supervisor_get_team_tasks(
    current_user: User = Depends(require_role(UserRole.supervisor)),
    db: Session = Depends(get_db)
):
    # Get all employees in supervisor's team
    team_members = db.query(User).filter(
        User.team_id == current_user.team_id,
        User.role == UserRole.employee
    ).all()
    
    team_member_ids = [member.id for member in team_members]
    
    # Get all tasks for team members
    tasks = db.query(Task).filter(Task.employee_id.in_(team_member_ids)).order_by(Task.created_at.desc()).all()
    
    result = []
    for task in tasks:
        employee = db.query(User).filter(User.id == task.employee_id).first()
        assigned_by = db.query(User).filter(User.id == task.assigned_by_id).first()
        
        result.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority,
            "due_date": task.due_date,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "employee_id": task.employee_id,
            "employee_name": employee.name or employee.username if employee else "Unknown",
            "assigned_by_id": task.assigned_by_id,
            "assigned_by_name": assigned_by.name or assigned_by.username if assigned_by else "Unknown"
        })
    
    return result

# Supervisor updates team member's task
@router.put("/supervisor/{task_id}", response_model=TaskResponse)
def supervisor_update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: User = Depends(require_role(UserRole.supervisor)),
    db: Session = Depends(get_db)
):
    # Get task and check if employee is in supervisor's team
    task = db.query(Task).join(User, Task.employee_id == User.id).filter(
        Task.id == task_id,
        User.team_id == current_user.team_id,
        User.role == UserRole.employee
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update fields if provided
    if task_data.title is not None:
        setattr(task, 'title', task_data.title)
    if task_data.description is not None:
        setattr(task, 'description', task_data.description)
    if task_data.status is not None:
        setattr(task, 'status', TaskStatus(task_data.status))
    if task_data.priority is not None:
        setattr(task, 'priority', task_data.priority)
    if task_data.due_date is not None:
        setattr(task, 'due_date', task_data.due_date)
    
    setattr(task, 'updated_at', datetime.now())
    db.commit()
    db.refresh(task)
    
    # Get employee and assigned_by info for response
    employee = db.query(User).filter(User.id == task.employee_id).first()
    assigned_by = db.query(User).filter(User.id == task.assigned_by_id).first()
    
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "priority": task.priority,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "employee_id": task.employee_id,
        "employee_name": employee.name or employee.username if employee else "Unknown",
        "assigned_by_id": task.assigned_by_id,
        "assigned_by_name": assigned_by.name or assigned_by.username if assigned_by else "Unknown"
    }

# Supervisor deletes team member's task
@router.delete("/supervisor/{task_id}")
def supervisor_delete_task(
    task_id: int,
    current_user: User = Depends(require_role(UserRole.supervisor)),
    db: Session = Depends(get_db)
):
    # Get task and check if employee is in supervisor's team
    task = db.query(Task).join(User, Task.employee_id == User.id).filter(
        Task.id == task_id,
        User.team_id == current_user.team_id,
        User.role == UserRole.employee
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    
    return {"message": "Task deleted successfully"}

# Supervisor gets team members list
@router.get("/supervisor/team-members")
def supervisor_get_team_members(
    current_user: User = Depends(require_role(UserRole.supervisor)),
    db: Session = Depends(get_db)
):
    team_members = db.query(User).filter(
        User.team_id == current_user.team_id,
        User.role == UserRole.employee
    ).all()
    
    return [
        {
            "id": member.id,
            "name": member.name or member.username,
            "username": member.username,
            "email": member.email
        }
        for member in team_members
    ] 