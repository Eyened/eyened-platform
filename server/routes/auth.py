import jwt
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac

from eyened_orm import Creator, CreatorTagLink
from eyened_orm.utils.db_users import create_user, verify_password, hash_password
from fastapi import APIRouter, Depends, HTTPException, Header, status, Response, Cookie

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..utils.db_logging import get_db_logger

# Password hashing configuration

router = APIRouter()


# Pydantic models
class UserLogin(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class TokenLoginRequest(BaseModel):
    username: str
    password: str
    api_client: bool = False


class UserResponse(BaseModel):
    id: int
    username: str
    role: int | None
    starred_tags: list[int] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CurrentUser:
    def __init__(self, creator_id: int, username: str, role: str | None = None):
        self.id = creator_id
        self.username = username
        self.role = role

    def get_creator(self, session: Session) -> Creator:
        return session.query(Creator).where(Creator.CreatorID == self.id).first()


# JWT utilities
def create_access_token(user_id: int, username: str, role: str | None = None) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": str(user_id),  # Convert to string
        "username": username,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload, settings.secret_key_value, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: int) -> str:
    """Create a JWT refresh token."""
    payload = {
        "sub": str(user_id),  # Convert to string
        "type": "refresh",
        "exp": datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload, settings.secret_key_value, algorithm=settings.jwt_algorithm
    )


def _decode_token_or_401(token: str, *, detail: str | None = None) -> dict:
    """Decode JWT; raise 401 when invalid."""
    try:
        return jwt.decode(
            token, settings.secret_key_value, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    return _decode_token_or_401(token)


def _try_decode_token(token: str) -> dict | None:
    """Decode JWT safely; return None when invalid."""
    try:
        return jwt.decode(
            token, settings.secret_key_value, algorithms=[settings.jwt_algorithm]
        )
    except Exception:
        return None


async def is_authenticated(
    authorization: str = Header(None),
    jwt_token: str = Cookie(None),
) -> bool:
    """Return True if a valid access token is present (header or cookie)."""
    if settings.public_auth_disabled:
        return True

    if authorization and authorization.startswith("Bearer "):
        payload = _try_decode_token(authorization[7:])
        if payload and payload.get("type") == "access":
            return True

    if jwt_token:
        payload = _try_decode_token(jwt_token)
        if payload and payload.get("type") == "access":
            return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


# Replace the existing get_current_user function with this merged version
async def get_current_user(
    authorization: str = Header(None),
    jwt_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
    session: Session = Depends(get_db),
) -> CurrentUser:
    """Get the current authenticated user from either Authorization header or cookies."""
    # Bypass authentication if disabled (development mode)
    if settings.public_auth_disabled:
        creator = (
            session.query(Creator)
            .where(Creator.CreatorName == settings.admin_username)
            .first()
        )
        if not creator:
            # Should not happen if init_admin ran; ensure dev usability
            creator = create_user(
                session, settings.admin_username, settings.admin_password
            )
        return CurrentUser(
            creator_id=creator.CreatorID,
            username=creator.CreatorName,
            role=creator.Role,
        )

    # Try Authorization header first (for API clients)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        payload = verify_token(token)
        if payload.get("type") == "access":
            return CurrentUser(
                creator_id=int(payload["sub"]),
                username=payload["username"],
                role=payload.get("role"),
            )

    # Try access token cookie (for web clients)
    if jwt_token:
        try:
            payload = verify_token(jwt_token)
            if payload.get("type") == "access":
                return CurrentUser(
                    creator_id=int(payload["sub"]),
                    username=payload["username"],
                    role=payload.get("role"),
                )
        except:
            pass  # Access token failed, try refresh

    # Try refresh token
    if refresh_token:
        try:
            payload = verify_token(refresh_token)
            if payload.get("type") == "refresh":
                # This will be handled by the refresh endpoint
                # For now, we'll let the client handle the 401 and call refresh
                pass
        except:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
    )


# User utilities
def creator_to_response(
    creator: Creator, session: Session | None = None
) -> UserResponse:
    """Convert a Creator object to a UserResponse."""
    starred: list[int] = []
    if session is not None:
        rows = (
            session.query(CreatorTagLink)
            .where(CreatorTagLink.CreatorID == creator.CreatorID)
            .all()
        )
        starred = [r.TagID for r in rows]
    return UserResponse(
        id=creator.CreatorID,
        username=creator.CreatorName,
        role=creator.Role,
        starred_tags=starred,
    )


