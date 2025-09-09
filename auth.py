from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
from database import SessionLocal
from models import User, UserRole
from dependencies import get_current_user
import os
from typing import Optional

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

auth_router = APIRouter()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Schemas
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole

class AdminCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

# Utility functions
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Admin registration endpoint
@auth_router.post("/admin/register", response_model=Token)
def register_admin(user: AdminCreate, db: Session = Depends(get_db)):
    if db.query(User).filter((User.username == user.username) | (User.email == user.email)).first():
        raise HTTPException(status_code=400, detail="Username or email already registered")
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=UserRole.admin
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    access_token = create_access_token(data={"sub": db_user.username, "role": db_user.role.value})
    return {"access_token": access_token, "token_type": "bearer", "role": db_user.role.value, "username": db_user.username}

# Registration endpoint
@auth_router.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter((User.username == user.username) | (User.email == user.email)).first():
        raise HTTPException(status_code=400, detail="Username or email already registered")
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    access_token = create_access_token(data={"sub": db_user.username, "role": db_user.role.value})
    return {"access_token": access_token, "token_type": "bearer", "role": db_user.role.value, "username": db_user.username}

# Login endpoint
@auth_router.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": db_user.username, "role": db_user.role.value})
    return {"access_token": access_token, "token_type": "bearer", "role": db_user.role.value, "username": db_user.username}

# Token refresh endpoint
@auth_router.post("/refresh", response_model=Token)
def refresh_token(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Refresh the access token with current user data from database"""
    # Get fresh user data from database
    db_user = db.query(User).filter(User.id == current_user.id).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Create new token with current role
    access_token = create_access_token(data={"sub": db_user.username, "role": db_user.role.value})
    return {"access_token": access_token, "token_type": "bearer", "role": db_user.role.value, "username": db_user.username}

# Get user name endpoint
@auth_router.get("/user/name")
def get_user_name(current_user: User = Depends(get_current_user)):
    """Get the display name of the authenticated user"""
    try:
        # Return the user's name from the database
        display_name = current_user.name if current_user.name else current_user.username
        
        return {
            "displayName": display_name
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving user name: {str(e)}"
        ) 