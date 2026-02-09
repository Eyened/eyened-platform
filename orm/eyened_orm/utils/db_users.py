from eyened_orm import Creator
from sqlalchemy.orm import Session
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return pwd_context.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(password, stored_hash)


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
        raise ValueError("Username already exists")

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
