from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, time, timedelta
from typing import List, Optional
from pydantic import BaseModel, EmailStr, validator, ValidationError
from models import User, Consultant, ConsultantAvailability, ConsultantBooking, BookingStatus
from dependencies import get_db, require_role, UserRole
from sqlalchemy import func
import re

router = APIRouter(prefix="/hr/psychiatrists", tags=["HR Psychiatrist Management"])

class CreatePsychiatristWithAvailabilityRequest(BaseModel):
    name: str
    qualifications: str
    registration_number: str
    hospital: str
    specialization: str
    email: EmailStr  # Changed from username to email
    password: str
    availabilities: List[dict]  # List of availability objects
    
    @validator('availabilities')
    def validate_availabilities(cls, v):
        print(f"Validating availabilities: {v}")
        if not v:
            raise ValueError('At least one availability slot is required')
        for i, availability in enumerate(v):
            print(f"Validating availability {i}: {availability}")
            if not isinstance(availability, dict):
                raise ValueError(f'Each availability must be a dictionary, got {type(availability)}')
            required_fields = ['day_of_week', 'start_time', 'end_time']
            for field in required_fields:
                if field not in availability:
                    raise ValueError(f'Missing required field in availability: {field}')
                print(f"Field {field}: {availability[field]} (type: {type(availability[field])})")
        return v
    
    @validator('password')
    def validate_password(cls, v):
        print(f"Validating password: {v[:3]}... (length: {len(v) if v else 0})")
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        print(f"Validating name: {v}")
        if len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters long')
        return v.strip()
    
    @validator('registration_number')
    def validate_registration_number(cls, v):
        print(f"Validating registration_number: {v}")
        if len(v.strip()) < 3:
            raise ValueError('Registration number must be at least 3 characters long')
        return v.strip()

class UpdatePsychiatristRequest(BaseModel):
    name: Optional[str] = None
    qualifications: Optional[str] = None
    registration_number: Optional[str] = None
    hospital: Optional[str] = None
    specialization: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    availabilities: Optional[List[dict]] = None
    
    @validator('password')
    def validate_password(cls, v):
        if v is not None:
            if len(v) < 8:
                raise ValueError('Password must be at least 8 characters long')
            if not re.search(r'[A-Z]', v):
                raise ValueError('Password must contain at least one uppercase letter')
            if not re.search(r'[a-z]', v):
                raise ValueError('Password must contain at least one lowercase letter')
            if not re.search(r'\d', v):
                raise ValueError('Password must contain at least one number')
        return v

