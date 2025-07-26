from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from auth import auth_router, get_password_hash
from dashboard import router as dashboard_router
from work import router as work_router
from stress import router as stress_router
from psychiatrist import router as psychiatrist_router
from admin import router as admin_router
from registration_requests import router as registration_requests_router
from tasks import router as tasks_router
from consultant import router as consultant_router
from hr_consultants import router as hr_consultants_router
from database import SessionLocal
from models import User, UserRole, Department
from dependencies import get_db
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_default_admin():
    """Create default admin user if it doesn't exist"""
    db = SessionLocal()
    try:
        # Check if admin user already exists
        admin_user = db.query(User).filter(User.username == "admin@stressmind.com").first()
        if not admin_user:
            # Create default admin user
            hashed_password = get_password_hash("admin@11540")
            admin_user = User(
                username="admin@stressmind.com",
                email="admin@stressmind.com",
                hashed_password=hashed_password,
                role=UserRole.admin
            )
            db.add(admin_user)
            db.commit()
            print("✅ Default admin user created successfully!")
            print("   Username: admin@stressmind.com")
            print("   Password: admin@11540")
        else:
            print("ℹ️  Admin user already exists")
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    """Create default admin user on startup"""
    create_default_admin()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Employee Stress Management API"}

# Public endpoint to get departments for registration
@app.get("/public/departments")
def get_public_departments(db: Session = Depends(get_db)):
    departments = db.query(Department).all()
    return [
        {
            "id": dept.id,
            "name": dept.name,
            "description": dept.description
        }
        for dept in departments
    ]

app.include_router(auth_router, prefix="/auth")
app.include_router(dashboard_router)
app.include_router(work_router)
app.include_router(stress_router)
app.include_router(psychiatrist_router)
app.include_router(admin_router)
app.include_router(registration_requests_router)
app.include_router(tasks_router)
app.include_router(consultant_router)
app.include_router(hr_consultants_router) 