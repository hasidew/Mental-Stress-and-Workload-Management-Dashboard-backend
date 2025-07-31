from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import User, UserRole, Consultant, ConsultantBooking, BookingStatus
from dependencies import require_roles, require_role, get_db
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from notification_service import NotificationService

router = APIRouter(prefix="/psychiatrist", tags=["psychiatrist"])

class ConsultationRequest(BaseModel):
    employee_id: int
    message: str

class BookingRequest(BaseModel):
    psychiatrist_id: int
    booking_date: str  # ISO format datetime
    notes: Optional[str] = None

class ApprovalRequest(BaseModel):
    status: str  # "approved" or "rejected"
    rejection_reason: Optional[str] = None

# Get available psychiatrists with their weekly schedule
@router.get("/available")
def get_available_psychiatrists(current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Get all available psychiatrists with their weekly schedule"""
    consultants = db.query(Consultant).all()
    
    result = []
    for consultant in consultants:
        from models import ConsultantAvailability
        availabilities = db.query(ConsultantAvailability).filter(
            ConsultantAvailability.consultant_id == consultant.id,
            ConsultantAvailability.is_available == True
        ).all()
        
        # Get existing bookings for this consultant
        existing_bookings = db.query(ConsultantBooking).filter(
            ConsultantBooking.consultant_id == consultant.id,
            ConsultantBooking.status.in_([BookingStatus.pending, BookingStatus.approved])
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
        
        # Get bookings for the next 7 days
        today = datetime.now().date()
        bookings_data = []
        for booking in existing_bookings:
            if booking.booking_date.date() >= today:
                bookings_data.append({
                    "id": booking.id,
                    "booking_date": booking.booking_date.isoformat(),
                    "duration_minutes": booking.duration_minutes,
                    "status": booking.status.value,
                    "employee_name": booking.employee.name if booking.employee else "Unknown",
                    "notes": booking.notes
                })
        
        result.append({
            "id": consultant.id,
            "name": consultant.name,
            "qualifications": consultant.qualifications,
            "registration_number": consultant.registration_number,
            "hospital": consultant.hospital,
            "specialization": consultant.specialization,
            "availabilities": availability_data,
            "bookings": bookings_data
        })
    
    return result

# Get psychiatrist timetable for a specific date
@router.get("/{psychiatrist_id}/timetable")
def get_psychiatrist_timetable(psychiatrist_id: int, date: str, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Get psychiatrist's timetable for a specific date with 30-minute slots"""
    consultant = db.query(Consultant).filter(Consultant.id == psychiatrist_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist not found")
    
    # Parse the date
    try:
        target_date = datetime.fromisoformat(date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Get day of week (0=Monday, 1=Tuesday, etc.)
    day_of_week = target_date.weekday()
    
    # Get availability for this day
    from models import ConsultantAvailability
    availability = db.query(ConsultantAvailability).filter(
        ConsultantAvailability.consultant_id == psychiatrist_id,
        ConsultantAvailability.day_of_week == day_of_week,
        ConsultantAvailability.is_available == True
    ).first()
    
    # Get all bookings for this psychiatrist on this date
    all_bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == psychiatrist_id,
        ConsultantBooking.booking_date >= datetime.combine(target_date, datetime.min.time()),
        ConsultantBooking.booking_date < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
        ConsultantBooking.status.in_([BookingStatus.pending, BookingStatus.approved, BookingStatus.completed])
    ).all()
    
    print(f"Found {len(all_bookings)} bookings for date {target_date}")
    
    # Create a set of booked times for quick lookup
    booked_times = set()
    for booking in all_bookings:
        # Use the stored time directly since we're storing in local time
        booking_time = booking.booking_date.time()
        booked_times.add(booking_time)
        print(f"Found booking at {booking_time}: status={booking.status.value}, employee={booking.employee.name if booking.employee else 'Unknown'}")
    
    # Generate slots based on availability window
    slots = []
    if availability:
        start_time = availability.start_time
        end_time = availability.end_time
        
        current_time = start_time
        while current_time < end_time:
            slot_end = (datetime.combine(datetime.min, current_time) + timedelta(minutes=30)).time()
            if slot_end > end_time:
                break
                
            slot_start_datetime = datetime.combine(target_date, current_time)
            
            # Check if this slot is already booked by comparing the time component
            existing_booking = db.query(ConsultantBooking).filter(
                ConsultantBooking.consultant_id == psychiatrist_id,
                func.time(ConsultantBooking.booking_date) == current_time,
                ConsultantBooking.status.in_([BookingStatus.pending, BookingStatus.approved, BookingStatus.completed])
            ).first()
            
            print(f"Slot {current_time.strftime('%H:%M')}: available={existing_booking is None}")
            
            slots.append({
                "start_time": current_time.strftime('%H:%M'),
                "end_time": slot_end.strftime('%H:%M'),
                "available": existing_booking is None,
                "booking_id": existing_booking.id if existing_booking else None,
                "status": existing_booking.status.value if existing_booking else None,
                "employee_name": existing_booking.employee.name if existing_booking and existing_booking.employee else None
            })
            
            current_time = slot_end
    
    # Add slots for any bookings outside the availability window
    for booking in all_bookings:
        booking_time = booking.booking_date.time()
        booking_end_time = (datetime.combine(datetime.min, booking_time) + timedelta(minutes=30)).time()
        
        # Check if this booking time is already covered by availability window slots
        booking_time_str = booking_time.strftime('%H:%M')
        booking_end_time_str = booking_end_time.strftime('%H:%M')
        
        existing_slot = next((slot for slot in slots if slot["start_time"] == booking_time_str), None)
        
        if not existing_slot:
            # Add slot for booking outside availability window
            slots.append({
                "start_time": booking_time_str,
                "end_time": booking_end_time_str,
                "available": False,
                "booking_id": booking.id,
                "status": booking.status.value,
                "employee_name": booking.employee.name if booking.employee else None
            })
            print(f"Added slot for booking outside availability window: {booking_time_str} - {booking_end_time_str}")
    
    # Sort slots by start time (convert to datetime for proper time sorting)
    slots.sort(key=lambda x: datetime.strptime(x["start_time"], "%H:%M"))
    
    return {
        "psychiatrist_id": psychiatrist_id,
        "date": date,
        "available": len(slots) > 0,
        "slots": slots
    }

# Book psychiatrist session
@router.post("/book")
def book_psychiatrist(booking_data: BookingRequest, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Book a psychiatrist appointment (30-minute session)"""
    # Validate psychiatrist exists
    consultant = db.query(Consultant).filter(Consultant.id == booking_data.psychiatrist_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist not found")
    
    # Parse booking date - frontend now sends local time directly
    try:
        # Parse the local datetime string directly
        booking_datetime = datetime.fromisoformat(booking_data.booking_date)
        print(f"Frontend sent (local time): {booking_data.booking_date}")
        print(f"Parsed as local: {booking_datetime}")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Check if booking is in the past
    current_datetime = datetime.now()
    if booking_datetime <= current_datetime:
        raise HTTPException(status_code=400, detail="Cannot book sessions in the past or current time")
    
    # Check if slot is available
    existing_booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == booking_data.psychiatrist_id,
        ConsultantBooking.booking_date == booking_datetime,
        ConsultantBooking.status.in_([BookingStatus.pending, BookingStatus.approved])
    ).first()
    
    if existing_booking:
        raise HTTPException(status_code=400, detail="This time slot is already booked")
    
    # Create booking
    booking = ConsultantBooking(
        consultant_id=booking_data.psychiatrist_id,
        employee_id=current_user.id,
        booked_by_id=current_user.id,
        booking_date=booking_datetime,
        duration_minutes=30,
        status=BookingStatus.pending,
        notes=booking_data.notes
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    # Send notifications
    try:
        NotificationService.notify_booking_created(db, booking)
    except Exception as e:
        print(f"Error sending notification: {e}")
    
    return {
        "message": "Booking request submitted successfully. Waiting for psychiatrist approval.",
        "booking_id": booking.id,
        "status": "pending"
    }

# Get my psychiatrist bookings
@router.get("/my-bookings")
def get_my_psychiatrist_bookings(current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Get current user's psychiatrist bookings"""
    bookings = db.query(ConsultantBooking).filter(ConsultantBooking.employee_id == current_user.id).all()
    
    return [
        {
            "id": booking.id,
            "psychiatrist_name": booking.consultant.name if booking.consultant else "Unknown",
            "booking_date": booking.booking_date.isoformat(),
            "status": booking.status.value,
            "duration_minutes": booking.duration_minutes,
            "notes": booking.notes,
            "rejection_reason": booking.rejection_reason
        } for booking in bookings
    ]

# Psychiatrist endpoints for managing bookings
@router.get("/my-pending-bookings")
def get_my_pending_bookings(current_user: User = Depends(require_role(UserRole.psychiatrist)), db: Session = Depends(get_db)):
    """Get pending bookings for the current psychiatrist"""
    bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == current_user.id,
        ConsultantBooking.status == BookingStatus.pending
    ).all()
    
    return [
        {
            "id": booking.id,
            "employee_name": booking.employee.name if booking.employee else "Unknown",
            "booking_date": booking.booking_date.isoformat(),
            "duration_minutes": booking.duration_minutes,
            "notes": booking.notes,
            "booked_by": booking.booked_by.name if booking.booked_by else "Unknown"
        } for booking in bookings
    ]

# Psychiatrist dashboard endpoints
@router.get("/dashboard")
def psychiatrist_dashboard(current_user: User = Depends(require_role(UserRole.psychiatrist)), db: Session = Depends(get_db)):
    """Get psychiatrist dashboard with sessions and pending requests"""
    # Get psychiatrist's consultant record
    consultant = db.query(Consultant).filter(Consultant.name == current_user.name).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist profile not found")
    
    # Get all bookings for this psychiatrist
    all_bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == consultant.id
    ).order_by(ConsultantBooking.booking_date).all()
    
    # Separate bookings by status
    pending_bookings = [b for b in all_bookings if b.status == BookingStatus.pending]
    approved_bookings = [b for b in all_bookings if b.status == BookingStatus.approved]
    completed_bookings = [b for b in all_bookings if b.status == BookingStatus.completed]
    
    # Get today's date
    today = datetime.now().date()
    
    # Get upcoming sessions (approved bookings from today onwards)
    upcoming_sessions = [
        b for b in approved_bookings 
        if b.booking_date.date() >= today
    ]
    
    # Get today's sessions
    today_sessions = [
        b for b in approved_bookings 
        if b.booking_date.date() == today
    ]
    
    return {
        "psychiatrist_id": consultant.id,
        "name": consultant.name,
        "specialization": consultant.specialization,
        "stats": {
            "pending_requests": len(pending_bookings),
            "upcoming_sessions": len(upcoming_sessions),
            "today_sessions": len(today_sessions),
            "total_bookings": len(all_bookings)
        },
        "pending_requests": [
            {
                "id": booking.id,
                "employee_name": booking.employee.name if booking.employee else "Unknown",
                "booked_by_name": booking.booked_by.name if booking.booked_by else "Unknown",
                "booking_date": booking.booking_date.isoformat(),
                "duration_minutes": booking.duration_minutes,
                "notes": booking.notes,
                "created_at": booking.created_at.isoformat()
            } for booking in pending_bookings
        ],
        "upcoming_sessions": [
            {
                "id": booking.id,
                "employee_name": booking.employee.name if booking.employee else "Unknown",
                "booking_date": booking.booking_date.isoformat(),
                "duration_minutes": booking.duration_minutes,
                "notes": booking.notes
            } for booking in upcoming_sessions
        ],
        "today_sessions": [
            {
                "id": booking.id,
                "employee_name": booking.employee.name if booking.employee else "Unknown",
                "booking_date": booking.booking_date.isoformat(),
                "duration_minutes": booking.duration_minutes,
                "notes": booking.notes
            } for booking in today_sessions
        ]
    }

@router.get("/my-sessions")
def get_my_sessions(current_user: User = Depends(require_role(UserRole.psychiatrist)), db: Session = Depends(get_db)):
    """Get all sessions for the current psychiatrist"""
    # Get psychiatrist's consultant record
    consultant = db.query(Consultant).filter(Consultant.name == current_user.name).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist profile not found")
    
    # Get all bookings for this psychiatrist
    bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == consultant.id
    ).order_by(ConsultantBooking.booking_date).all()
    
    return [
        {
            "id": booking.id,
            "employee_name": booking.employee.name if booking.employee else "Unknown",
            "booked_by_name": booking.booked_by.name if booking.booked_by else "Unknown",
            "booking_date": booking.booking_date.isoformat(),
            "status": booking.status.value,
            "duration_minutes": booking.duration_minutes,
            "notes": booking.notes,
            "rejection_reason": booking.rejection_reason,
            "created_at": booking.created_at.isoformat()
        } for booking in bookings
    ]

