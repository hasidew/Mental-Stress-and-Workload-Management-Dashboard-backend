from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from database import SessionLocal
from models import User, UserRole, UserRegistrationRequest, RequestStatus, Department, Team
from dependencies import get_current_user, require_role, get_db
from auth import get_password_hash

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/registration-requests", tags=["registration-requests"])

# Pydantic models
class RegistrationRequestCreate(BaseModel):
    first_name: str
    last_name: str
    gender: str
    nic: str
    birthday: datetime
    contact: Optional[str] = None
    job_role: str
    employee_id: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None
    address: Optional[str] = None
    supervisor_name: Optional[str] = None
    registration_number: Optional[str] = None
    hospital: Optional[str] = None
    username: str
    email: EmailStr
    password: str

class RegistrationRequestResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    gender: str
    nic: str
    birthday: datetime
    contact: Optional[str] = None
    job_role: str
    employee_id: Optional[str] = None
    department: Optional[str] = None
    team: Optional[str] = None
    address: Optional[str] = None
    supervisor_name: Optional[str] = None
    registration_number: Optional[str] = None
    hospital: Optional[str] = None
    username: str
    email: str
    status: str
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

class ApproveRejectRequest(BaseModel):
    action: str  # "approve" or "reject"
    rejection_reason: Optional[str] = None

