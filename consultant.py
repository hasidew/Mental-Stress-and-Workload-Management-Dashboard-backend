from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from database import SessionLocal
from models import User, UserRole, Consultant, ConsultantAvailability, ConsultantBooking, BookingStatus
from dependencies import get_current_user, require_role, require_roles, get_db

router = APIRouter(prefix="/consultant", tags=["consultant"])

# Pydantic models
class ConsultantResponse(BaseModel):
    id: int
    name: str
    qualifications: str
    registration_number: str
    hospital: str
    specialization: str
    availabilities: List[dict]

class BookingRequest(BaseModel):
    consultant_id: int
    booking_date: datetime
    duration_minutes: int = 60
    notes: Optional[str] = None

class BookingResponse(BaseModel):
    id: int
    consultant_id: int
    consultant_name: str
    employee_id: int
    employee_name: str
    booked_by_id: int
    booked_by_name: str
    booking_date: datetime
    duration_minutes: int
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class UpdateBookingRequest(BaseModel):
    consultant_id: Optional[int] = None
    booking_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None

@router.get("/available", response_model=List[ConsultantResponse])
def get_available_consultants(
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Get all available consultants with their availabilities"""
    consultants = db.query(Consultant).all()
    
    result = []
    for consultant in consultants:
        availabilities = db.query(ConsultantAvailability).filter(
            ConsultantAvailability.consultant_id == consultant.id,
            ConsultantAvailability.is_available == True
        ).all()
        
        availability_data = []
        for availability in availabilities:
            availability_data.append({
                "id": availability.id,
                "day_of_week": availability.day_of_week,
                "start_time": str(availability.start_time),
                "end_time": str(availability.end_time),
                "is_available": availability.is_available
            })
        
        result.append({
            "id": consultant.id,
            "name": consultant.name,
            "qualifications": consultant.qualifications,
            "registration_number": consultant.registration_number,
            "hospital": consultant.hospital,
            "specialization": consultant.specialization,
            "availabilities": availability_data
        })
    
    return result

@router.post("/book", response_model=BookingResponse)
def book_consultation(
    request: BookingRequest,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Book a consultation session"""
    # Check if consultant exists
    consultant = db.query(Consultant).filter(Consultant.id == request.consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    # Check if booking time is in the future
    if request.booking_date <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Booking date must be in the future")
    
    # Check if consultant is available at that time
    day_of_week = request.booking_date.weekday()
    booking_time = request.booking_date.time()
    
    availability = db.query(ConsultantAvailability).filter(
        ConsultantAvailability.consultant_id == request.consultant_id,
        ConsultantAvailability.day_of_week == day_of_week,
        ConsultantAvailability.is_available == True,
        ConsultantAvailability.start_time <= booking_time,
        ConsultantAvailability.end_time >= booking_time
    ).first()
    
    if not availability:
        raise HTTPException(status_code=400, detail="Consultant is not available at this time")
    
    # Check if there's already a booking at this time
    existing_booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == request.consultant_id,
        ConsultantBooking.booking_date == request.booking_date,
        ConsultantBooking.status == BookingStatus.pending
    ).first()
    
    if existing_booking:
        raise HTTPException(status_code=400, detail="This time slot is already booked")
    
    # Create booking
    booking = ConsultantBooking(
        consultant_id=request.consultant_id,
        employee_id=current_user.id,
        booked_by_id=current_user.id,
        booking_date=request.booking_date,
        duration_minutes=request.duration_minutes,
        status=BookingStatus.pending,
        notes=request.notes
    )
    
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    return {
        "id": booking.id,
        "consultant_id": booking.consultant_id,
        "consultant_name": consultant.name,
        "employee_id": booking.employee_id,
        "employee_name": current_user.name or current_user.username,
        "booked_by_id": booking.booked_by_id,
        "booked_by_name": current_user.name or current_user.username,
        "booking_date": booking.booking_date,
        "duration_minutes": booking.duration_minutes,
        "status": booking.status.value,
        "notes": booking.notes,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at
    }

@router.get("/my-bookings", response_model=List[BookingResponse])
def get_my_bookings(
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Get current user's bookings"""
    bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.employee_id == current_user.id
    ).order_by(ConsultantBooking.booking_date.desc()).all()
    
    result = []
    for booking in bookings:
        consultant = db.query(Consultant).filter(Consultant.id == booking.consultant_id).first()
        booked_by = db.query(User).filter(User.id == booking.booked_by_id).first()
        
        result.append({
            "id": booking.id,
            "consultant_id": booking.consultant_id,
            "consultant_name": consultant.name if consultant else "Unknown",
            "employee_id": booking.employee_id,
            "employee_name": current_user.name or current_user.username,
            "booked_by_id": booking.booked_by_id,
            "booked_by_name": booked_by.name if booked_by else "Unknown",
            "booking_date": booking.booking_date,
            "duration_minutes": booking.duration_minutes,
            "status": booking.status.value,
            "notes": booking.notes,
            "created_at": booking.created_at,
            "updated_at": booking.updated_at
        })
    
    return result

@router.put("/bookings/{booking_id}", response_model=BookingResponse)
def update_booking(
    booking_id: int,
    request: UpdateBookingRequest,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Update a booking (employee can only update their own bookings)"""
    booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.id == booking_id,
        ConsultantBooking.employee_id == current_user.id
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check if booking is in the future
    if booking.booking_date <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Cannot update past bookings")
    
    # Update fields
    if request.consultant_id is not None:
        # Check if new consultant exists
        consultant = db.query(Consultant).filter(Consultant.id == request.consultant_id).first()
        if not consultant:
            raise HTTPException(status_code=404, detail="Consultant not found")
        booking.consultant_id = request.consultant_id
    
    if request.booking_date is not None:
        # Check if new time is in the future
        if request.booking_date <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="Booking date must be in the future")
        
        # Check if consultant is available at new time
        day_of_week = request.booking_date.weekday()
        booking_time = request.booking_date.time()
        
        availability = db.query(ConsultantAvailability).filter(
            ConsultantAvailability.consultant_id == booking.consultant_id,
            ConsultantAvailability.day_of_week == day_of_week,
            ConsultantAvailability.is_available == True,
            ConsultantAvailability.start_time <= booking_time,
            ConsultantAvailability.end_time >= booking_time
        ).first()
        
        if not availability:
            raise HTTPException(status_code=400, detail="Consultant is not available at this time")
        
        # Check if there's already a booking at this time (excluding current booking)
        existing_booking = db.query(ConsultantBooking).filter(
            ConsultantBooking.consultant_id == booking.consultant_id,
            ConsultantBooking.booking_date == request.booking_date,
            ConsultantBooking.status == BookingStatus.pending,
            ConsultantBooking.id != booking_id
        ).first()
        
        if existing_booking:
            raise HTTPException(status_code=400, detail="This time slot is already booked")
        
        booking.booking_date = request.booking_date
    
    if request.duration_minutes is not None:
        booking.duration_minutes = request.duration_minutes
    
    if request.notes is not None:
        booking.notes = request.notes
    
    booking.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(booking)
    
    # Get consultant and employee info for response
    consultant = db.query(Consultant).filter(Consultant.id == booking.consultant_id).first()
    employee = db.query(User).filter(User.id == booking.employee_id).first()
    booked_by = db.query(User).filter(User.id == booking.booked_by_id).first()
    
    return {
        "id": booking.id,
        "consultant_id": booking.consultant_id,
        "consultant_name": consultant.name if consultant else "Unknown",
        "employee_id": booking.employee_id,
        "employee_name": employee.name or employee.username if employee else "Unknown",
        "booked_by_id": booking.booked_by_id,
        "booked_by_name": booked_by.name or booked_by.username if booked_by else "Unknown",
        "booking_date": booking.booking_date,
        "duration_minutes": booking.duration_minutes,
        "status": booking.status.value,
        "notes": booking.notes,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at
    }

@router.delete("/bookings/{booking_id}")
def cancel_booking(
    booking_id: int,
    current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Cancel a booking (employee can only cancel their own bookings)"""
    booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.id == booking_id,
        ConsultantBooking.employee_id == current_user.id
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check if booking is in the future
    if booking.booking_date <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Cannot cancel past bookings")
    
    booking.status = BookingStatus.cancelled
    booking.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Booking cancelled successfully"}

# Supervisor/HR endpoints for booking on behalf of employees
@router.post("/book-for-employee", response_model=BookingResponse)
def book_for_employee(
    request: BookingRequest,
    employee_id: int,
    current_user: User = Depends(require_roles([UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Book a consultation for an employee (supervisor/HR only)"""
    # Check if employee exists
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if consultant exists
    consultant = db.query(Consultant).filter(Consultant.id == request.consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    # Check if booking time is in the future
    if request.booking_date <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Booking date must be in the future")
    
    # Check if consultant is available at that time
    day_of_week = request.booking_date.weekday()
    booking_time = request.booking_date.time()
    
    availability = db.query(ConsultantAvailability).filter(
        ConsultantAvailability.consultant_id == request.consultant_id,
        ConsultantAvailability.day_of_week == day_of_week,
        ConsultantAvailability.is_available == True,
        ConsultantAvailability.start_time <= booking_time,
        ConsultantAvailability.end_time >= booking_time
    ).first()
    
    if not availability:
        raise HTTPException(status_code=400, detail="Consultant is not available at this time")
    
    # Check if there's already a booking at this time
    existing_booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == request.consultant_id,
        ConsultantBooking.booking_date == request.booking_date,
        ConsultantBooking.status == BookingStatus.pending
    ).first()
    
    if existing_booking:
        raise HTTPException(status_code=400, detail="This time slot is already booked")
    
    # Create booking
    booking = ConsultantBooking(
        consultant_id=request.consultant_id,
        employee_id=employee_id,
        booked_by_id=current_user.id,
        booking_date=request.booking_date,
        duration_minutes=request.duration_minutes,
        status=BookingStatus.pending,
        notes=request.notes
    )
    
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    return {
        "id": booking.id,
        "consultant_id": booking.consultant_id,
        "consultant_name": consultant.name,
        "employee_id": booking.employee_id,
        "employee_name": employee.name or employee.username,
        "booked_by_id": booking.booked_by_id,
        "booked_by_name": current_user.name or current_user.username,
        "booking_date": booking.booking_date,
        "duration_minutes": booking.duration_minutes,
        "status": booking.status.value,
        "notes": booking.notes,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at
    }

@router.get("/team-bookings", response_model=List[BookingResponse])
def get_team_bookings(
    current_user: User = Depends(require_roles([UserRole.supervisor, UserRole.hr_manager])),
    db: Session = Depends(get_db)
):
    """Get bookings for team members (supervisor/HR only)"""
    if current_user.role == UserRole.supervisor:
        # Get employees supervised by current user
        team_members = db.query(User).filter(
            User.team_id == current_user.team_id,
            User.role == UserRole.employee
        ).all()
    else:  # HR manager
        # Get all employees
        team_members = db.query(User).filter(User.role == UserRole.employee).all()
    
    employee_ids = [member.id for member in team_members]
    
    bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.employee_id.in_(employee_ids)
    ).order_by(ConsultantBooking.booking_date.desc()).all()
    
    result = []
    for booking in bookings:
        consultant = db.query(Consultant).filter(Consultant.id == booking.consultant_id).first()
        employee = db.query(User).filter(User.id == booking.employee_id).first()
        booked_by = db.query(User).filter(User.id == booking.booked_by_id).first()
        
        result.append({
            "id": booking.id,
            "consultant_id": booking.consultant_id,
            "consultant_name": consultant.name if consultant else "Unknown",
            "employee_id": booking.employee_id,
            "employee_name": employee.name or employee.username if employee else "Unknown",
            "booked_by_id": booking.booked_by_id,
            "booked_by_name": booked_by.name or booked_by.username if booked_by else "Unknown",
            "booking_date": booking.booking_date,
            "duration_minutes": booking.duration_minutes,
            "status": booking.status.value,
            "notes": booking.notes,
            "created_at": booking.created_at,
            "updated_at": booking.updated_at
        })
    
    return result 