@router.get("/pending-requests")
def get_pending_requests(current_user: User = Depends(require_role(UserRole.psychiatrist)), db: Session = Depends(get_db)):
    """Get all pending requests for the current psychiatrist"""
    # Get psychiatrist's consultant record
    consultant = db.query(Consultant).filter(Consultant.name == current_user.name).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist profile not found")
    
    # Get pending bookings
    pending_bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == consultant.id,
        ConsultantBooking.status == BookingStatus.pending
    ).order_by(ConsultantBooking.booking_date).all()
    
    # Group by time slot to show conflicts
    time_slots = {}
    for booking in pending_bookings:
        slot_key = booking.booking_date.strftime('%Y-%m-%d %H:%M')
        if slot_key not in time_slots:
            time_slots[slot_key] = []
        time_slots[slot_key].append(booking)
    
    return {
        "total_pending": len(pending_bookings),
        "time_slots": [
            {
                "time_slot": slot_key,
                "booking_date": slot_bookings[0].booking_date.isoformat(),
                "requests": [
                    {
                        "id": booking.id,
                        "employee_name": booking.employee.name if booking.employee else "Unknown",
                        "booked_by_name": booking.booked_by.name if booking.booked_by else "Unknown",
                        "notes": booking.notes,
                        "created_at": booking.created_at.isoformat()
                    } for booking in slot_bookings
                ],
                "conflict_count": len(slot_bookings)
            } for slot_key, slot_bookings in time_slots.items()
        ]
    }

