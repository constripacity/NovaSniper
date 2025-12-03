"""
NovaSniper v2.0 Authentication Utilities
JWT tokens and API key authentication
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional, Union

from fastapi import Depends, HTTPException, status, Security
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import TokenData

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def generate_api_key() -> str:
    """Generate a random API key"""
    return secrets.token_urlsafe(48)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT access token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: int = payload.get("sub")
        email: str = payload.get("email")
        
        if user_id is None:
            return None
        
        return TokenData(user_id=user_id, email=email)
        
    except JWTError:
        return None


def get_user_by_api_key(db: Session, api_key: str) -> Optional[User]:
    """Get user by API key"""
    return db.query(User).filter(User.api_key == api_key, User.is_active == True).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password"""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(
    db: Session = Depends(get_db),
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> Optional[User]:
    """
    Get current user from API key or JWT token
    Returns None for anonymous access (optional auth)
    """
    # Try API key first
    if api_key:
        user = get_user_by_api_key(db, api_key)
        if user:
            return user
    
    # Try JWT token
    if bearer:
        token_data = decode_access_token(bearer.credentials)
        if token_data and token_data.user_id:
            user = get_user_by_id(db, token_data.user_id)
            if user and user.is_active:
                return user
    
    return None


async def get_current_user_required(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """
    Require authenticated user
    Raises 401 if not authenticated
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_admin_user(
    user: User = Depends(get_current_user_required),
) -> User:
    """
    Require admin user
    Raises 403 if not admin
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def create_user(
    db: Session,
    email: str,
    password: Optional[str] = None,
    username: Optional[str] = None,
    is_admin: bool = False,
) -> User:
    """Create a new user"""
    user = User(
        email=email,
        username=username,
        hashed_password=get_password_hash(password) if password else None,
        api_key=generate_api_key(),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def regenerate_api_key(db: Session, user: User) -> str:
    """Regenerate user's API key"""
    user.api_key = generate_api_key()
    db.commit()
    return user.api_key
