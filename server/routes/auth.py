from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from eyened_orm import Creator

from .config import settings
from .db import get_db
from .login_manager import LoginManager
from .utils import password_hash

router = APIRouter()

# Initialize LoginManager
manager = LoginManager(
    secret=settings.jwt_secret_key,
    token_url="/auth/token",
    use_cookie=True,
    use_header=False,
    access_cookie_name="access_token_cookie",
    refresh_cookie_name="refresh_token_cookie",
    access_token_expiry=timedelta(seconds=settings.access_token_duration),
    refresh_token_expiry=timedelta(seconds=settings.refresh_token_duration),
)


# Pydantic models
class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str | None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

# User loader callback


@manager.user_loader()
def load_user(id: int, session: Session):
    return session.query(Creator).get(id)


@router.post("/auth/login-password", response_model=UserResponse)
async def login_password(user_data: UserLogin, session: Session = Depends(get_db)):
    """Login with username and password"""
    # Placeholder: Replace with your user authentication logic
    # Example:
    # user = db.query(User).filter(User.username == user_data.username).first()
    # if not user or not verify_password(user_data.password, user.hashed_password):
    #     raise HTTPException(status_code=401, detail="Invalid credentials")

    user = (
        session.query(Creator).where(
            Creator.CreatorName == user_data.username).first()
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.Password != password_hash(user_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create tokens
    sub = str(user.CreatorID)
    access_token = manager.create_access_token(data={"sub": sub})
    refresh_token = manager.create_refresh_token(data={"sub": sub})

    # Create response
    response = JSONResponse(
        content={
            "id": user.CreatorID,
            "username": user.CreatorName,
            "role": user.Role,
        }
    )

    # Set cookies
    manager.set_access_cookie(response, access_token)
    manager.set_refresh_cookie(response, refresh_token)

    return response


@router.post("/auth/refresh", response_model=UserResponse)
async def refresh(
    session: Session = Depends(get_db),
    refresh_token: Optional[str] = Cookie(None, alias="refresh_token_cookie"),
):
    """Refresh access token using refresh token
    This endpoint may be called when the access token has expired
    """
    if not refresh_token:
        raise HTTPException(
            status_code=401, detail="No refresh token provided")

    # Verify refresh token
    user_identifier = manager._get_userid(refresh_token)
    # Get user data from database
    user = session.query(Creator).get(user_identifier)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    sub = str(user.CreatorID)
    # Create new access token
    access_token = manager.create_access_token(data={"sub": sub})

    # Create response
    response = JSONResponse(
        content={
            "id": user.CreatorID,
            "username": user.CreatorName,
            "role": user.Role,
        }
    )

    # Set new access token
    manager.set_access_cookie(response, access_token)

    return response


@router.post("/auth/logout")
async def logout():
    """Log out user by clearing tokens"""
    response = JSONResponse(content={"message": "Logged out successfully"})

    # Clear cookies
    response.delete_cookie(manager.access_cookie_name)
    response.delete_cookie(manager.refresh_cookie_name)

    return response


@router.post("/auth/change-password", response_model=UserResponse)
async def change_password(
    change_password_data: ChangePasswordRequest,
    session: Session = Depends(get_db),
    user_id: int = Depends(manager)
):
    """Change user password"""

    user = session.query(Creator).get(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify old password
    if user.Password != password_hash(change_password_data.old_password):
        raise HTTPException(status_code=401, detail="Invalid old password")

    # Update password
    user.Password = password_hash(change_password_data.new_password)
    session.commit()

    return UserResponse(id=user_id, username=user.CreatorName, role=user.Role)


@router.post('/auth/register', response_model=UserResponse)
async def register_user(
        user_data: UserLogin,
        session: Session = Depends(get_db),
        user_id: int = Depends(manager)):

    exisiting_user = (
        session.query(Creator).where(
            Creator.CreatorName == user_data.username).first()
    )
    if exisiting_user is not None:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = Creator()
    new_user.CreatorName = user_data.username
    new_user.Password = password_hash(user_data.password)
    # TODO: MSN? email?
    new_user.IsHuman = 1

    session.add(new_user)
    session.commit()

    return UserResponse(id=new_user.CreatorID, username=new_user.CreatorName, role=new_user.Role)