# Enhanced approval endpoint with conflict resolution
@router.put("/bookings/{booking_id}/approve")
def approve_booking_with_conflict_resolution(booking_id: int, request: ApprovalRequest, current_user: User = Depends(require_role(UserRole.psychiatrist)), db: Session = Depends(get_db)):
    """Approve or reject a booking request with automatic conflict resolution"""
    # Get psychiatrist's consultant record
    consultant = db.query(Consultant).filter(Consultant.name == current_user.name).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist profile not found")
    
    booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.id == booking_id,
        ConsultantBooking.consultant_id == consultant.id
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status != BookingStatus.pending:
        raise HTTPException(status_code=400, detail="Booking is not pending approval")
    
    cancelled_count = 0
    
    if request.status == "approved":
        # Get all other pending bookings for the same time slot
        conflicting_bookings = db.query(ConsultantBooking).filter(
            ConsultantBooking.consultant_id == consultant.id,
            ConsultantBooking.booking_date == booking.booking_date,
            ConsultantBooking.status == BookingStatus.pending,
            ConsultantBooking.id != booking_id
        ).all()
        
        # Cancel all conflicting bookings
        for conflicting_booking in conflicting_bookings:
            conflicting_booking.status = BookingStatus.cancelled
            conflicting_booking.rejection_reason = f"Automatically cancelled - another request was approved for this time slot"
            cancelled_count += 1
            
            # Send cancellation notifications
            try:
                NotificationService.notify_booking_cancelled(db, conflicting_booking, "Automatically cancelled - another request was approved for this time slot")
            except Exception as e:
                print(f"Error sending cancellation notification: {e}")
        
        # Approve the selected booking
        booking.status = BookingStatus.approved
        message = f"Booking approved successfully. {cancelled_count} conflicting requests were automatically cancelled."
        
        # Send approval notification
        try:
            NotificationService.notify_booking_approved(db, booking)
        except Exception as e:
            print(f"Error sending approval notification: {e}")
        
    elif request.status == "rejected":
        if not request.rejection_reason:
            raise HTTPException(status_code=400, detail="Rejection reason is required")
        
        booking.status = BookingStatus.rejected
        booking.rejection_reason = request.rejection_reason
        message = "Booking rejected"
        
        # Send rejection notification
        try:
            NotificationService.notify_booking_rejected(db, booking, request.rejection_reason)
        except Exception as e:
            print(f"Error sending rejection notification: {e}")
    else:
        raise HTTPException(status_code=400, detail="Invalid status. Use 'approved' or 'rejected'")
    
    db.commit()
    
    return {
        "message": message, 
        "booking_id": booking.id, 
        "status": booking.status.value,
        "cancelled_conflicts": cancelled_count if request.status == "approved" else 0
    }

