from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dependencies import get_db, require_role
from models import User, UserRole
from pydantic import BaseModel

router = APIRouter(prefix="/psychiatrist", tags=["psychiatrist"])

class ConsultationRequest(BaseModel):
    employee_id: int
    message: str

# In a real app, this would create a record or send a notification. Here, just a placeholder.
@router.post("/contact")
def contact_psychiatrist(current_user: User = Depends(require_role(UserRole.employee)), db: Session = Depends(get_db)):
    psychiatrists = db.query(User).filter(User.role == UserRole.psychiatrist).all()
    if not psychiatrists:
        raise HTTPException(status_code=404, detail="No psychiatrists available")
    # In a real app, you might create a ContactRequest model here
    return {"message": "Psychiatrist contact request sent", "psychiatrists": [p.username for p in psychiatrists]}

# Psychiatrist initiates consultation with an employee
@router.post("/consult")
def initiate_consultation(request: ConsultationRequest, current_user: User = Depends(require_role(UserRole.psychiatrist)), db: Session = Depends(get_db)):
    employee = db.query(User).filter(User.id == request.employee_id, User.role == UserRole.employee).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    # In a real app, you would create a Consultation model or send a notification
    return {"message": f"Consultation initiated with {employee.username}", "employee_id": employee.id, "note": request.message} 