"""Password authentication and the account lifecycle behind ``/auth``.

The one service that holds no ``AccessScope``. Authentication runs before an
actor exists -- logging in is how one comes to exist -- so there is no scope to
hold, and a ``trusted()`` scope kept as an attribute and never read would only
look like one. ``get_auth_service`` builds the repositories with
``AccessScope.trusted()`` instead, in that one place.

For the same reason the actor is a per-method argument rather than constructor
state: a constructor actor would make this service's factory depend on
``get_current_user``, and logging in would then require being logged in.

The OIDC half of ``server/routes/auth.py`` (``check_oidc_login``) is
deliberately not here. It keeps its ``Session`` until its token-validation
branches have a test harness of their own.
"""
from __future__ import annotations

from hashlib import pbkdf2_hmac

from fastapi import Depends
from sqlalchemy.orm import Session

from eyened_orm import Creator
from eyened_orm.authz.scope import AccessScope
from eyened_orm.repositories.creator_repository import CreatorRepository
from eyened_orm.repositories.tag_repository import TagRepository
from eyened_orm.utils.db_users import disable_password, hash_password, verify_password

from ..db import get_db
from .acting_user import ActingUser
from .audit_service import AuditService, get_audit_service
from .exceptions import ConflictError, UnauthenticatedError
from .password_hashing import password_hash_capacity

_INVALID_CREDENTIALS = "Invalid credentials"


class AuthService:
    """Authenticate, register and re-credential password accounts.

    Returns ORM models; the routes build the DTOs.
    """

    def __init__(
        self,
        creators: CreatorRepository,
        tags: TagRepository,
        *,
        audit: AuditService,
    ) -> None:
        self._creators = creators
        self._tags = tags
        self._audit = audit

    def authenticate(self, username: str, password: str) -> Creator:
        """Return the active account these credentials belong to.

        Raises:
            UnauthenticatedError: For an unknown username, a deactivated account
                and a wrong password alike, with the same detail.
        """
        creator = self._creators.get_by_name(username)
        if creator is None or creator.Inactive:
            # v0.3: a deactivated user *cannot authenticate* and holds no access.
            # Checked before the password is verified, and answered with the same
            # "Invalid credentials" as an unknown name, so the refusal does not
            # tell a caller whether the account exists or whether the password was
            # right. It also stops the legacy-hash migration below from writing to
            # a revoked row.
            raise UnauthenticatedError(_INVALID_CREDENTIALS)

        # Verify password using Argon2 hash. Gated: this is the one hashing site an
        # unauthenticated caller reaches, so it is the one that can be amplified.
        if creator.PasswordHash:
            with password_hash_capacity():
                if verify_password(password, creator.PasswordHash):
                    return creator

        # Legacy password hash support (for migration)
        if creator.Password:
            old_hash = pbkdf2_hmac(
                "sha256", password.encode(), "6f4b661212".encode(), 10000
            )
            if old_hash == creator.Password:
                # Migrate to new hash. Flushed here; get_db commits it at the
                # request boundary.
                with password_hash_capacity():
                    creator.PasswordHash = hash_password(password)
                creator.Password = None
                self._creators.save(creator)
                self._audit.record(
                    action="UPDATE",
                    entity="Creator",
                    actor=ActingUser(id=creator.CreatorID, username=creator.CreatorName),
                    entity_id=creator.CreatorID,
                    changes={"password_hash": "migrated from legacy"},
                )
                return creator

        raise UnauthenticatedError(_INVALID_CREDENTIALS)

    def get_creator(self, creator_id: int) -> Creator | None:
        """The account with this id, or None. A seam for routes, which may not hold a repository."""
        return self._creators.get_by_id(creator_id)

    def starred_tag_ids(self, creator_id: int) -> list[int]:
        """Ids of the tags this account has starred. A seam, like ``get_creator``."""
        return self._tags.starred_tag_ids(creator_id)

    def register(self, username: str, password: str) -> Creator:
        """Create a password account, attributed to the ``auth:register`` trusted path.

        Raises:
            ConflictError: If the username is taken.
        """
        if self._creators.get_by_name(username) is not None:
            # Uncaught, a taken name reached main.py's blanket handler as a 500,
            # which made an unauthenticated caller's 200-vs-500 a
            # username-enumeration oracle. A plain string rather than
            # ConflictError's structured {"code", "message"} dict, on purpose:
            # this is the exact body the endpoint has always returned, and no
            # client branches on it, so it is kept rather than reshaped.
            raise ConflictError("An account with this username already exists.")

        with password_hash_capacity():
            password_hash = hash_password(password) if password else disable_password(None)
        creator = Creator(CreatorName=username, PasswordHash=password_hash, IsHuman=True)
        self._creators.add(creator)

        self._audit.record(
            action="INSERT",
            entity="Creator",
            trusted_path="auth:register",
            entity_id=creator.CreatorID,
            changes={"username": creator.CreatorName, "is_human": creator.IsHuman},
        )
        return creator

    def change_password(
        self,
        username: str,
        old_password: str,
        new_password: str,
        *,
        actor: ActingUser,
    ) -> Creator:
        """Replace the password of the account ``old_password`` authenticates.

        Raises:
            UnauthenticatedError: If ``username`` and ``old_password`` do not
                authenticate.
        """
        creator = self.authenticate(username, old_password)

        with password_hash_capacity():
            creator.PasswordHash = hash_password(new_password)
        creator.Password = None  # Clear old hash if it exists
        self._creators.save(creator)

        self._audit.record(
            action="UPDATE",
            entity="Creator",
            actor=actor,
            entity_id=creator.CreatorID,
            changes={"password_hash": "updated"},
        )
        return creator


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Default AuthService wiring for FastAPI ``Depends()``.

    Resolves no ``AccessScope``: ``get_access_scope`` depends on
    ``get_current_user``, so depending on it here would make logging in require
    a login. The ``trusted()`` scope is built once, for both repositories.
    """
    scope = AccessScope.trusted()
    return AuthService(
        CreatorRepository(db, scope=scope),
        TagRepository(db, scope=scope),
        audit=get_audit_service(db),
    )
