from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models import User, Notification, NotificationType, UserRole
from dependencies import require_roles, require_role, get_db
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/notifications", tags=["notifications"])

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    related_booking_id: int = None
    created_at: str

@router.get("/my-notifications")
def get_my_notifications(current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager, UserRole.psychiatrist, UserRole.admin])), db: Session = Depends(get_db)):
    """Get current user's notifications"""
    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    return [
        {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "notification_type": notification.notification_type.value,
            "is_read": notification.is_read,
            "related_booking_id": notification.related_booking_id,
            "created_at": notification.created_at.isoformat()
        }
        for notification in notifications
    ]

@router.get("/my-unread-count")
def get_unread_count(current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager, UserRole.psychiatrist, UserRole.admin])), db: Session = Depends(get_db)):
    """Get count of unread notifications for current user"""
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    
    return {"unread_count": count}

@router.put("/{notification_id}/mark-read")
def mark_notification_read(notification_id: int, current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager, UserRole.psychiatrist, UserRole.admin])), db: Session = Depends(get_db)):
    """Mark a notification as read"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    db.commit()
    
    return {"message": "Notification marked as read"}

@router.put("/mark-all-read")
def mark_all_notifications_read(current_user: User = Depends(require_roles([UserRole.employee, UserRole.supervisor, UserRole.hr_manager, UserRole.psychiatrist, UserRole.admin])), db: Session = Depends(get_db)):
    """Mark all notifications as read for current user"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    
    db.commit()
    
    return {"message": "All notifications marked as read"} 