"""Account lifecycle: activation, administrator status and passwords.

Separate from ``membership_admin.py`` because the two change for different
reasons -- membership for RBAC-policy reasons, credentials for identity
reasons -- and because these four methods need one repository where the
membership methods need four. Under a single class each of these would carry
three dependencies it never touches.

v0.3 places the CLI outside RBAC enforcement as a trusted path, so nothing here
authorizes its operator. Everything here **attributes**: each state change
writes an ``AuditLog`` row naming the ``Actor`` this instance was constructed
with, and an unchanged call writes nothing.
"""
from __future__ import annotations

from ..audit_writer import AuditWriter
from ..creator import Creator
from ..repositories.creator_repository import CreatorRepository
from ..utils.db_users import hash_password
from .actor import Actor
from .errors import AdminEntityNotFound

__all__ = ["AccountAdministration"]


class AccountAdministration:
    """Deactivate, reactivate, promote and re-credential accounts.

    ``actor`` and ``audit`` are required constructor state for the same reasons
    they are on ``MembershipAdministration``: it is the house style for actors,
    and a defaulted sink would be fail-open on the property this class exists
    to protect.
    """

    def __init__(
        self, creators: CreatorRepository, *, audit: AuditWriter, actor: Actor
    ) -> None:
        self._creators = creators
        self._audit = audit
        self._actor = actor

    def _creator(self, username: str) -> Creator:
        creator = self._creators.get_by_name(username)
        if creator is None:
            raise AdminEntityNotFound(
                f"no creator named {username!r}", entity="Creator"
            )
        return creator

    def deactivate(self, *, username: str) -> bool:
        """Revoke everything, without deleting the row.

        v0.3 requires that administrators can *delete* users and defines that as
        deactivation: Creator is referenced by Segmentation, FormAnnotation,
        SubTask, Task, Tag and Annotation, so a real delete either fails on the
        foreign keys or destroys the attribution that is the entire compliance
        rationale.

        Memberships are left in place, so reactivation restores the state that
        existed rather than requiring it to be rebuilt from memory.

        Deactivating the last administrator is permitted: recovery is an UPDATE
        against the database, which is access the operator running this command
        already has.
        """
        creator = self._creator(username)
        if creator.Inactive:
            return False
        creator.Inactive = True
        self._creators.save(creator)
        self._audit.write(
            actor=self._actor,
            action="UPDATE",
            entity="Creator",
            entity_id=creator.CreatorID,
            changes={"username": username, "inactive": {"old": False, "new": True}},
        )
        return True

    def reactivate(self, *, username: str) -> bool:
        creator = self._creator(username)
        if not creator.Inactive:
            return False
        creator.Inactive = False
        self._creators.save(creator)
        self._audit.write(
            actor=self._actor,
            action="UPDATE",
            entity="Creator",
            entity_id=creator.CreatorID,
            changes={"username": username, "inactive": {"old": True, "new": False}},
        )
        return True

    def set_admin(self, *, username: str, is_admin: bool) -> bool:
        """Set or clear administrator status on an existing account.

        Returns False when the account is already in the requested state, so an
        unchanged call writes no audit row -- the same idempotence rule `grant`
        follows.

        Creating is not offered: `init-admin` is the bootstrap (it create-or-
        promotes and owns the password), and this is the flip on an account that
        already exists.

        **Demoting the last administrator is permitted.** `deactivate` above
        already commits to this for the equivalent risk, and recovery here is
        strictly cheaper than it is there: `eorm init-admin --username U`
        restores administrator status from the CLI, with no database access at
        all. A guard would block a state that one documented command undoes.
        """
        creator = self._creator(username)
        if bool(creator.IsAdmin) is is_admin:
            return False
        creator.IsAdmin = is_admin
        self._creators.save(creator)
        self._audit.write(
            actor=self._actor,
            action="UPDATE",
            entity="Creator",
            entity_id=creator.CreatorID,
            changes={
                "username": username,
                "is_admin": {"old": not is_admin, "new": is_admin},
            },
        )
        return True

    def set_password(self, *, username: str, password: str) -> None:
        """Replace an existing user's password.

        Unconditional -- there is no "unchanged" case to detect. Hashing is
        salted, so re-hashing the same password yields a different string, and a
        command whose only job is to set the password has no reason to skip the
        write.

        `init-admin` owns the administrator's credential and reads
        EYENED_API_ADMIN_PASSWORD; this owns everyone else's and reads no
        environment variable at all.
        """
        creator = self._creator(username)
        creator.PasswordHash = hash_password(password)
        # check_login falls through to this legacy pbkdf2 column when PasswordHash
        # misses. Leaving it set would let the password this command is resetting
        # away from keep authenticating -- a reset that doesn't reset. Do not
        # "simplify" this away: on a row with no legacy hash it is a no-op, but on
        # one that still carries it, it is the only line that actually revokes the
        # old credential.
        creator.Password = None
        self._creators.save(creator)
        self._audit.write(
            actor=self._actor,
            action="UPDATE",
            entity="Creator",
            entity_id=creator.CreatorID,
            # Never the password and never the hash -- only that a reset occurred,
            # the same rule init-admin follows.
            changes={"username": username, "password_changed": True},
        )
