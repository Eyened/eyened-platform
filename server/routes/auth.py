import os
import uuid
from datetime import datetime, timedelta

from eyened_orm import Creator
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..utils.crypto import hash_password, password_hash, verify_password
from ..config import settings

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
        role=creator.Role if hasattr(creator, "Role") else None,
    )


@router.get("/auth/me", response_model=UserResponse)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return creator_to_response(current_user.get_creator(session))



def check_login(username: str, password: str, session: Session) -> Creator:
    creator = (
        session.query(Creator).where(Creator.CreatorName == username).first()
    )
    if creator is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    try:
        if not verify_password(password, creator.Password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except ValueError as e:
        print(e)
        # check old hash
        # TODO: remove this once all users have been migrated to argon2
        valid = password_hash(password, settings.secret_key) == creator.Password
        if valid:
            new_hash = hash_password(password)
            print('TODO: migrate user', creator.CreatorID, 'to new hash', new_hash)
            #creator.Password = new_hash
            #session.commit()
            #session.refresh(creator)
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    return creator
        
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

    creator.Password = password_hash(change_password_data.new_password, settings.secret_key)
    session.commit()

    # Log out the user after password change
    # if session_id in session_store:
    #     del session_store[session_id]
    # response.delete_cookie(SESSION_COOKIE_NAME)

    return creator_to_response(creator)


@router.post("/auth/register", response_model=UserResponse)
async def register_user(
    user_data: UserLogin, response: Response, session: Session = Depends(get_db)
):
    # Check if username already exists
    existing_user = (
        session.query(Creator).where(Creator.CreatorName == user_data.username).first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create new user
    new_user = Creator(
        CreatorName=user_data.username,
        Password=password_hash(user_data.password, settings.secret_key),
        IsHuman=1,
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return creator_to_response(new_user)
