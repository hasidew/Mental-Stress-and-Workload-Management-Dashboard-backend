from sqlalchemy.orm import Session
from models import Notification, NotificationType, User, ConsultantBooking, UserRole, Task
from datetime import datetime

class NotificationService:
    @staticmethod
    def create_notification(db: Session, user_id: int, title: str, message: str, 
                          notification_type: NotificationType, booking_id: int = None):
        """Create a new notification"""
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            related_booking_id=booking_id
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def notify_booking_created(db: Session, booking: ConsultantBooking):
        """Notify relevant parties when a booking is created"""
        # Try to find psychiatrist user by matching consultant name with user name
        # This is a temporary solution until we have a proper consultant-user relationship
        psychiatrist_user = db.query(User).filter(
            User.name == booking.consultant.name,
            User.role == UserRole.psychiatrist
        ).first()
        
        if psychiatrist_user:
            # Notify psychiatrist about new booking request
            NotificationService.create_notification(
                db=db,
                user_id=psychiatrist_user.id,
                title="New Booking Request",
                message=f"New booking request from {booking.employee.name} for {booking.booking_date.strftime('%Y-%m-%d %H:%M')}",
                notification_type=NotificationType.booking_created,
                booking_id=booking.id
            )
        else:
            # Log that psychiatrist user not found (for debugging)
            print(f"Warning: No psychiatrist user found for consultant {booking.consultant.name}")
        
        # If booking was made by someone else (supervisor/HR), notify the employee
        if booking.employee_id != booking.booked_by_id:
            NotificationService.create_notification(
                db=db,
                user_id=booking.employee_id,
                title="Session Booked for You",
                message=f"A psychiatrist session has been booked for you on {booking.booking_date.strftime('%Y-%m-%d %H:%M')} by {booking.booked_by.name}",
                notification_type=NotificationType.booking_created,
                booking_id=booking.id
            )

    @staticmethod
    def notify_booking_approved(db: Session, booking: ConsultantBooking):
        """Notify relevant parties when a booking is approved"""
        # Notify the employee
        NotificationService.create_notification(
            db=db,
            user_id=booking.employee_id,
            title="Session Approved",
            message=f"Your psychiatrist session on {booking.booking_date.strftime('%Y-%m-%d %H:%M')} has been approved",
            notification_type=NotificationType.booking_approved,
            booking_id=booking.id
        )
        
        # If booking was made by someone else, notify the booker
        if booking.employee_id != booking.booked_by_id:
            NotificationService.create_notification(
                db=db,
                user_id=booking.booked_by_id,
                title="Session Approved",
                message=f"The session you booked for {booking.employee.name} on {booking.booking_date.strftime('%Y-%m-%d %H:%M')} has been approved",
                notification_type=NotificationType.booking_approved,
                booking_id=booking.id
            )

    @staticmethod
    def notify_booking_rejected(db: Session, booking: ConsultantBooking, rejection_reason: str):
        """Notify relevant parties when a booking is rejected"""
        # Notify the employee
        NotificationService.create_notification(
            db=db,
            user_id=booking.employee_id,
            title="Session Rejected",
            message=f"Your psychiatrist session on {booking.booking_date.strftime('%Y-%m-%d %H:%M')} has been rejected. Reason: {rejection_reason}",
            notification_type=NotificationType.booking_rejected,
            booking_id=booking.id
        )
        
        # If booking was made by someone else, notify the booker
        if booking.employee_id != booking.booked_by_id:
            NotificationService.create_notification(
                db=db,
                user_id=booking.booked_by_id,
                title="Session Rejected",
                message=f"The session you booked for {booking.employee.name} on {booking.booking_date.strftime('%Y-%m-%d %H:%M')} has been rejected. Reason: {rejection_reason}",
                notification_type=NotificationType.booking_rejected,
                booking_id=booking.id
            )

    @staticmethod
    def notify_booking_cancelled(db: Session, booking: ConsultantBooking, reason: str = "Automatically cancelled"):
        """Notify relevant parties when a booking is cancelled"""
        # Notify the employee
        NotificationService.create_notification(
            db=db,
            user_id=booking.employee_id,
            title="Session Cancelled",
            message=f"Your psychiatrist session on {booking.booking_date.strftime('%Y-%m-%d %H:%M')} has been cancelled. Reason: {reason}",
            notification_type=NotificationType.booking_cancelled,
            booking_id=booking.id
        )
        
        # If booking was made by someone else, notify the booker
        if booking.employee_id != booking.booked_by_id:
            NotificationService.create_notification(
                db=db,
                user_id=booking.booked_by_id,
                title="Session Cancelled",
                message=f"The session you booked for {booking.employee.name} on {booking.booking_date.strftime('%Y-%m-%d %H:%M')} has been cancelled. Reason: {reason}",
                notification_type=NotificationType.booking_cancelled,
                booking_id=booking.id
            )

    @staticmethod
    def notify_session_completed(db: Session, booking: ConsultantBooking):
        """Notify relevant parties when a session is completed"""
        # Notify the employee
        NotificationService.create_notification(
            db=db,
            user_id=booking.employee_id,
            title="Session Completed",
            message=f"Your psychiatrist session on {booking.booking_date.strftime('%Y-%m-%d %H:%M')} has been marked as completed",
            notification_type=NotificationType.session_completed,
            booking_id=booking.id
        )
        
        # If booking was made by someone else, notify the booker
        if booking.employee_id != booking.booked_by_id:
            NotificationService.create_notification(
                db=db,
                user_id=booking.booked_by_id,
                title="Session Completed",
                message=f"The session you booked for {booking.employee.name} on {booking.booking_date.strftime('%Y-%m-%d %H:%M')} has been marked as completed",
                notification_type=NotificationType.session_completed,
                booking_id=booking.id
            )

    @staticmethod
    def notify_task_assigned(db: Session, task: Task):
        """Notify employee when a task is assigned"""
        NotificationService.create_notification(
            db=db,
            user_id=task.employee_id,
            title="New Task Assigned",
            message=f"You have been assigned a new task: {task.title}",
            notification_type=NotificationType.task_assigned
        )

    @staticmethod
    def notify_task_completed(db: Session, task: Task):
        """Notify supervisor when a task is completed"""
        if task.assigned_by_id:
            NotificationService.create_notification(
                db=db,
                user_id=task.assigned_by_id,
                title="Task Completed",
                message=f"Task '{task.title}' has been completed by {task.employee.name}",
                notification_type=NotificationType.task_completed
            )

    @staticmethod
    def notify_task_overdue(db: Session, task: Task):
        """Notify employee when a task is overdue"""
        NotificationService.create_notification(
            db=db,
            user_id=task.employee_id,
            title="Task Overdue",
            message=f"Your task '{task.title}' is overdue. Please complete it as soon as possible.",
            notification_type=NotificationType.task_overdue
        )

    @staticmethod
    def notify_stress_score_updated(db: Session, user_id: int, score: int):
        """Notify when a stress score is updated"""
        NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title="Stress Score Updated",
            message=f"Your stress score has been updated to {score}",
            notification_type=NotificationType.stress_score_updated
        )

    @staticmethod
    def notify_stress_score_high(db: Session, user_id: int, score: int, supervisor_id: int = None):
        """Notify when a stress score is high (above threshold)"""
        # Notify the employee
        NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title="High Stress Level Detected",
            message=f"Your stress score is {score}, which indicates high stress. Consider booking a session with a psychiatrist.",
            notification_type=NotificationType.stress_score_high
        )
        
        # Notify supervisor if available
        if supervisor_id:
            NotificationService.create_notification(
                db=db,
                user_id=supervisor_id,
                title="Team Member High Stress",
                message=f"A team member has a high stress score of {score}. Please check on their well-being.",
                notification_type=NotificationType.stress_score_high
            ) 