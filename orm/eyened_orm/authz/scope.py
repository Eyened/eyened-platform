from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from types import MappingProxyType

from .errors import NotVisibleError, PermissionDeniedError
from .roles import ProjectRole

__all__ = ["AccessScope"]


@dataclass(frozen=True)
class AccessScope:
    """Everything one request may do, resolved once from the database.

    Not from the JWT. The token carries identity only (``sub``, ``username``);
    the admin flag and the project-role map are looked up per request. That is
    what makes v0.3's "a grant or a revocation takes effect on the user's next
    request, without them signing in again" true -- a scope baked into a token
    would linger until expiry, defeating a system whose stated job is revoking
    access on request.
    """

    actor_id: int
    username: str
    is_admin: bool
    # hash=False: a synthesized __hash__ over a Mapping raises TypeError at call
    # time, which is exactly when `functools.lru_cache` on a scope-taking helper
    # would blow up. Excluding it leaves the scope hashable on its identity
    # fields -- and that is safe precisely because __eq__ still compares
    # `roles` in full (MappingProxyType compares by content), so two scopes for
    # the same actor with different role maps share a cache bucket and are then
    # separated by equality. Dropping roles from __eq__ as well would turn this
    # into a cache-poisoning bug; do not.
    roles: Mapping[int, ProjectRole] = field(hash=False, default_factory=dict)

    def __post_init__(self) -> None:
        # frozen=True freezes the *reference*, not the dict behind it, and the
        # caller who built it otherwise keeps a live handle on a
        # security-critical object. Copy, then wrap.
        object.__setattr__(self, "roles", MappingProxyType(dict(self.roles)))

    @classmethod
    def trusted(
        cls, *, actor_id: int = 0, username: str = "trusted-path"
    ) -> "AccessScope":
        """Unrestricted scope for the non-API paths v0.3 places outside
        enforcement: the ``eorm`` CLI, RQ workers, and the pre-authentication
        login path. Never returned by ``get_access_scope``. Its call sites are
        pinned by a test -- an unbounded escape hatch needs one.
        """
        return cls(actor_id=actor_id, username=username, is_admin=True, roles={})

    def effective_role(self, project_id: int) -> ProjectRole | None:
        return ProjectRole.project_admin if self.is_admin else self.roles.get(project_id)

    @property
    def project_ids(self) -> AbstractSet[int]:
        if self.is_admin:
            # Would be the empty set: an admin holds no ProjectMember rows, so
            # any caller building a predicate from this without repeating
            # effective_role's short-circuit gives them access to *nothing*.
            raise TypeError(
                "an administrator's projects are unbounded; short-circuit instead"
            )
        return self.roles.keys()

    def require(
        self,
        project_ids: AbstractSet[int],
        floor: ProjectRole,
        *,
        entity: str,
        entity_id: int | None = None,
    ) -> None:
        """Assert the actor holds every one of ``project_ids`` at ``floor``.

        Containment, vacuity and the 404/403 split all fall out of this one
        method rather than needing separate rules. An empty ``project_ids``
        satisfies both guards trivially -- that is v0.3's accepted vacuity.
        """
        # Resolved once into a dict rather than twice through effective_role:
        # `self.effective_role(p) < floor` is a type error against a
        # `ProjectRole | None` return, and mypy is right -- narrowing here is
        # what makes the second comprehension well-typed.
        roles = {p: self.effective_role(p) for p in project_ids}
        missing = {p for p, r in roles.items() if r is None}
        if missing:
            raise NotVisibleError(
                actor_id=self.actor_id,
                entity=entity,
                entity_id=entity_id,
                projects=missing,
            )
        under = {p for p, r in roles.items() if r is not None and r < floor}
        if under:
            raise PermissionDeniedError(
                actor_id=self.actor_id,
                entity=entity,
                entity_id=entity_id,
                projects=under,
            )

    def require_admin(self, *, entity: str, entity_id: int | None = None) -> None:
        """Gate a platform-administrator action (source data, whole-database sweeps).

        403 rather than 404: the caller reached this only after the row passed
        the read scope, so it is a visible row with a refused action.
        """
        if not self.is_admin:
            raise PermissionDeniedError(
                actor_id=self.actor_id,
                entity=entity,
                entity_id=entity_id,
                projects=frozenset(),
            )