# Submit registration request
@router.post("/submit", response_model=dict)
def submit_registration_request(request: RegistrationRequestCreate, db: Session = Depends(get_db)):
    # Check for duplicate username or email
    existing_user = db.query(User).filter(
        (User.username == request.username) | (User.email == request.email)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Check for duplicate registration number if provided
    if request.registration_number and request.registration_number.strip():
        existing_registration = db.query(UserRegistrationRequest).filter(
            UserRegistrationRequest.registration_number == request.registration_number
        ).first()
        if existing_registration:
            raise HTTPException(status_code=400, detail="Registration number already exists")
    
    # Check for duplicate employee ID if provided
    if request.employee_id:
        existing_employee = db.query(User).filter(User.name == request.employee_id).first()
        if existing_employee:
            raise HTTPException(status_code=400, detail="Employee ID already exists")
    
    # Check for duplicate NIC
    existing_nic = db.query(UserRegistrationRequest).filter(
        UserRegistrationRequest.nic == request.nic
    ).first()
    if existing_nic:
        raise HTTPException(status_code=400, detail="NIC already exists in a pending request")
    
    # Hash the password
    hashed_password = get_password_hash(request.password)
    
    # Clean up empty strings to None for optional fields
    registration_number = request.registration_number.strip() if request.registration_number and request.registration_number.strip() else None
    hospital = request.hospital.strip() if request.hospital and request.hospital.strip() else None
    team = request.team.strip() if request.team and request.team.strip() else None
    address = request.address.strip() if request.address and request.address.strip() else None
    supervisor_name = request.supervisor_name.strip() if request.supervisor_name and request.supervisor_name.strip() else None
    contact = request.contact.strip() if request.contact and request.contact.strip() else None
    
    # Create registration request
    registration_request = UserRegistrationRequest(
        first_name=request.first_name,
        last_name=request.last_name,
        gender=request.gender,
        nic=request.nic,
        birthday=request.birthday,
        contact=contact,
        job_role=request.job_role,
        employee_id=request.employee_id,
        department=request.department,
        team=team,
        address=address,
        supervisor_name=supervisor_name,
        registration_number=registration_number,
        hospital=hospital,
        username=request.username,
        email=request.email,
        password=hashed_password,
        status=RequestStatus.pending
    )
    
    db.add(registration_request)
    db.commit()
    db.refresh(registration_request)
    
    return {
        "message": "Registration request submitted successfully. Please wait for admin approval.",
        "request_id": registration_request.id
    }

# Get all registration requests (admin only)
@router.get("/all", response_model=List[RegistrationRequestResponse])
def get_all_registration_requests(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    requests = db.query(UserRegistrationRequest).order_by(UserRegistrationRequest.submitted_at.desc()).all()
    return requests

# Get pending registration requests (admin only)
@router.get("/pending", response_model=List[RegistrationRequestResponse])
def get_pending_registration_requests(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    requests = db.query(UserRegistrationRequest).filter(
        UserRegistrationRequest.status == RequestStatus.pending
    ).order_by(UserRegistrationRequest.submitted_at.desc()).all()
    return requests

# Approve or reject registration request (admin only)
@router.put("/{request_id}/review")
def review_registration_request(
    request_id: int,
    review_data: ApproveRejectRequest,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    registration_request = db.query(UserRegistrationRequest).filter(
        UserRegistrationRequest.id == request_id
    ).first()
    
    if not registration_request:
        raise HTTPException(status_code=404, detail="Registration request not found")
    
    if registration_request.status != RequestStatus.pending:
        raise HTTPException(status_code=400, detail="Request has already been reviewed")
    
    if review_data.action == "approve":
        # Check for duplicates again before approving
        existing_user = db.query(User).filter(
            (User.username == registration_request.username) | (User.email == registration_request.email)
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username or email already exists")
        
        # Check for duplicate employee ID if provided
        if registration_request.employee_id:
            existing_employee = db.query(User).filter(User.name == registration_request.employee_id).first()
            if existing_employee:
                raise HTTPException(status_code=400, detail="Employee ID already exists")
        
        # Check for duplicate registration number if provided
        if registration_request.registration_number:
            existing_registration = db.query(User).filter(
                User.registration_number == registration_request.registration_number
            ).first()
            if existing_registration:
                raise HTTPException(status_code=400, detail="Registration number already exists")
        
        # Map job role to UserRole
        role_mapping = {
            "Employee": UserRole.employee,
            "Supervisor": UserRole.supervisor,
            "HR Manager": UserRole.hr_manager,
            "Consultant": UserRole.consultant,
            "Psychiatrist": UserRole.psychiatrist
        }
        
        user_role = role_mapping.get(registration_request.job_role)
        if not user_role:
            raise HTTPException(status_code=400, detail="Invalid job role")
        
        # Create the user
        new_user = User(
            username=registration_request.username,
            email=registration_request.email,
            hashed_password=registration_request.password,
            role=user_role,
            name=f"{registration_request.first_name} {registration_request.last_name}",
            age=(datetime.utcnow() - registration_request.birthday).days // 365,
            sex=registration_request.gender
        )
        
        # Set department and team if provided
        if registration_request.department:
            department = db.query(Department).filter(Department.name == registration_request.department).first()
            if department:
                new_user.department_id = department.id
        
        if registration_request.team:
            team = db.query(Team).filter(Team.name == registration_request.team).first()
            if team:
                new_user.team_id = team.id
        
        db.add(new_user)
        
        # Update request status
        registration_request.status = RequestStatus.approved
        registration_request.reviewed_at = datetime.utcnow()
        registration_request.reviewed_by = current_user.id
        
        db.commit()
        
        return {
            "message": "Registration request approved successfully",
            "user_id": new_user.id
        }
    
    elif review_data.action == "reject":
        registration_request.status = RequestStatus.rejected
        registration_request.reviewed_at = datetime.utcnow()
        registration_request.reviewed_by = current_user.id
        registration_request.rejection_reason = review_data.rejection_reason
        
        db.commit()
        
        return {
            "message": "Registration request rejected",
            "rejection_reason": review_data.rejection_reason
        }
    
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'approve' or 'reject'")

# Get registration request by ID (admin only)
@router.get("/{request_id}", response_model=RegistrationRequestResponse)
def get_registration_request(
    request_id: int,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    registration_request = db.query(UserRegistrationRequest).filter(
        UserRegistrationRequest.id == request_id
    ).first()
    
    if not registration_request:
        raise HTTPException(status_code=404, detail="Registration request not found")
    
    return registration_request 