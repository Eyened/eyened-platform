from eyened_orm import Creator, SystemRole, is_system_admin
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

def create_user(
    session: Session,
    username: str,
    password: str | None,
    is_human: bool = True,
    description: str | None = None,
    employee_identifier: str | None = None,
    role: SystemRole | None = None,
) -> Creator:
    """
    Create a new user with the given credentials.

    If the password is None, a disabled password is generated.

    ``role`` defaults to None so the unauthenticated paths that call this
    (``/auth/register``, OIDC auto-provision) keep landing at ``Role = NULL``:
    they cannot set a system role, so neither is an escalation path.

    Flushes so the new user's PK is assigned; the caller owns the commit.
    """
    # Check if username already exists
    existing_user = (
        session.query(Creator).where(Creator.CreatorName == username).first()
    )
    if existing_user:
        raise ValueError("Username already exists")

    # Create new user
    password_hash = hash_password(password) if password else disable_password(None)
    new_user = Creator(
        CreatorName=username,
        PasswordHash=password_hash,
        IsHuman=is_human,
        Description=description,
        EmployeeIdentifier=employee_identifier,
        Role=role,
    )
    session.add(new_user)
    session.flush()

    return new_user


def ensure_admin(
    session: Session, username: str, password: str | None
) -> Creator:
    """Idempotent create-or-promote of a ``system_admin`` -- the real ``init_admin``.

    Bootstrap must precede enforcement: granting a role needs an existing admin,
    so >=1 system_admin is seeded out-of-band here. A
    single admin suffices -- an admin is a data superuser, so it can grant everyone
    else and the platform cannot brick.

    Three cases, in order:

    - **absent** -> create with ``Role = system_admin``
    - **present but not an admin** -> promote in place (Role=NULL is the state of
      every production row pre-cutover)
    - **present, deactivated** -> reactivate, so this stays the recovery path for a
      deployment whose only admin was deactivated

    An account that is already an active admin is returned untouched -- in
    particular the password is **not** reset, so re-running the bootstrap can never
    lock the real admin out.

    Flushes only; the caller owns the commit (``eorm init-admin`` commits
    explicitly, and under the API ``get_db`` commits at the request boundary).
    """
    from eyened_orm.repositories.creator_repository import CreatorRepository

    repository = CreatorRepository(session)
    creator = repository.get_by_name(username)
    if creator is None:
        return create_user(
            session, username, password, role=SystemRole.system_admin
        )

    if not is_system_admin(creator):
        creator.Role = SystemRole.system_admin
    if creator.Inactive:
        creator.Inactive = False
    repository.add(creator)
    return creator
