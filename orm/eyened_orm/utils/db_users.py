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
        # Coerce explicitly: Creator.Role is an untyped Integer with no bind
        # processor, so pymysql's encoders dict (keyed on exact type) misses an
        # IntEnum and falls through to the string encoder. MySQL coerces the
        # resulting quoted string back to an int for this column, but only
        # because Python 3.11+ made IntEnum.__str__ return the number -- on
        # <=3.10 the same call yields e.g. "SystemRole.system_admin" and the
        # INSERT fails under STRICT mode.
        Role=int(role) if role is not None else None,
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
    lock the real admin out. More generally: the ``password`` argument is used
    **only** when creating a brand-new account -- the promote and reactivate
    branches below discard it just as much as the already-admin case does.

    Flushes only; the caller owns the commit (``eorm init-admin`` commits
    explicitly, and under the API ``get_db`` commits at the request boundary).

    Note: two concurrent first requests on a cold DB can both see
    ``get_by_name -> None`` and both attempt the create branch below; the second
    then fails its INSERT on the unique ``CreatorName`` constraint (IntegrityError
    -> 500). This is dev-only (the only caller that can race is the
    ``public_auth_disabled`` bypass), fails closed, and self-heals on retry once
    the first request's row is visible. Left unhandled deliberately: the obvious
    ``except IntegrityError: session.rollback()`` would discard the rest of the
    request's transaction, which is a bigger behavior change than this bootstrap
    helper should make unilaterally.
    """
    from eyened_orm.repositories.creator_repository import CreatorRepository

    repository = CreatorRepository(session)
    creator = repository.get_by_name(username)
    if creator is None:
        return create_user(
            session, username, password, role=SystemRole.system_admin
        )

    if not is_system_admin(creator):
        # int(): see the matching comment on create_user's Role= -- same untyped
        # Integer column, same pymysql encoder gap.
        creator.Role = int(SystemRole.system_admin)
    if creator.Inactive:
        creator.Inactive = False
    repository.add(creator)
    return creator