def check_login(username: str, password: str, db: Session) -> Creator:
    """Verify user credentials and return the user."""
    creator = db.query(Creator).where(Creator.CreatorName == username).first()
    if creator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Verify password using Argon2 hash
    if creator.PasswordHash and verify_password(password, creator.PasswordHash):
        return creator

    # Legacy password hash support (for migration)
    if creator.Password:
        old_hash = pbkdf2_hmac(
            "sha256", password.encode(), "6f4b661212".encode(), 10000
        )
        if old_hash == creator.Password:
            # Migrate to new hash
            creator.PasswordHash = hash_password(password)
            creator.Password = None
            db.commit()
            db.refresh(creator)
            # Log password migration
            logger = get_db_logger()
            if logger:
                logger.log_update(
                    user=creator.CreatorName,
                    user_id=creator.CreatorID,
                    endpoint="POST /api/auth/login",
                    entity="Creator",
                    entity_id=creator.CreatorID,
                    changes={"password_hash": "migrated from legacy"},
                )
            return creator

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
    )


# API endpoints
@router.post("/auth/login", response_model=UserResponse)
async def login(
    user_data: TokenLoginRequest,  # Changed from UserLogin to TokenLoginRequest
    response: Response,
    session: Session = Depends(get_db),
):
    """Login with username and password, return user info and set JWT cookies or return token."""
    creator = check_login(user_data.username, user_data.password, session)

    # Create both tokens
    access_token = create_access_token(
        creator.CreatorID, creator.CreatorName, creator.Role
    )
    refresh_token = create_refresh_token(creator.CreatorID)

    # If API client, return token in response body
    if user_data.api_client:
        return {
            "user": creator_to_response(creator, session),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }

    # Otherwise, set cookies (existing behavior)
    response.set_cookie(
        key=settings.jwt_cookie_name,
        value=access_token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        secure=False,  # Set to True in production
        samesite="strict",
        path="/",
    )

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        secure=False,  # Set to True in production
        samesite="strict",
        path="/",
    )

    return creator_to_response(creator, session)


@router.post("/auth/token", response_model=TokenResponse)
async def get_token(user_data: UserLogin, session: Session = Depends(get_db)):
    """Get access token for API clients."""
    creator = check_login(user_data.username, user_data.password, session)

    access_token = create_access_token(
        creator.CreatorID, creator.CreatorName, creator.Role
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=creator_to_response(creator, session),
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Get current user information."""
    return creator_to_response(current_user.get_creator(session), session)


@router.post("/auth/change-password", response_model=UserResponse)
async def change_password(
    change_password_data: ChangePasswordRequest,
    session: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Change user password."""
    creator = check_login(
        current_user.username, change_password_data.old_password, session
    )

    # Set new password using Argon2
    creator.PasswordHash = hash_password(change_password_data.new_password)
    creator.Password = None  # Clear old hash if it exists
    session.commit()

    # Log password change
    logger = get_db_logger()
    if logger:
        logger.log_update(
            user=creator.CreatorName,
            user_id=creator.CreatorID,
            endpoint="POST /api/auth/change-password",
            entity="Creator",
            entity_id=creator.CreatorID,
            changes={"password_hash": "updated"},
        )

    return creator_to_response(creator, session)


@router.post("/auth/register", response_model=UserResponse)
async def register_user(user_data: UserLogin, session: Session = Depends(get_db)):
    """Register a new user."""
    new_user = create_user(session, user_data.username, user_data.password)

    # Log user creation
    logger = get_db_logger()
    if logger:
        logger.log_insert(
            user="system",  # Registration doesn't require auth
            user_id=0,
            endpoint="POST /api/auth/register",
            entity="Creator",
            entity_id=new_user.CreatorID,
            fields={
                "username": new_user.CreatorName,
                "is_human": new_user.IsHuman,
            },
        )

    return creator_to_response(new_user, session)


@router.post("/auth/refresh", response_model=UserResponse)
async def refresh_token(
    response: Response,
    refresh_token: str = Cookie(None),
    session: Session = Depends(get_db),
):
    """Refresh access token and extend refresh token for active users."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token required")

    try:
        payload = verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        # Get user from database
        creator = (
            session.query(Creator).where(Creator.CreatorID == payload["sub"]).first()
        )
        if not creator:
            raise HTTPException(status_code=401, detail="User not found")

        # Create new access token
        new_access_token = create_access_token(
            creator.CreatorID, creator.CreatorName, creator.Role
        )

        # Create NEW refresh token (extends session for active users)
        new_refresh_token = create_refresh_token(creator.CreatorID)

        # Update access token cookie
        response.set_cookie(
            key=settings.jwt_cookie_name,
            value=new_access_token,
            httponly=True,
            max_age=settings.access_token_expire_minutes * 60,
            secure=False,
            samesite="strict",
            path="/",
        )

        # Update refresh token cookie (extends session)
        response.set_cookie(
            key=settings.refresh_cookie_name,
            value=new_refresh_token,
            httponly=True,
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
            secure=False,
            samesite="strict",
            path="/",
        )

        return creator_to_response(creator, session)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


# Update logout to clear both cookies
@router.post("/auth/logout")
async def logout(response: Response):
    """Logout and clear both JWT cookies."""
    response.delete_cookie(settings.jwt_cookie_name)
    response.delete_cookie(settings.refresh_cookie_name)
    return {"message": "Logged out successfully"}
