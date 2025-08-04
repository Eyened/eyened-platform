import jwt
from datetime import datetime, timedelta

from eyened_orm import Creator
from fastapi import APIRouter, Depends, HTTPException, Header, status, Response, Cookie
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db

# Password hashing configuration
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# JWT configuration
JWT_SECRET_KEY = settings.secret_key
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Add refresh token cookie name constant
JWT_COOKIE_NAME = "jwt_token"
REFRESH_COOKIE_NAME = "refresh_token"

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


# Password utilities
def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return pwd_context.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(password, stored_hash)


# JWT utilities
def create_access_token(user_id: int, username: str, role: str | None = None) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": str(user_id),  # Convert to string
        "username": username,
        "role": role,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Create a JWT refresh token."""
    payload = {
        "sub": str(user_id),  # Convert to string
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed"
        )

# Replace the existing get_current_user function with this merged version
async def get_current_user(
    authorization: str = Header(None),
    jwt_token: str = Cookie(None),
    refresh_token: str = Cookie(None)
) -> CurrentUser:
    """Get the current authenticated user from either Authorization header or cookies."""
    
    # Try Authorization header first (for API clients)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            payload = verify_token(token)
            if payload.get("type") == "access":
                return CurrentUser(
                    creator_id=int(payload["sub"]),
                    username=payload["username"],
                    role=payload.get("role")
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    # Try access token cookie (for web clients)
    if jwt_token:
        try:
            payload = verify_token(jwt_token)
            if payload.get("type") == "access":
                return CurrentUser(
                    creator_id=int(payload["sub"]),
                    username=payload["username"],
                    role=payload.get("role")
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
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required"
    )


# User utilities
def creator_to_response(creator: Creator) -> UserResponse:
    """Convert a Creator object to a UserResponse."""
    return UserResponse(
        id=creator.CreatorID,
        username=creator.CreatorName,
        role=creator.Role
    )


def check_login(username: str, password: str, db: Session) -> Creator:
    """Verify user credentials and return the user."""
    creator = (
        db.query(Creator).where(Creator.CreatorName == username).first()
    )
    if creator is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Verify password using Argon2 hash
    if creator.PasswordHash and verify_password(password, creator.PasswordHash):
        return creator

    # Legacy password hash support (for migration)
    if creator.Password:
        from hashlib import pbkdf2_hmac
        old_hash = pbkdf2_hmac("sha256", password.encode(), "6f4b661212".encode(), 10000)
        if old_hash == creator.Password:
            # Migrate to new hash
            creator.PasswordHash = hash_password(password)
            creator.Password = None
            db.commit()
            db.refresh(creator)
            return creator

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )


def create_user(
    session: Session,
    username: str,
    password: str,
    is_human: bool = True,
    description: str | None = None,
) -> Creator:
    """Create a new user with the given credentials."""
    # Check if username already exists
    existing_user = (
        session.query(Creator).where(Creator.CreatorName == username).first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

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


# API endpoints
@router.post("/auth/login", response_model=UserResponse)
async def login(
    user_data: TokenLoginRequest,  # Changed from UserLogin to TokenLoginRequest
    response: Response,
    session: Session = Depends(get_db)
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
            "user": creator_to_response(creator),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    # Otherwise, set cookies (existing behavior)
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=False,  # Set to True in production
        samesite="strict",
        path="/",
    )
    
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        secure=False,  # Set to True in production
        samesite="strict",
        path="/",
    )
    
    return creator_to_response(creator)


@router.post("/auth/token", response_model=TokenResponse)
async def get_token(
    user_data: UserLogin,
    session: Session = Depends(get_db)
):
    """Get access token for API clients."""
    creator = check_login(user_data.username, user_data.password, session)
    
    access_token = create_access_token(
        creator.CreatorID, creator.CreatorName, creator.Role
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=creator_to_response(creator)
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Get current user information."""
    return creator_to_response(current_user.get_creator(session))


@router.post("/auth/change-password", response_model=UserResponse)
async def change_password(
    change_password_data: ChangePasswordRequest,
    session: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Change user password."""
    creator = check_login(current_user.username, change_password_data.old_password, session)

    # Set new password using Argon2
    creator.PasswordHash = hash_password(change_password_data.new_password)
    creator.Password = None  # Clear old hash if it exists
    session.commit()

    return creator_to_response(creator)


@router.post("/auth/register", response_model=UserResponse)
async def register_user(
    user_data: UserLogin,
    session: Session = Depends(get_db)
):
    """Register a new user."""
    new_user = create_user(session, user_data.username, user_data.password)
    return creator_to_response(new_user)


@router.post("/auth/refresh", response_model=UserResponse)
async def refresh_token(
    response: Response,
    refresh_token: str = Cookie(None),
    session: Session = Depends(get_db)
):
    """Refresh access token using refresh token from cookie."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )
    
    try:
        payload = verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        # Get user from database
        creator = session.query(Creator).where(Creator.CreatorID == payload["sub"]).first()
        if not creator:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Create new access token
        new_access_token = create_access_token(
            creator.CreatorID, creator.CreatorName, creator.Role
        )
        
        # Update access token cookie
        response.set_cookie(
            key=JWT_COOKIE_NAME,
            value=new_access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            secure=False,
            samesite="strict",
            path="/",
        )
        
        return creator_to_response(creator)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

# Update logout to clear both cookies
@router.post("/auth/logout")
async def logout(response: Response):
    """Logout and clear both JWT cookies."""
    response.delete_cookie(JWT_COOKIE_NAME)
    response.delete_cookie(REFRESH_COOKIE_NAME)
    return {"message": "Logged out successfully"}