@router.post("/with-availability")
async def create_psychiatrist_with_availability(psychiatrist_data: CreatePsychiatristWithAvailabilityRequest, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    try:
        print(f"Received psychiatrist creation request: {psychiatrist_data}")
        print(f"Request data: {psychiatrist_data.dict()}")
        print(f"Availabilities: {psychiatrist_data.availabilities}")
        print(f"Email: {psychiatrist_data.email}")
        print(f"Password length: {len(psychiatrist_data.password) if psychiatrist_data.password else 0}")
        print(f"Name: {psychiatrist_data.name}")
        print(f"Qualifications: {psychiatrist_data.qualifications}")
        print(f"Registration number: {psychiatrist_data.registration_number}")
        print(f"Hospital: {psychiatrist_data.hospital}")
        print(f"Specialization: {psychiatrist_data.specialization}")
        
        # Check if consultant with registration number already exists
        existing_consultant = db.query(Consultant).filter(Consultant.registration_number == psychiatrist_data.registration_number).first()
        if existing_consultant:
            raise HTTPException(status_code=400, detail="Registration number already exists")
        
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == psychiatrist_data.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")
        
        # Create consultant
        consultant = Consultant(
            name=psychiatrist_data.name,
            qualifications=psychiatrist_data.qualifications,
            registration_number=psychiatrist_data.registration_number,
            hospital=psychiatrist_data.hospital,
            specialization=psychiatrist_data.specialization,
            created_at=datetime.utcnow()
        )
        db.add(consultant)
        db.flush()  # Get the ID without committing
        
        # Create user account for the consultant
        from auth import get_password_hash
        hashed_password = get_password_hash(psychiatrist_data.password)
        user = User(
            username=psychiatrist_data.email,  # Use email as username
            email=psychiatrist_data.email,
            hashed_password=hashed_password,
            role=UserRole.psychiatrist,
            name=psychiatrist_data.name
        )
        db.add(user)
        db.flush()
        
        # Create availabilities
        for availability_data in psychiatrist_data.availabilities:
            try:
                # Ensure time format is correct (HH:MM)
                start_time_str = availability_data['start_time']
                end_time_str = availability_data['end_time']
                
                # Validate time format
                if not (len(start_time_str) == 5 and start_time_str[2] == ':' and 
                       len(end_time_str) == 5 and end_time_str[2] == ':'):
                    raise HTTPException(
                        status_code=422, 
                        detail=f"Invalid time format. Expected HH:MM format, got start_time: {start_time_str}, end_time: {end_time_str}"
                    )
                
                availability = ConsultantAvailability(
                    consultant_id=consultant.id,
                    day_of_week=availability_data['day_of_week'],
                    start_time=time.fromisoformat(start_time_str),
                    end_time=time.fromisoformat(end_time_str),
                    is_available=availability_data.get('is_available', True)
                )
                db.add(availability)
            except ValueError as e:
                raise HTTPException(
                    status_code=422, 
                    detail=f"Invalid time format in availability: {e}. Expected HH:MM format."
                )
            except KeyError as e:
                raise HTTPException(
                    status_code=422, 
                    detail=f"Missing required field in availability: {e}"
                )
        
        db.commit()
        db.refresh(consultant)
        
        return {
            "id": consultant.id,
            "name": consultant.name,
            "qualifications": consultant.qualifications,
            "registration_number": consultant.registration_number,
            "hospital": consultant.hospital,
            "specialization": consultant.specialization,
            "email": psychiatrist_data.email,
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
    except ValidationError as e:
        print(f"Pydantic validation error: {e}")
        print(f"Validation errors: {e.errors()}")
        raise HTTPException(status_code=422, detail=f"Validation error: {str(e)}")
    except Exception as e:
        db.rollback()
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create psychiatrist: {str(e)}")

@router.get("/")
def get_all_psychiatrists(current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    consultants = db.query(Consultant).all()
    return [
        {
            "id": consultant.id,
            "name": consultant.name,
            "qualifications": consultant.qualifications,
            "registration_number": consultant.registration_number,
            "hospital": consultant.hospital,
            "specialization": consultant.specialization,
            "username": consultant.name,  # Using consultant name as username for now
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

@router.get("/{psychiatrist_id}")
def get_psychiatrist(psychiatrist_id: int, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == psychiatrist_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist not found")
    
    return {
        "id": consultant.id,
        "name": consultant.name,
        "qualifications": consultant.qualifications,
        "registration_number": consultant.registration_number,
        "hospital": consultant.hospital,
        "specialization": consultant.specialization,
        "username": consultant.name,  # Using consultant name as username for now
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

@router.put("/{psychiatrist_id}")
def update_psychiatrist(psychiatrist_id: int, request: UpdatePsychiatristRequest, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == psychiatrist_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist not found")
    
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
            Consultant.id != psychiatrist_id
        ).first()
        if existing_consultant:
            raise HTTPException(status_code=400, detail="Registration number already exists")
        setattr(consultant, 'registration_number', request.registration_number)
    
    # Update user account if username or password is provided
    if request.email is not None or request.password is not None:
        # Find the user account for this consultant
        user = db.query(User).filter(
            User.username == consultant.name,  # Assuming username is stored as consultant name
            User.role == UserRole.psychiatrist
        ).first()
        
        if user:
            if request.email is not None:
                # Check if new email already exists
                existing_user = db.query(User).filter(
                    User.username == request.email,
                    User.id != user.id
                ).first()
                if existing_user:
                    raise HTTPException(status_code=400, detail="Username already exists")
                user.username = request.email
                user.email = request.email  # Update email too
            
            if request.password is not None:
                from auth import get_password_hash
                user.hashed_password = get_password_hash(request.password)
    
    # Update availabilities if provided
    if request.availabilities is not None:
        # Delete existing availabilities
        db.query(ConsultantAvailability).filter(ConsultantAvailability.consultant_id == psychiatrist_id).delete()
        
        # Create new availabilities
        for availability_data in request.availabilities:
            availability = ConsultantAvailability(
                consultant_id=psychiatrist_id,
                day_of_week=availability_data['day_of_week'],
                start_time=time.fromisoformat(availability_data['start_time']),
                end_time=time.fromisoformat(availability_data['end_time']),
                is_available=availability_data.get('is_available', True)
            )
            db.add(availability)
    
    db.commit()
    db.refresh(consultant)
    
    return {
        "id": consultant.id,
        "name": consultant.name,
        "qualifications": consultant.qualifications,
        "registration_number": consultant.registration_number,
        "hospital": consultant.hospital,
        "specialization": consultant.specialization,
        "username": consultant.name,
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

@router.delete("/{psychiatrist_id}")
def delete_psychiatrist(psychiatrist_id: int, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == psychiatrist_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist not found")
    
    # Find and delete the associated user account
    user = db.query(User).filter(
        User.username == consultant.name,
        User.role == UserRole.psychiatrist
    ).first()
    
    if user:
        db.delete(user)
    
    # Delete the consultant (availabilities will be deleted due to cascade)
    db.delete(consultant)
    db.commit()
    
    return {"message": "Psychiatrist deleted successfully"}

@router.get("/{psychiatrist_id}/bookings")
def get_psychiatrist_bookings(psychiatrist_id: int, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == psychiatrist_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist not found")
    
    bookings = db.query(ConsultantBooking).filter(ConsultantBooking.consultant_id == psychiatrist_id).all()
    
    return [
        {
            "id": booking.id,
            "employee_name": booking.employee.name if booking.employee else "Unknown",
            "booked_by_name": booking.booked_by.name if booking.booked_by else "Unknown",
            "booking_date": booking.booking_date,
            "status": booking.status.value,
            "duration_minutes": booking.duration_minutes,
            "notes": booking.notes,
            "created_at": booking.created_at
        }
        for booking in bookings
    ]

@router.get("/{psychiatrist_id}/available-times")
def get_psychiatrist_available_times(psychiatrist_id: int, date: str, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == psychiatrist_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist not found")
    
    # Parse the date
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Get day of week (0=Monday, 6=Sunday)
    day_of_week = target_date.weekday()
    
    # Get availabilities for this day
    availabilities = db.query(ConsultantAvailability).filter(
        ConsultantAvailability.consultant_id == psychiatrist_id,
        ConsultantAvailability.day_of_week == day_of_week,
        ConsultantAvailability.is_available == True
    ).all()
    
    if not availabilities:
        return {"available_times": []}
    
    # Get existing bookings for this date
    bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == psychiatrist_id,
        func.date(ConsultantBooking.booking_date) == target_date,
        ConsultantBooking.status.in_([BookingStatus.pending, BookingStatus.approved])
    ).all()
    
    # Create booked time slots
    booked_slots = set()
    for booking in bookings:
        start_time = booking.booking_date.time()
        end_time = (datetime.combine(target_date, start_time) + timedelta(minutes=booking.duration_minutes)).time()
        
        # Add 30-minute slots within the booking duration
        current_time = start_time
        while current_time < end_time:
            booked_slots.add(current_time.strftime('%H:%M'))
            current_time = (datetime.combine(target_date, current_time) + timedelta(minutes=30)).time()
    
    # Generate available time slots
    available_times = []
    session_duration = 30  # 30-minute sessions
    
    for availability in availabilities:
        current_time = availability.start_time
        while current_time < availability.end_time:
            time_str = current_time.strftime('%H:%M')
            if time_str not in booked_slots:
                available_times.append(time_str)
            current_time = (datetime.combine(target_date, current_time) + timedelta(minutes=session_duration)).time()
    
    return {"available_times": available_times} 