# Update psychiatrist booking
@router.put("/bookings/{booking_id}")
def update_psychiatrist_booking(booking_id: int, booking_data: dict, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Update a psychiatrist booking (only if pending)"""
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
    
    db.commit()
    return {"message": "Booking updated successfully"}

# Cancel psychiatrist booking
@router.delete("/bookings/{booking_id}")
def cancel_psychiatrist_booking(booking_id: int, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Cancel a psychiatrist booking"""
    booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.id == booking_id, 
        ConsultantBooking.employee_id == current_user.id
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status == BookingStatus.completed:
        raise HTTPException(status_code=400, detail="Cannot cancel completed booking")
    
    booking.status = BookingStatus.cancelled
    db.commit()
    
    return {"message": "Booking cancelled successfully"}

# Complete a session
@router.put("/bookings/{booking_id}/complete")
def complete_session(booking_id: int, current_user: User = Depends(require_role(UserRole.psychiatrist)), db: Session = Depends(get_db)):
    """Mark a session as completed"""
    # Get psychiatrist's consultant record
    consultant = db.query(Consultant).filter(Consultant.name == current_user.name).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist profile not found")
    
    booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.id == booking_id,
        ConsultantBooking.consultant_id == consultant.id
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status != BookingStatus.approved:
        raise HTTPException(status_code=400, detail="Can only complete approved sessions")
    
    booking.status = BookingStatus.completed
    db.commit()
    
    # Send completion notification
    try:
        NotificationService.notify_session_completed(db, booking)
    except Exception as e:
        print(f"Error sending completion notification: {e}")
    
    return {"message": "Session marked as completed", "booking_id": booking.id}

# Book psychiatrist for employee (HR/Supervisor)
@router.post("/book-for-employee")
def book_psychiatrist_for_employee(booking_data: BookingRequest, employee_id: int, current_user: User = Depends(require_roles([UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Book a psychiatrist appointment for an employee"""
    # Validate employee exists
    employee = db.query(User).filter(User.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Validate psychiatrist exists
    consultant = db.query(Consultant).filter(Consultant.id == booking_data.psychiatrist_id).first()
    if not consultant:
        raise HTTPException(status_code=404, detail="Psychiatrist not found")
    
    # Parse booking date - frontend now sends local time directly
    try:
        booking_datetime = datetime.fromisoformat(booking_data.booking_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Check if slot is available
    existing_booking = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == booking_data.psychiatrist_id,
        ConsultantBooking.booking_date == booking_datetime,
        ConsultantBooking.status.in_([BookingStatus.pending, BookingStatus.approved])
    ).first()
    
    if existing_booking:
        raise HTTPException(status_code=400, detail="This time slot is already booked")
    
    # Create booking
    booking = ConsultantBooking(
        consultant_id=booking_data.psychiatrist_id,
        employee_id=employee_id,
        booked_by_id=current_user.id,
        booking_date=booking_datetime,
        duration_minutes=30,
        status=BookingStatus.pending,
        notes=booking_data.notes
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    # Send notifications
    try:
        NotificationService.notify_booking_created(db, booking)
    except Exception as e:
        print(f"Error sending notification: {e}")
    
    return {
        "message": "Booking request submitted successfully. Waiting for psychiatrist approval.",
        "booking_id": booking.id,
        "status": "pending"
    }

# Get team psychiatrist bookings (for supervisors)
@router.get("/team-bookings")
def get_team_psychiatrist_bookings(current_user: User = Depends(require_roles([UserRole.supervisor, UserRole.hr_manager])), db: Session = Depends(get_db)):
    """Get psychiatrist bookings for team members"""
    if current_user.role == UserRole.supervisor:
        # Get bookings for team members
        team_members = db.query(User).filter(User.team_id == current_user.team_id).all()
        team_member_ids = [member.id for member in team_members]
        
        bookings = db.query(ConsultantBooking).filter(
            ConsultantBooking.employee_id.in_(team_member_ids)
        ).all()
    else:
        # HR managers can see all bookings
        bookings = db.query(ConsultantBooking).all()
    
    return [
        {
            "id": booking.id,
            "employee_name": booking.employee.name if booking.employee else "Unknown",
            "psychiatrist_name": booking.consultant.name if booking.consultant else "Unknown",
            "booking_date": booking.booking_date.isoformat(),
            "status": booking.status.value,
            "duration_minutes": booking.duration_minutes,
            "notes": booking.notes,
            "booked_by": booking.booked_by.name if booking.booked_by else "Unknown"
        } for booking in bookings
    ]

# Contact psychiatrist
@router.post("/contact")
def contact_psychiatrist(current_user: User = Depends(require_role(UserRole.employee)), db: Session = Depends(get_db)):
    """Contact a psychiatrist (placeholder for future implementation)"""
    return {"message": "Contact feature coming soon"}

# Initiate consultation
@router.post("/consult")
def initiate_consultation(request: ConsultationRequest, current_user: User = Depends(require_role(UserRole.psychiatrist)), db: Session = Depends(get_db)):
    """Initiate a consultation (placeholder for future implementation)"""
    return {"message": "Consultation initiated"} 

# Debug endpoint to check bookings
@router.get("/debug/bookings/{psychiatrist_id}")
def debug_psychiatrist_bookings(psychiatrist_id: int, db: Session = Depends(get_db)):
    """Debug endpoint to check all bookings for a psychiatrist"""
    from models import ConsultantBooking, BookingStatus
    
    bookings = db.query(ConsultantBooking).filter(
        ConsultantBooking.consultant_id == psychiatrist_id
    ).all()
    
    return [
        {
            "id": booking.id,
            "booking_date": booking.booking_date.isoformat(),
            "status": booking.status.value,
            "employee_name": booking.employee.name if booking.employee else "Unknown",
            "notes": booking.notes
        } for booking in bookings
    ] 