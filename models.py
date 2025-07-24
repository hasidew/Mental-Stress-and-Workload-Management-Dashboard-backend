from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Text, Boolean, Time
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime

class UserRole(enum.Enum):
    admin = "admin"
    employee = "employee"
    supervisor = "supervisor"
    psychiatrist = "psychiatrist"
    hr_manager = "hr_manager"
    consultant = "consultant"

class RequestStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class TaskStatus(enum.Enum):
    pending = "pending"
    completed = "completed"

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.pending)
    priority = Column(String(20), default="medium")  # low, medium, high
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Who assigned the task (can be self or supervisor/HR)
    
    employee = relationship("User", foreign_keys=[employee_id], back_populates="tasks")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])

class UserRegistrationRequest(Base):
    __tablename__ = "user_registration_requests"
    id = Column(Integer, primary_key=True, index=True)
    
    # Personal Information
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    gender = Column(String(10), nullable=False)  # 'male', 'female', 'other'
    nic = Column(String(20), nullable=False)
    birthday = Column(DateTime, nullable=False)
    contact = Column(String(20), nullable=True)
    
    # Job Information
    job_role = Column(String(50), nullable=False)
    employee_id = Column(String(50), nullable=True, unique=True)
    department = Column(String(100), nullable=True)
    team = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)
    supervisor_name = Column(String(100), nullable=True)
    
    # Consultant specific fields
    registration_number = Column(String(50), nullable=True, unique=True)
    hospital = Column(String(100), nullable=True)
    
    # Account Information
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password = Column(String(128), nullable=False)  # Hashed password
    
    # Request Status
    status = Column(Enum(RequestStatus), default=RequestStatus.pending)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Relationships
    reviewer = relationship("User", foreign_keys=[reviewed_by])

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)
    
    # Relationships
    teams = relationship("Team", back_populates="department")
    employees = relationship("User", back_populates="department")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    supervisor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False)
    
    # Relationships
    department = relationship("Department", back_populates="teams")
    supervisor = relationship("User", foreign_keys=[supervisor_id])
    employees = relationship("User", foreign_keys="User.team_id")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(128), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    
    # New fields for employee details
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    sex = Column(String(10), nullable=True)  # 'male', 'female', 'other'
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)

    # Relationships
    department = relationship("Department", back_populates="employees")
    team = relationship("Team", foreign_keys=[team_id])
    stress_scores = relationship("StressScore", back_populates="employee")
    daily_workloads = relationship("DailyWorkload", back_populates="employee")
    assigned_works = relationship("WorkAssignment", back_populates="employee", foreign_keys='WorkAssignment.employee_id')
    supervisor_works = relationship("WorkAssignment", back_populates="supervisor", foreign_keys='WorkAssignment.supervisor_id')
    tasks = relationship("Task", back_populates="employee", foreign_keys="Task.employee_id")

class StressScore(Base):
    __tablename__ = "stress_scores"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Integer, nullable=False)
    level = Column(String(20), nullable=False)  # low, medium, high
    share_with_supervisor = Column(Boolean, default=False)
    share_with_hr = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = relationship("User", back_populates="stress_scores")

class DailyWorkload(Base):
    __tablename__ = "daily_workloads"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text, nullable=False)
    date = Column(DateTime, nullable=False)
    employee_id = Column(Integer, ForeignKey("users.id"))
    employee = relationship("User", back_populates="daily_workloads")

class WorkAssignment(Base):
    __tablename__ = "work_assignments"
    id = Column(Integer, primary_key=True, index=True)
    work_description = Column(Text, nullable=False)
    assigned_at = Column(DateTime, nullable=False)
    employee_id = Column(Integer, ForeignKey("users.id"))
    supervisor_id = Column(Integer, ForeignKey("users.id"))
    employee = relationship("User", back_populates="assigned_works", foreign_keys=[employee_id])
    supervisor = relationship("User", back_populates="supervisor_works", foreign_keys=[supervisor_id])

class Consultant(Base):
    __tablename__ = "consultants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    qualifications = Column(Text, nullable=False)
    registration_number = Column(String(50), unique=True, nullable=False)
    hospital = Column(String(100), nullable=False)
    specialization = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False)
    
    # Relationships
    availabilities = relationship("ConsultantAvailability", back_populates="consultant", cascade="all, delete-orphan")

class ConsultantAvailability(Base):
    __tablename__ = "consultant_availabilities"
    id = Column(Integer, primary_key=True, index=True)
    consultant_id = Column(Integer, ForeignKey("consultants.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_available = Column(Boolean, default=True)
    
    # Relationships
    consultant = relationship("Consultant", back_populates="availabilities")

class BookingStatus(enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"

class ConsultantBooking(Base):
    __tablename__ = "consultant_bookings"
    id = Column(Integer, primary_key=True, index=True)
    consultant_id = Column(Integer, ForeignKey("consultants.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    booked_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Who made the booking (employee, supervisor, HR)
    booking_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=60)
    status = Column(Enum(BookingStatus), default=BookingStatus.scheduled)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    consultant = relationship("Consultant", foreign_keys=[consultant_id])
    employee = relationship("User", foreign_keys=[employee_id])
    booked_by = relationship("User", foreign_keys=[booked_by_id]) 