from eyened_orm import Creator
from sqlalchemy.orm import Session
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2", "unix_disabled"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return pwd_context.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(password, stored_hash)


def disable_password(stored_hash: str|None) -> str:
    """Generated a valid password hash that disables password login."""
    return pwd_context.disable(stored_hash)


class WeakPasswordError(Exception):
    """A password being set fails the policy. Not ``ValueError``: ``create_user`` raises that for a taken name."""


# NIST SP 800-63B-4 §3.1.1.2: 15 is the minimum without MFA; the maximum must be at least 64.
_MIN_LENGTH = 15
_MAX_LENGTH = 128
# Below this length a username would ban every password that contains its letters.
_MIN_CHECKED_USERNAME = 4


def check_new_password(password: str, *, username: str) -> None:
    """Raise ``WeakPasswordError`` unless ``password`` may be set.

    Counts code points and normalizes nothing: normalizing before hashing would
    change how every stored non-ASCII password verifies. No composition rules.
    Not applied at login, so existing passwords keep working.
    """
    if len(password) < _MIN_LENGTH:
        raise WeakPasswordError(f"password must be at least {_MIN_LENGTH} characters")
    if len(password) > _MAX_LENGTH:
        raise WeakPasswordError(f"password must be at most {_MAX_LENGTH} characters")
    lowered = password.casefold()
    if "eyened" in lowered:
        raise WeakPasswordError("password must not contain 'eyened'")
    if len(username) >= _MIN_CHECKED_USERNAME and username.casefold() in lowered:
        raise WeakPasswordError("password must not contain the username")


def build_user(
    username: str,
    password: str | None,
    *,
    is_human: bool = True,
    description: str | None = None,
    employee_identifier: str | None = None,
) -> Creator:
    """An unsaved Creator. A ``None`` or empty password disables password login."""
    return Creator(
        CreatorName=username,
        PasswordHash=hash_password(password) if password else disable_password(None),
        IsHuman=is_human,
        Description=description,
        EmployeeIdentifier=employee_identifier,
    )


def create_user(
    session: Session,
    username: str,
    password: str | None,
    is_human: bool = True,
    description: str | None = None,
    employee_identifier: str | None = None,
) -> Creator:
    """
    Create a new user with the given credentials.

    If the password is None, a disabled password is generated. The password
    policy is not applied: OIDC provisioning passes None, and test fixtures
    seed through here.

    Flushes so the new user's PK is assigned; the caller owns the commit.
    """
    existing_user = (
        session.query(Creator).where(Creator.CreatorName == username).first()
    )
    if existing_user:
        raise ValueError("Username already exists")

    new_user = build_user(
        username,
        password,
        is_human=is_human,
        description=description,
        employee_identifier=employee_identifier,
    )
    session.add(new_user)
    session.flush()

    return new_user
