from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, time, timedelta
from typing import List, Optional
from pydantic import BaseModel
from models import User, Consultant, ConsultantAvailability, ConsultantBooking, BookingStatus
from dependencies import get_db, require_role, UserRole
from sqlalchemy import func

router = APIRouter(prefix="/hr/consultants", tags=["HR Consultant Management"])

class CreateConsultantWithAvailabilityRequest(BaseModel):
    name: str
    qualifications: str
    registration_number: str
    hospital: str
    specialization: str
    username: str
    password: str
    availabilities: List[dict]  # List of availability objects

class UpdateConsultantRequest(BaseModel):
    name: Optional[str] = None
    qualifications: Optional[str] = None
    registration_number: Optional[str] = None
    hospital: Optional[str] = None
    specialization: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    availabilities: Optional[List[dict]] = None

@router.post("/with-availability")
def create_consultant_with_availability(request: CreateConsultantWithAvailabilityRequest, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    # Check if consultant with registration number already exists
    existing_consultant = db.query(Consultant).filter(Consultant.registration_number == request.registration_number).first()
    if existing_consultant:
        raise HTTPException(status_code=400, detail="Consultant with this registration number already exists")
    
    # Check if user with username already exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this username already exists")
    
    # Hash the password
    from auth import get_password_hash
    hashed_password = get_password_hash(request.password)
    
    # Create user account for consultant
    user = User(
        username=request.username,
        email=request.username,  # Using username as email for consultants
        hashed_password=hashed_password,
        role=UserRole.consultant,
        name=request.name
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
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
            "username": user.username,
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

@router.get("/")
def get_all_consultants(current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
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

@router.get("/{consultant_id}")
def get_consultant(consultant_id: int, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
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

@router.put("/{consultant_id}")
def update_consultant(consultant_id: int, request: UpdateConsultantRequest, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
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
    
    # Update user account if username or password is provided
    if request.username is not None or request.password is not None:
        # Find the user account for this consultant
        user = db.query(User).filter(
            User.username == consultant.name,  # Assuming username is stored as consultant name
            User.role == UserRole.consultant
        ).first()
        
        if user:
            if request.username is not None:
                # Check if new username already exists
                existing_user = db.query(User).filter(
                    User.username == request.username,
                    User.id != user.id
                ).first()
                if existing_user:
                    raise HTTPException(status_code=400, detail="Username already exists")
                user.username = request.username
                user.email = request.username  # Update email as well
            
            if request.password is not None:
                from auth import get_password_hash
                user.hashed_password = get_password_hash(request.password)
        else:
            # Create new user account if none exists
            if request.username is None:
                raise HTTPException(status_code=400, detail="Username is required when creating user account")
            if request.password is None:
                raise HTTPException(status_code=400, detail="Password is required when creating user account")
            
            # Check if username already exists
            existing_user = db.query(User).filter(User.username == request.username).first()
            if existing_user:
                raise HTTPException(status_code=400, detail="Username already exists")
            
            from auth import get_password_hash
            user = User(
                username=request.username,
                email=request.username,
                hashed_password=get_password_hash(request.password),
                role=UserRole.consultant,
                name=consultant.name
            )
            db.add(user)
    
    # Update availabilities if provided
    if request.availabilities is not None:
        # Get current bookings for this consultant
        current_bookings = db.query(ConsultantBooking).filter(
            ConsultantBooking.consultant_id == consultant_id,
            ConsultantBooking.status == BookingStatus.pending
        ).all()
        
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
        
        # Cancel bookings that conflict with new availability
        cancelled_bookings = []
        for booking in current_bookings:
            booking_date = booking.booking_date
            booking_day = booking_date.weekday()  # 0=Monday, 6=Sunday
            booking_time = booking_date.time()
            
            # Check if booking time conflicts with new availability
            conflict_found = True
            for availability_data in request.availabilities:
                if availability_data['day_of_week'] == booking_day:
                    start_time = datetime.strptime(availability_data['start_time'], '%H:%M').time()
                    end_time = datetime.strptime(availability_data['end_time'], '%H:%M').time()
                    
                    if start_time <= booking_time <= end_time:
                        conflict_found = False
                        break
            
            if conflict_found:
                setattr(booking, 'status', BookingStatus.cancelled)
                cancelled_bookings.append(booking.id)
    
    db.commit()
    db.refresh(consultant)
    
    return {
        "message": "Consultant updated successfully",
        "cancelled_bookings": cancelled_bookings if request.availabilities is not None else [],
        "consultant": {
            "id": consultant.id,
            "name": consultant.name,
            "qualifications": consultant.qualifications,
            "registration_number": consultant.registration_number,
            "hospital": consultant.hospital,
            "specialization": consultant.specialization,
            "username": user.username if 'user' in locals() else None,
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

@router.delete("/{consultant_id}")
def delete_consultant(consultant_id: int, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    # Cancel all scheduled bookings for this consultant
    scheduled_bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == consultant_id,
        ConsultantBooking.status == BookingStatus.pending
    ).all()
    
    cancelled_count = 0
    for booking in scheduled_bookings:
        setattr(booking, 'status', BookingStatus.cancelled)
        cancelled_count += 1
    
    # Delete the consultant (this will cascade delete availabilities)
    db.delete(consultant)
    db.commit()
    
    return {
        "message": "Consultant deleted successfully",
        "cancelled_bookings": cancelled_count
    }

@router.get("/{consultant_id}/bookings")
def get_consultant_bookings(consultant_id: int, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    consultant = db.query(Consultant).filter(Consultant.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    bookings = db.query(ConsultantBooking).filter(ConsultantBooking.consultant_id == consultant_id).all()
    
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

@router.get("/{consultant_id}/available-times")
def get_consultant_available_times(consultant_id: int, date: str, current_user: User = Depends(require_role(UserRole.hr_manager)), db: Session = Depends(get_db)):
    """Get available time slots for a consultant on a specific date"""
    consultant = db.query(Consultant).filter(Consultant.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    # Parse the date
    try:
        booking_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Get the day of week (0=Monday, 6=Sunday)
    day_of_week = booking_date.weekday()
    
    # Get consultant's availability for this day
    availabilities = db.query(ConsultantAvailability).filter(
        ConsultantAvailability.consultant_id == consultant_id,
        ConsultantAvailability.day_of_week == day_of_week,
        ConsultantAvailability.is_available == True
    ).all()
    
    if not availabilities:
        return {"available_times": []}
    
    # Get existing bookings for this consultant on this date
    existing_bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == consultant_id,
        ConsultantBooking.status == BookingStatus.pending,
        func.date(ConsultantBooking.booking_date) == booking_date
    ).all()
    
    # Generate 30-minute time slots for each availability period
    available_times = []
    session_duration = 30  # minutes
    
    for availability in availabilities:
        start_time = availability.start_time
        end_time = availability.end_time
        
        # Convert to datetime for easier manipulation
        start_dt = datetime.combine(booking_date, start_time)
        end_dt = datetime.combine(booking_date, end_time)
        
        # Generate 30-minute slots
        current_time = start_dt
        while current_time + timedelta(minutes=session_duration) <= end_dt:
            slot_start = current_time
            slot_end = current_time + timedelta(minutes=session_duration)
            
            # Check if this slot conflicts with existing bookings
            conflict = False
            for booking in existing_bookings:
                booking_start = booking.booking_date
                booking_end = booking.booking_date + timedelta(minutes=booking.duration_minutes)
                
                # Check for overlap
                if (slot_start < booking_end and slot_end > booking_start):
                    conflict = True
                    break
            
            if not conflict:
                available_times.append({
                    "start_time": slot_start.strftime('%H:%M'),
                    "end_time": slot_end.strftime('%H:%M'),
                    "display": f"{slot_start.strftime('%H:%M')} - {slot_end.strftime('%H:%M')}"
                })
            
            current_time += timedelta(minutes=session_duration)
    
    return {"available_times": available_times} 