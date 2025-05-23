import os
import uuid
from datetime import datetime, timedelta
from hashlib import pbkdf2_hmac

from eyened_orm import Creator
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing_extensions import deprecated

from ..config import settings
from ..db import get_db

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, stored_hash: str):
    return pwd_context.verify(password, stored_hash)


@deprecated("Use hash_password() instead")
def password_hash(password: str, secret_key: str):
    return pbkdf2_hmac("sha256", password.encode(), secret_key.encode(), 10000)


secure = False  # TODO: set to True when deploying (set up https)

router = APIRouter()
SESSION_COOKIE_NAME = "session_id"


class UserLogin(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class UserResponse(BaseModel):
    id: int
    username: str
    role: str | None


class SessionData(BaseModel):
    user_id: int


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


session_store = {}


class CurrentUser:
    def __init__(self, creator_id: int, username: str, role: str | None = None):
        self.id = creator_id
        self.username = username
        self.role = role

    def get_creator(self, session: Session) -> Creator:
        return session.query(Creator).where(Creator.CreatorID == self.id).first()


async def get_current_user(session_id: str = Cookie(None)) -> CurrentUser:
    """Get the current authenticated user."""
    if not session_id or session_id not in session_store:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_session = session_store[session_id]

    if datetime.now() > user_session["expires"]:
        del session_store[session_id]
        raise HTTPException(status_code=401, detail="Session expired")

    return CurrentUser(
        creator_id=user_session["user_id"],
        username=user_session["username"],
        role=user_session["role"],
    )

def create_session(user_id: int, username: str, role: str, remember_me: bool):
    session_id = str(uuid.uuid4())
    now = datetime.now()
    expiry = now + (timedelta(days=30) if remember_me else timedelta(hours=1))
    session_store[session_id] = {
        "user_id": user_id,
        "expires": expiry,
        "username": username,
        "role": role,
    }
    return session_id, expiry


def creator_to_response(creator: Creator) -> UserResponse:
    """Convert a Creator object to a UserResponse."""
    return UserResponse(
        id=creator.CreatorID,
        username=creator.CreatorName,
        role=creator.Role
    )


@router.get("/auth/me", response_model=UserResponse)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return creator_to_response(current_user.get_creator(session))



def check_login(username: str, password: str, db: Session) -> Creator:
    creator = (
        db.query(Creator).where(Creator.CreatorName == username).first()
    )
    if creator is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # First try the new Argon2 hash
    if creator.PasswordHash and verify_password(password, creator.PasswordHash):
        return creator

    # If no new hash or verification failed, try old hash
    if creator.Password and password_hash(password, settings.secret_key) == creator.Password:
        # Migrate to new hash
        new_hash = hash_password(password)
        creator.PasswordHash = new_hash
        creator.Password = None  # Clear old hash
        db.commit()
        db.refresh(creator)
        return creator

    raise HTTPException(status_code=401, detail="Invalid credentials")
        
@router.post("/auth/login-password", response_model=UserResponse)
async def login_password(
    user_data: UserLogin, response: Response, session: Session = Depends(get_db)
):
    creator = check_login(user_data.username, user_data.password, session)

    session_id, expiry = create_session(
        creator.CreatorID, creator.CreatorName, creator.Role, user_data.remember_me
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        max_age=int((expiry - datetime.now()).total_seconds()),
        secure=secure,
        samesite="strict",
        path="/",
    )

    return creator_to_response(creator)


@router.post("/auth/logout")
async def logout(response: Response, session_id: str = Cookie(None)):
    if session_id in session_store:
        del session_store[session_id]
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"message": "Logged out successfully"}


@router.post("/auth/change-password", response_model=UserResponse)
async def change_password(
    change_password_data: ChangePasswordRequest,
    response: Response,
    session: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    session_id: str = Cookie(None),
):
    creator = check_login(current_user.username, change_password_data.old_password, session)

    # Set new password using Argon2
    creator.PasswordHash = hash_password(change_password_data.new_password)
    creator.Password = None  # Clear old hash if it exists
    session.commit()

    # Log out the user after password change
    # if session_id in session_store:
    #     del session_store[session_id]
    # response.delete_cookie(SESSION_COOKIE_NAME)

    return creator_to_response(creator)


def create_user(
    session: Session,
    username: str,
    password: str,
    is_human: bool = True,
    description: str | None = None,
) -> Creator:
    """Create a new user with the given credentials.
    
    Args:
        session: Database session
        username: Username for the new user
        password: Password for the new user
        is_human: Whether the user is a human (default: True)
        description: Optional description of the user
        
    Returns:
        Creator: The newly created user
        
    Raises:
        HTTPException: If username already exists
    """
    # Check if username already exists
    existing_user = (
        session.query(Creator).where(Creator.CreatorName == username).first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create new user
    new_user = Creator(
        CreatorName=username,
        PasswordHash=hash_password(password),
        IsHuman=is_human,
        Description=description,
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    return new_user


@router.post("/auth/register", response_model=UserResponse)
async def register_user(
    user_data: UserLogin, response: Response, session: Session = Depends(get_db)
):
    new_user = create_user(session, user_data.username, user_data.password)
    return creator_to_response(new_user)
