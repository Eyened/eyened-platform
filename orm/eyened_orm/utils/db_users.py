import enum

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


class BootstrapOutcome(enum.Enum):
    """What ``ensure_admin`` actually did, so callers can react proportionately.

    The distinction is load-bearing, not cosmetic: promoting a *pre-existing*
    account is the one case a human must approve, because the account keeps its
    existing password and therefore its existing owner. Reporting it the same
    way as a routine no-op re-run is what made the previous warning useless.
    """

    created = "created"          # brand-new account
    promoted = "promoted"        # a pre-existing account gained system_admin
    reactivated = "reactivated"  # a pre-existing admin's Inactive was cleared
    unchanged = "unchanged"      # already an active admin; nothing written


def ensure_admin(
    session: Session,
    username: str,
    password: str | None,
    *,
    reactivate: bool = False,
) -> tuple[Creator, BootstrapOutcome]:
    """Idempotent create-or-promote of a ``system_admin`` -- the real ``init_admin``.

    Bootstrap must precede enforcement: granting a role needs an existing admin,
    so >=1 system_admin is seeded out-of-band here. A single admin suffices --
    an admin is a data superuser, so it can grant everyone else and the platform
    cannot brick.

    Four outcomes, returned alongside the ``Creator`` so the caller can react
    proportionately (see ``BootstrapOutcome``):

    - **absent** -> create with ``Role = system_admin`` (``created``)
    - **present but not an admin** -> promote in place (``promoted``).
      ``Role = NULL`` is the state of every production row pre-cutover. A
      deactivated non-admin is promoted without clearing ``Inactive``:
      promotion is the security-significant fact here, and reactivating a
      *non*-admin is not something any caller asked for.
    - **present, deactivated admin, and ``reactivate=True``** -> clear
      ``Inactive`` (``reactivated``)
    - **otherwise** -> return untouched (``unchanged``)

    ``password`` is used **only** when creating a brand-new account. The promote
    and reactivate branches keep the account's existing credential -- so
    re-running the bootstrap can never lock the real admin out, and equally, a
    promoted pre-existing account stays reachable by whoever set that password.
    That is why the promote case wants human confirmation at the call site.

    ``reactivate`` is opt-in because the callers differ in kind. ``eorm
    init-admin`` passes ``True``: a human running the recovery command *is* the
    consent, and without it a deployment whose only admin was deactivated could
    not be recovered by the one command that exists to recover it (the
    last-admin guard that would prevent that state is P7). The
    ``public_auth_disabled`` dev bypass passes the default ``False``: it runs on
    every request, so unconditional reactivation would silently and permanently
    undo a deliberate deactivation, and the reactivation would outlive the flag.

    Flushes only; the caller owns the commit (``eorm init-admin`` commits
    explicitly, and under the API the commit happens at the request boundary).

    Note: two concurrent first callers on a cold database can both see
    ``get_by_name -> None`` and both attempt the create branch; the second then
    fails its INSERT on the unique ``CreatorName`` constraint (IntegrityError
    -> a 500 under the dev bypass, a traceback under ``eorm init-admin``). Not
    a dev-bypass-only hazard -- two concurrent bootstrap runs race identically;
    the bypass merely makes it easy to hit, since it runs on every request.
    Fails closed either way, and self-heals on retry once the first writer's
    row is visible. Left unhandled deliberately:
    the obvious ``except IntegrityError: session.rollback()`` would discard the
    rest of the request's transaction, which is a bigger behaviour change than
    this bootstrap helper should make unilaterally.
    """
    from eyened_orm.repositories.creator_repository import CreatorRepository

    repository = CreatorRepository(session)
    creator = repository.get_by_name(username)
    if creator is None:
        created = create_user(
            session, username, password, role=SystemRole.system_admin
        )
        return created, BootstrapOutcome.created

    if not is_system_admin(creator):
        # int(): see the matching comment on create_user's Role= -- same untyped
        # Integer column, same pymysql encoder gap.
        creator.Role = int(SystemRole.system_admin)
        repository.add(creator)
        return creator, BootstrapOutcome.promoted

    if creator.Inactive and reactivate:
        creator.Inactive = False
        repository.add(creator)
        return creator, BootstrapOutcome.reactivated

    return creator, BootstrapOutcome.unchanged
