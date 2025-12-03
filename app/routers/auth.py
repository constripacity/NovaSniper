"""
NovaSniper v2.0 Authentication Router
User registration, login, and API key management
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import (
    UserCreate, UserUpdate, UserResponse, UserWithStats,
    Token, LoginRequest, APIKeyResponse
)
from app.utils.auth import (
    get_current_user, get_current_user_required,
    authenticate_user, create_user, create_access_token,
    regenerate_api_key, get_user_by_email, get_password_hash
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Register a new user account
    """
    # Check if email already exists
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = create_user(
        db=db,
        email=user_in.email,
        password=user_in.password,
        username=user_in.username,
    )
    
    return user


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Login and get JWT access token
    """
    user = authenticate_user(db, login_data.email, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email},
        expires_delta=access_token_expires,
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserWithStats)
async def get_current_user_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Get current user info with stats
    """
    from app.models import TrackedProduct, Watchlist, Alert, AlertStatus
    
    # Get counts
    tracked_count = db.query(TrackedProduct).filter(
        TrackedProduct.user_id == current_user.id
    ).count()
    
    active_alerts = db.query(TrackedProduct).filter(
        TrackedProduct.user_id == current_user.id,
        TrackedProduct.alert_status == AlertStatus.PENDING,
    ).count()
    
    watchlists_count = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id
    ).count()
    
    return UserWithStats(
        **{
            "id": current_user.id,
            "email": current_user.email,
            "username": current_user.username,
            "timezone": current_user.timezone,
            "is_active": current_user.is_active,
            "is_admin": current_user.is_admin,
            "api_key": current_user.api_key,
            "created_at": current_user.created_at,
            "last_login": current_user.last_login,
        },
        tracked_products_count=tracked_count,
        active_alerts_count=active_alerts,
        watchlists_count=watchlists_count,
    )


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Update current user info
    """
    update_data = user_in.dict(exclude_unset=True)
    
    # Handle password separately
    if "password" in update_data:
        current_user.hashed_password = get_password_hash(update_data.pop("password"))
    
    # Check email uniqueness if changing
    if "email" in update_data and update_data["email"] != current_user.email:
        existing = get_user_by_email(db, update_data["email"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Update fields
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    return current_user


@router.post("/api-key/regenerate", response_model=APIKeyResponse)
async def regenerate_user_api_key(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Regenerate API key for current user
    """
    new_key = regenerate_api_key(db, current_user)
    
    return APIKeyResponse(
        api_key=new_key,
        created_at=datetime.utcnow(),
    )


@router.get("/api-key", response_model=APIKeyResponse)
async def get_api_key(
    current_user: User = Depends(get_current_user_required),
):
    """
    Get current API key
    """
    return APIKeyResponse(
        api_key=current_user.api_key,
        created_at=current_user.created_at,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """
    Delete current user account and all data
    """
    db.delete(current_user)
    db.commit()
