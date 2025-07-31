from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models import User, UserRole, Consultant, ConsultantBooking, BookingStatus
from dependencies import require_roles, require_role, get_db
from datetime import datetime, timedelta
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/consultants", tags=["consultants"])

class BookingRequest(BaseModel):
    consultant_id: int
    booking_date: str
    duration_minutes: int = 30
    notes: str = ""

class BookingResponse(BaseModel):
    id: int
    consultant_id: int
    employee_id: int
    booking_date: datetime
    duration_minutes: int
    status: str
    notes: str = None
    created_at: datetime

@router.get("/")
def get_consultants(current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Get all consultants"""
    consultants = db.query(Consultant).all()
    return [
        {
            "id": consultant.id,
            "name": consultant.name,
            "qualifications": consultant.qualifications,
            "registration_number": consultant.registration_number,
            "hospital": consultant.hospital,
            "specialization": consultant.specialization
        }
        for consultant in consultants
    ]

@router.get("/{consultant_id}")
def get_consultant(consultant_id: int, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Get a specific consultant"""
    consultant = db.query(Consultant).filter(Consultant.id == consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    return {
        "id": consultant.id,
        "name": consultant.name,
        "qualifications": consultant.qualifications,
        "registration_number": consultant.registration_number,
        "hospital": consultant.hospital,
        "specialization": consultant.specialization
    }

@router.get("/{consultant_id}/bookings")
def get_consultant_bookings(consultant_id: int, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Get all bookings for a consultant"""
    bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == consultant_id,
        ConsultantBooking.employee_id == current_user.id
    ).all()
    
    return [
        {
            "id": booking.id,
            "consultant_id": booking.consultant_id,
            "employee_id": booking.employee_id,
            "booking_date": booking.booking_date,
            "duration_minutes": booking.duration_minutes,
            "status": booking.status.value,
            "notes": booking.notes,
            "created_at": booking.created_at
        }
        for booking in bookings
    ]

@router.post("/book")
def book_consultant(booking_data: BookingRequest, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Book a consultant appointment"""
    # Validate consultant exists
    consultant = db.query(Consultant).filter(Consultant.id == booking_data.consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    # Parse booking date - frontend now sends local time directly
    try:
        booking_datetime = datetime.fromisoformat(booking_data.booking_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Check if booking is in the past
    current_datetime = datetime.now()
    if booking_datetime <= current_datetime:
        raise HTTPException(status_code=400, detail="Cannot book sessions in the past or current time")
    
    # Check if slot is available
    existing_booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == booking_data.consultant_id,
        ConsultantBooking.booking_date == booking_datetime,
        ConsultantBooking.status.in_([BookingStatus.pending, BookingStatus.approved])
    ).first()
    
    if existing_booking:
        raise HTTPException(status_code=400, detail="This time slot is already booked")
    
    # Create booking
    booking = ConsultantBooking(
        consultant_id=booking_data.consultant_id,
        employee_id=current_user.id,
        booked_by_id=current_user.id,
        booking_date=booking_datetime,
        duration_minutes=booking_data.duration_minutes,
        status=BookingStatus.pending,
        notes=booking_data.notes
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    return {
        "message": "Booking request submitted successfully.",
        "booking_id": booking.id,
        "status": "pending"
    }

@router.get("/my-bookings")
def get_my_bookings(current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Get all bookings for the current user"""
    bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.employee_id == current_user.id
    ).all()
    
    return [
        {
            "id": booking.id,
            "consultant_id": booking.consultant_id,
            "consultant_name": booking.consultant.name,
            "booking_date": booking.booking_date,
            "duration_minutes": booking.duration_minutes,
            "status": booking.status.value,
            "notes": booking.notes,
            "created_at": booking.created_at
        }
        for booking in bookings
    ]

@router.put("/bookings/{booking_id}")
def update_consultant_booking(booking_id: int, booking_data: dict, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Update a consultant booking (only if pending)"""
    booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.id == booking_id, 
        ConsultantBooking.employee_id == current_user.id
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status != BookingStatus.pending:
        raise HTTPException(status_code=400, detail="Can only update pending bookings")
    
    if 'booking_date' in booking_data:
        booking_datetime = datetime.fromisoformat(booking_data['booking_date'])
        booking.booking_date = booking_datetime
    if 'notes' in booking_data:
        booking.notes = booking_data['notes']
    
    booking.updated_at = datetime.now()
    db.commit()
    return {"message": "Booking updated successfully"}

@router.delete("/bookings/{booking_id}")
def cancel_consultant_booking(booking_id: int, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Cancel a consultant booking (only if pending)"""
    booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.id == booking_id, 
        ConsultantBooking.employee_id == current_user.id
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status != BookingStatus.pending:
        raise HTTPException(status_code=400, detail="Can only cancel pending bookings")
    
    booking.status = BookingStatus.cancelled
    booking.updated_at = datetime.now()
    db.commit()
    return {"message": "Booking cancelled successfully"}

@router.post("/book-for-employee")
def book_consultant_for_employee(booking_data: BookingRequest, employee_id: int, current_user: User = Depends(require_roles([UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Book a consultant appointment for an employee"""
    # Validate employee exists
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Validate consultant exists
    consultant = db.query(Consultant).filter(Consultant.id == booking_data.consultant_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Consultant not found")
    
    # Parse booking date - frontend now sends local time directly
    try:
        booking_datetime = datetime.fromisoformat(booking_data.booking_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Check if slot is available
    existing_booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == booking_data.consultant_id,
        ConsultantBooking.booking_date == booking_datetime,
        ConsultantBooking.status.in_([BookingStatus.pending, BookingStatus.approved])
    ).first()
    
    if existing_booking:
        raise HTTPException(status_code=400, detail="This time slot is already booked")
    
    # Create booking
    booking = ConsultantBooking(
        consultant_id=booking_data.consultant_id,
        employee_id=employee_id,
        booked_by_id=current_user.id,
        booking_date=booking_datetime,
        duration_minutes=booking_data.duration_minutes,
        status=BookingStatus.pending,
        notes=booking_data.notes
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    return {
        "message": "Booking request submitted successfully.",
        "booking_id": booking.id,
        "status": "pending"
    } 