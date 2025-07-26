from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User, UserRole
import os

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        print(f"JWT payload: {payload}")
        print(f"Username from token: {username}")
        if not isinstance(username, str) or username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    print(f"User from database: {user.username if user else 'None'}, Role: {user.role.value if user else 'None'}")
    if user is None:
        raise credentials_exception
    return user

def require_role(role: UserRole):
    def role_checker(user: User = Depends(get_current_user)):
        print(f"Role check: User role = {user.role.value}, Required role = {role.value}")
        if user.role.value != role.value:
            print(f"Role mismatch: User has {user.role.value}, but {role.value} is required")
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        print(f"Role check passed: User has {user.role.value}")
        return user
    return role_checker

def require_roles(roles: list[UserRole]):
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker 