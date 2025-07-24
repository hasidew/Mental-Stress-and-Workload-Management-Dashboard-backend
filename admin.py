from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, time
from dependencies import get_db, require_role, get_current_user
from models import User, UserRole, Department, Team, Consultant, ConsultantAvailability, UserRegistrationRequest, RequestStatus
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from fastapi import Path

router = APIRouter(prefix="/admin", tags=["admin"])

# Pydantic models for admin requests
class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole
    name: str
    age: int
    sex: str
    department_id: Optional[int] = None
    team_id: Optional[int] = None

class CreateConsultantRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    registration_number: str
    hospital: str
    specialization: str

class CreateConsultantWithAvailabilityRequest(BaseModel):
    name: str
    qualifications: str
    registration_number: str
    hospital: str
    specialization: str
    availabilities: List[dict]  # List of availability objects

class AvailabilityRequest(BaseModel):
    day_of_week: int  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    start_time: str  # Format: "HH:MM"
    end_time: str    # Format: "HH:MM"
    is_available: bool = True

class UpdateConsultantRequest(BaseModel):
    name: Optional[str] = None
    qualifications: Optional[str] = None
    registration_number: Optional[str] = None
    hospital: Optional[str] = None
    specialization: Optional[str] = None
    availabilities: Optional[List[dict]] = None

class CreateDepartmentRequest(BaseModel):
    name: str
    description: Optional[str] = None

class CreateTeamRequest(BaseModel):
    name: str
    description: Optional[str] = None
    department_id: int
    employees: Optional[List[int]] = []
    supervisor_id: Optional[int] = None

class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    name: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    department_id: Optional[int] = None
    team_id: Optional[int] = None

# Update department
class UpdateDepartmentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

# Update team
class UpdateTeamRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    department_id: Optional[int] = None
    employees: Optional[List[int]] = None
    supervisor_id: Optional[int] = None

# Department management
@router.post("/departments")
def create_department(request: CreateDepartmentRequest, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    # Check if department already exists
    existing_dept = db.query(Department).filter(Department.name == request.name).first()
    if existing_dept:
        raise HTTPException(status_code=400, detail="Department already exists")
    
    department = Department(
        name=request.name,
        description=request.description,
        created_at=datetime.utcnow()
    )
    
    db.add(department)
    db.commit()
    db.refresh(department)
    
    return {
        "message": "Department created successfully",
        "department": {
            "id": department.id,
            "name": department.name,
            "description": department.description
        }
    }

@router.get("/departments")
def get_all_departments(current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    departments = db.query(Department).all()
    return [
        {
            "id": dept.id,
            "name": dept.name,
            "description": dept.description,
            "team_count": len(dept.teams),
            "employee_count": len(dept.employees)
        }
        for dept in departments
    ]

# Update department
@router.put("/departments/{department_id}")
def update_department(department_id: int, request: UpdateDepartmentRequest, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    if request.name:
        setattr(department, 'name', request.name)
    if request.description is not None:
        setattr(department, 'description', request.description)
    db.commit()
    db.refresh(department)
    return {"message": "Department updated successfully", "department": {"id": department.id, "name": department.name, "description": department.description}}

# Team management
@router.post("/teams")
def create_team(request: CreateTeamRequest, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    # Check if department exists
    department = db.query(Department).filter(Department.id == request.department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Check if team name already exists in this department
    existing_team = db.query(Team).filter(
        Team.name == request.name,
        Team.department_id == request.department_id
    ).first()
    if existing_team:
        raise HTTPException(status_code=400, detail="Team already exists in this department")
    
    # Create team
    team = Team(
        name=request.name,
        description=request.description,
        department_id=request.department_id,
        created_at=datetime.utcnow()
    )
    
    db.add(team)
    db.commit()
    db.refresh(team)
    
    # Assign employees to team
    if request.employees:
        # Check if any employees are already in another team
        already_in_team = db.query(User).filter(User.id.in_(request.employees), User.team_id.isnot(None)).all()
        if already_in_team:
            names = ', '.join([str(getattr(u, 'name', None) or getattr(u, 'username', '')) for u in already_in_team])
            raise HTTPException(status_code=400, detail=f"The following users are already in another team: {names}")
        employees = db.query(User).filter(User.id.in_(request.employees)).all()
        for employee in employees:
            if employee.role.value == UserRole.employee.value:
                setattr(employee, 'team_id', team.id)
                setattr(employee, 'department_id', request.department_id)
    
    # Assign supervisor if provided
    if request.supervisor_id:
        supervisor = db.query(User).filter(User.id == request.supervisor_id).first()
        if not supervisor:
            raise HTTPException(status_code=404, detail="Supervisor not found")
        
        if supervisor.role.value != UserRole.employee.value:
            raise HTTPException(status_code=400, detail="Only employees can be promoted to supervisors")
        
        # Check if supervisor is already assigned to another team
        existing_supervisor_team = db.query(Team).filter(Team.supervisor_id == request.supervisor_id).first()
        if existing_supervisor_team is not None:
            raise HTTPException(status_code=400, detail="Employee is already a supervisor of another team")
        
        # Promote employee to supervisor and assign to team
        setattr(supervisor, 'role', UserRole.supervisor)
        setattr(supervisor, 'team_id', team.id)
        setattr(supervisor, 'department_id', request.department_id)
        setattr(team, 'supervisor_id', request.supervisor_id)
    
    db.commit()
    db.refresh(team)
    
    return {
        "message": "Team created successfully",
        "team": {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "department_id": team.department_id,
            "supervisor_id": team.supervisor_id,
            "employee_count": len(team.employees) if hasattr(team, 'employees') else 0
        }
    }

@router.get("/teams")
def get_all_teams(current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    teams = db.query(Team).all()
    return [
        {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "department_id": team.department_id,
            "department_name": team.department.name,
            "supervisor_id": team.supervisor_id,
            "supervisor_name": team.supervisor.name if team.supervisor else None,
            "employee_count": len(team.employees)
        }
        for team in teams
    ]

@router.get("/teams/department/{department_id}")
def get_teams_by_department(department_id: int, db: Session = Depends(get_db)):
    """Get teams by department, optionally filtering out teams with supervisors"""
    teams = db.query(Team).filter(Team.department_id == department_id).all()
    return [
        {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "department_id": team.department_id,
            "department_name": team.department.name,
            "supervisor_id": team.supervisor_id,
            "supervisor_name": team.supervisor.name if team.supervisor else None,
            "employee_count": len(team.employees)
        }
        for team in teams
    ]

@router.get("/teams/department/{department_id}/supervisor-less")
def get_supervisor_less_teams_by_department(department_id: int, db: Session = Depends(get_db)):
    """Get teams by department that don't have supervisors assigned"""
    teams = db.query(Team).filter(
        Team.department_id == department_id,
        Team.supervisor_id.is_(None)
    ).all()
    return [
        {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "department_id": team.department_id,
            "department_name": team.department.name,
            "supervisor_id": team.supervisor_id,
            "supervisor_name": team.supervisor.name if team.supervisor else None,
            "employee_count": len(team.employees)
        }
        for team in teams
    ]

# Update team
@router.put("/teams/{team_id}")
def update_team(team_id: int, request: UpdateTeamRequest, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if request.name:
        setattr(team, 'name', request.name)
    if request.description is not None:
        setattr(team, 'description', request.description)
    # Update department
    if request.department_id is not None:
        department = db.query(Department).filter(Department.id == request.department_id).first()
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        setattr(team, 'department_id', request.department_id)
        # Update department_id for all team members when department changes
        for emp in team.employees:
            setattr(emp, 'department_id', request.department_id)
        if team.supervisor_id is not None:
            supervisor = db.query(User).filter(User.id == team.supervisor_id).first()
            if supervisor:
                setattr(supervisor, 'department_id', request.department_id)
    # Update employees
    if request.employees is not None:
        # Check if any employees are already in another team (and not this team)
        already_in_team = db.query(User).filter(User.id.in_(request.employees), User.team_id.isnot(None), User.team_id != team.id).all()
        if already_in_team:
            names = ', '.join([str(getattr(u, 'name', None) or getattr(u, 'username', '')) for u in already_in_team])
            raise HTTPException(status_code=400, detail=f"The following users are already in another team: {names}")
        # Remove all current employees from this team
        for emp in team.employees:
            setattr(emp, 'team_id', None)
        # Assign new employees
        employees = db.query(User).filter(User.id.in_(request.employees)).all()
        for emp in employees:
            setattr(emp, 'team_id', team.id)
            # Update employee's department to match team's department
            setattr(emp, 'department_id', team.department_id)
    # Update supervisor
    if request.supervisor_id is not None:
        # Demote old supervisor if exists
        if team.supervisor_id is not None:
            old_supervisor = db.query(User).filter(User.id == team.supervisor_id).first()
            if old_supervisor:
                setattr(old_supervisor, 'role', UserRole.employee.value)
        # Promote new supervisor
        if request.supervisor_id:
            supervisor = db.query(User).filter(User.id == request.supervisor_id).first()
            if not supervisor:
                raise HTTPException(status_code=404, detail="Supervisor not found")
            setattr(supervisor, 'role', UserRole.supervisor.value)
            setattr(team, 'supervisor_id', request.supervisor_id)
            # Update supervisor's department to match team's department
            setattr(supervisor, 'department_id', team.department_id)
        else:
            setattr(team, 'supervisor_id', None)
    db.commit()
    db.refresh(team)
    return {"message": "Team updated successfully", "team": {"id": team.id, "name": team.name, "description": team.description, "supervisor_id": team.supervisor_id}}

# Delete team
@router.delete("/teams/{team_id}")
def delete_team(team_id: int, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    # Remove team assignment from employees
    for emp in team.employees:
        setattr(emp, 'team_id', None)
    # Demote supervisor if exists
    if team.supervisor_id is not None:
        supervisor = db.query(User).filter(User.id == team.supervisor_id).first()
        if supervisor:
            setattr(supervisor, 'role', UserRole.employee.value)
    db.delete(team)
    db.commit()
    return {"message": "Team deleted successfully"}

# Assign supervisor to team
@router.put("/teams/{team_id}/supervisor/{user_id}")
def assign_supervisor(team_id: int, user_id: int, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role.value != UserRole.employee.value:
        raise HTTPException(status_code=400, detail="Only employees can be assigned as supervisors")
    
    # Check if user is already a supervisor of another team
    existing_supervisor_team = db.query(Team).filter(Team.supervisor_id == user_id).first()
    if existing_supervisor_team is not None:
        raise HTTPException(status_code=400, detail="User is already a supervisor of another team")
    
    # Demote old supervisor back to employee if exists
    if team.supervisor_id is not None:
        old_supervisor = db.query(User).filter(User.id == team.supervisor_id).first()
        if old_supervisor is not None:
            setattr(old_supervisor, 'role', UserRole.employee.value)
            # Remove old supervisor from team if they're not already a member
            if getattr(old_supervisor, 'team_id', None) is not None and getattr(old_supervisor, 'team_id', None) != team.id:
                setattr(old_supervisor, 'team_id', None)
    
    # Promote new user to supervisor and add to team
    setattr(user, 'role', UserRole.supervisor.value)
    setattr(user, 'team_id', team.id)
    setattr(user, 'department_id', team.department_id)
    setattr(team, 'supervisor_id', user_id)
    
    db.commit()
    
    return {
        "message": "Supervisor assigned successfully",
        "team": {
            "id": team.id,
            "name": team.name,
            "supervisor_id": team.supervisor_id,
            "supervisor_name": user.name
        }
    }

# Admin creates new users (employees, supervisors, hr managers)
@router.post("/users")
def create_user(request: CreateUserRequest, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.username == request.username) | (User.email == request.email)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Only allow creating non-admin users
    if request.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot create admin users through this endpoint")
    
    # Hash password
    from auth import get_password_hash
    hashed_password = get_password_hash(request.password)
    
    # Create user
    new_user = User(
        username=request.username,
        email=request.email,
        hashed_password=hashed_password,
        role=request.role,
        name=request.name,
        age=request.age,
        sex=request.sex,
        department_id=request.department_id,
        team_id=request.team_id
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "message": "User created successfully",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role.value,
            "name": new_user.name,
            "age": new_user.age,
            "sex": new_user.sex,
            "department_id": new_user.department_id,
            "team_id": new_user.team_id
        }
    }

# Admin creates new consultants (psychiatrists)
@router.post("/consultants")
def create_consultant(request: CreateConsultantRequest, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.username == request.username) | (User.email == request.email)
    ).first()
    if existing_user is not None:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Hash password
    from auth import get_password_hash
    hashed_password = get_password_hash(request.password)
    
    # Create consultant (psychiatrist)
    new_consultant = User(
        username=request.username,
        email=request.email,
        hashed_password=hashed_password,
        role=UserRole.psychiatrist
    )
    
    db.add(new_consultant)
    db.commit()
    db.refresh(new_consultant)
    
    return {
        "message": "Consultant created successfully",
        "consultant": {
            "id": new_consultant.id,
            "username": new_consultant.username,
            "email": new_consultant.email,
            "role": new_consultant.role.value,
            "registration_number": request.registration_number,
            "hospital": request.hospital,
            "specialization": request.specialization
        }
    }

# Admin gets all users
# Get current user data
@router.get("/users/me")
def get_current_user_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "name": current_user.name,
        "department_id": current_user.department_id,
        "team_id": current_user.team_id,
        "is_active": current_user.is_active
    }

@router.get("/users")
def get_all_users(current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "name": user.name,
            "age": user.age,
            "sex": user.sex,
            "department_id": user.department_id,
            "department_name": user.department.name if user.department else None,
            "team_id": user.team_id,
            "team_name": user.team.name if user.team else None,
            "created_at": user.id  # Using id as placeholder for created_at
        }
        for user in users
    ]

# Admin gets users by role
@router.get("/users/{role}")
def get_users_by_role(role: str, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    try:
        user_role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    users = db.query(User).filter(User.role == user_role.value).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "name": user.name,
            "age": user.age,
            "sex": user.sex,
            "department_id": user.department_id,
            "department_name": user.department.name if user.department else None,
            "team_id": user.team_id,
            "team_name": user.team.name if user.team else None
        }
        for user in users
    ]

# Admin updates user
@router.put("/users/{user_id}")
def update_user(user_id: int, request: UpdateUserRequest, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields if provided
    update_data = {}
    
    if request.username is not None:
        # Check if username is already taken by another user
        existing_user = db.query(User).filter(
            User.username == request.username, 
            User.id != user_id
        ).first()
        if existing_user is not None:
            raise HTTPException(status_code=400, detail="Username already taken")
        update_data["username"] = request.username
    
    if request.email is not None:
        # Check if email is already taken by another user
        existing_user = db.query(User).filter(
            User.email == request.email, 
            User.id != user_id
        ).first()
        if existing_user is not None:
            raise HTTPException(status_code=400, detail="Email already taken")
        update_data["email"] = request.email
    
    if request.role is not None:
        update_data["role"] = request.role
    
    if request.name is not None:
        update_data["name"] = request.name
    
    if request.age is not None:
        update_data["age"] = request.age
    
    if request.sex is not None:
        update_data["sex"] = request.sex
    
    if request.department_id is not None:
        update_data["department_id"] = request.department_id
    
    if request.team_id is not None:
        update_data["team_id"] = request.team_id
    
    # Apply updates
    for field, value in update_data.items():
        setattr(user, field, value)
    
    # If user role is changed from supervisor to something else, remove them as supervisor from any teams
    if request.role is not None and user.role.value != UserRole.supervisor.value:
        # Find any teams where this user is the supervisor
        teams_with_user_as_supervisor = db.query(Team).filter(Team.supervisor_id == user_id).all()
        for team in teams_with_user_as_supervisor:
            setattr(team, 'supervisor_id', None)
    
    db.commit()
    db.refresh(user)
    
    return {
        "message": "User updated successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "name": user.name,
            "age": user.age,
            "sex": user.sex,
            "department_id": user.department_id,
            "team_id": user.team_id
        }
    }

# Admin deletes user
@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Prevent deletion of admin users
    if user.role.value == UserRole.admin.value:
        # Check if this is the only admin in the system
        admin_count = db.query(User).filter(User.role == UserRole.admin.value).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the only admin user in the system")
        else:
            raise HTTPException(status_code=400, detail="Cannot delete admin users")
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}

# Admin dashboard
@router.get("/dashboard")
def admin_dashboard(current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    # Get counts by role
    employee_count = db.query(User).filter(User.role == UserRole.employee.value).count()
    supervisor_count = db.query(User).filter(User.role == UserRole.supervisor.value).count()
    hr_count = db.query(User).filter(User.role == UserRole.hr_manager.value).count()
    consultant_count = db.query(User).filter(User.role == UserRole.psychiatrist.value).count()
    total_users = db.query(User).count()
    department_count = db.query(Department).count()
    team_count = db.query(Team).count()
    pending_requests_count = db.query(UserRegistrationRequest).filter(UserRegistrationRequest.status == RequestStatus.pending).count()
    
    return {
        "user": current_user.username,
        "stats": {
            "total_users": total_users,
            "employees": employee_count,
            "supervisors": supervisor_count,
            "hr_managers": hr_count,
            "consultants": consultant_count,
            "departments": department_count,
            "teams": team_count,
            "pending_requests": pending_requests_count
        },
        "recent_users": [
            {
                "id": user.id,
                "username": user.username,
                "role": user.role.value,
                "name": user.name
            }
            for user in db.query(User).order_by(User.id.desc()).limit(5).all()
        ]
    }

# Consultant management endpoints
@router.post("/consultants/with-availability")
def create_consultant_with_availability(request: CreateConsultantWithAvailabilityRequest, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    # Check if consultant with registration number already exists
    existing_consultant = db.query(Consultant).filter(Consultant.registration_number == request.registration_number).first()
    if existing_consultant:
        raise HTTPException(status_code=400, detail="Consultant with this registration number already exists")
    
    # Create consultant
    consultant = Consultant(
        name=request.name,
        qualifications=request.qualifications,
        registration_number=request.registration_number,
        hospital=request.hospital,
        specialization=request.specialization,
        created_at=datetime.utcnow()
    )
    
    db.add(consultant)
    db.commit()
    db.refresh(consultant)
    
    # Add availabilities
    for availability_data in request.availabilities:
        try:
            start_time = datetime.strptime(availability_data['start_time'], '%H:%M').time()
            end_time = datetime.strptime(availability_data['end_time'], '%H:%M').time()
            
            availability = ConsultantAvailability(
                consultant_id=consultant.id,
                day_of_week=availability_data['day_of_week'],
                start_time=start_time,
                end_time=end_time,
                is_available=True
            )
            db.add(availability)
        except (ValueError, KeyError) as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Invalid availability data: {str(e)}")
    
    db.commit()
    db.refresh(consultant)
    
    return {
        "message": "Consultant created successfully with availability",
        "consultant": {
            "id": consultant.id,
            "name": consultant.name,
            "qualifications": consultant.qualifications,
            "registration_number": consultant.registration_number,
            "hospital": consultant.hospital,
            "specialization": consultant.specialization,
            "availabilities": [
                {
                    "day_of_week": avail.day_of_week,
                    "start_time": avail.start_time.strftime('%H:%M'),
                    "end_time": avail.end_time.strftime('%H:%M'),
                    "is_available": avail.is_available
                }
                for avail in consultant.availabilities
            ]
        }
    }

@router.get("/consultants")
def get_all_consultants(current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    consultants = db.query(Consultant).all()
    return [
        {
            "id": consultant.id,
            "name": consultant.name,
            "qualifications": consultant.qualifications,
            "registration_number": consultant.registration_number,
            "hospital": consultant.hospital,
            "specialization": consultant.specialization,
            "created_at": consultant.created_at,
            "availabilities": [
                {
                    "id": avail.id,
                    "day_of_week": avail.day_of_week,
                    "start_time": avail.start_time.strftime('%H:%M'),
                    "end_time": avail.end_time.strftime('%H:%M'),
                    "is_available": avail.is_available
                }
                for avail in consultant.availabilities
            ]
        }
        for consultant in consultants
    ]

@router.get("/consultants/{consultant_id}")
def get_consultant(consultant_id: int, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    return {
        "id": consultant.id,
        "name": consultant.name,
        "qualifications": consultant.qualifications,
        "registration_number": consultant.registration_number,
        "hospital": consultant.hospital,
        "specialization": consultant.specialization,
        "created_at": consultant.created_at,
        "availabilities": [
            {
                "id": avail.id,
                "day_of_week": avail.day_of_week,
                "start_time": avail.start_time.strftime('%H:%M'),
                "end_time": avail.end_time.strftime('%H:%M'),
                "is_available": avail.is_available
            }
            for avail in consultant.availabilities
        ]
    }

@router.put("/consultants/{consultant_id}")
def update_consultant(consultant_id: int, request: UpdateConsultantRequest, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    # Update basic fields
    if request.name is not None:
        setattr(consultant, 'name', request.name)
    if request.qualifications is not None:
        setattr(consultant, 'qualifications', request.qualifications)
    if request.hospital is not None:
        setattr(consultant, 'hospital', request.hospital)
    if request.specialization is not None:
        setattr(consultant, 'specialization', request.specialization)
    
    # Check registration number uniqueness if being updated
    if request.registration_number is not None:
        existing_consultant = db.query(Consultant).filter(
            Consultant.registration_number == request.registration_number,
            Consultant.id != consultant_id
        ).first()
        if existing_consultant:
            raise HTTPException(status_code=400, detail="Registration number already exists")
        setattr(consultant, 'registration_number', request.registration_number)
    
    # Update availabilities if provided
    if request.availabilities is not None:
        # Delete existing availabilities
        db.query(ConsultantAvailability).filter(ConsultantAvailability.consultant_id == consultant_id).delete()
        
        # Add new availabilities
        for availability_data in request.availabilities:
            try:
                start_time = datetime.strptime(availability_data['start_time'], '%H:%M').time()
                end_time = datetime.strptime(availability_data['end_time'], '%H:%M').time()
                
                availability = ConsultantAvailability(
                    consultant_id=consultant.id,
                    day_of_week=availability_data['day_of_week'],
                    start_time=start_time,
                    end_time=end_time,
                    is_available=True
                )
                db.add(availability)
            except (ValueError, KeyError) as e:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"Invalid availability data: {str(e)}")
    
    db.commit()
    db.refresh(consultant)
    
    return {
        "message": "Consultant updated successfully",
        "consultant": {
            "id": consultant.id,
            "name": consultant.name,
            "qualifications": consultant.qualifications,
            "registration_number": consultant.registration_number,
            "hospital": consultant.hospital,
            "specialization": consultant.specialization,
            "availabilities": [
                {
                    "id": avail.id,
                    "day_of_week": avail.day_of_week,
                    "start_time": avail.start_time.strftime('%H:%M'),
                    "end_time": avail.end_time.strftime('%H:%M'),
                    "is_available": avail.is_available
                }
                for avail in consultant.availabilities
            ]
        }
    }

@router.delete("/consultants/{consultant_id}")
def delete_consultant(consultant_id: int, current_user: User = Depends(require_role(UserRole.admin)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    db.delete(consultant)
    db.commit()
    
    return {"message": "Consultant deleted successfully"} 