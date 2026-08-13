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
        """Unrestricted scope for the paths v0.3 places outside enforcement.

        Its only caller today is the pre-authentication login path in
        ``server/routes/auth.py`` -- token refresh and OIDC auto-provision,
        which must reach a Creator row before there is an actor to scope by.
        The ``eorm`` CLI and the RQ worker reach repositories without one.
        Never returned by ``get_access_scope``.

        The call sites ARE pinned to an allow-list:
        ``test_only_the_allow_listed_files_call_access_scope_trusted`` in
        ``server/tests/test_escalation_paths.py`` asserts the exact set over
        repository source, so a new caller turns the suite red rather than
        relying on review to notice it. Its sibling there guards the second
        door, ``AccessScope(..., is_admin=True)``, which a scan for this method
        cannot see. The service-factory guard additionally bans it there, which
        is the one place it would be invisible.
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

        Containment and the 404/403 split both fall out of this one method
        rather than needing separate rules.

        An empty ``project_ids`` **fails closed** for a non-administrator. Both
        comprehensions below iterate nothing, so vacuity would let any caller --
        including one with no memberships at all -- past every floor built on
        this method the moment the object it names touches no projects. v0.3
        accepts that vacuity for *visibility*, where the consequence is only
        that an empty shell is findable; carried into a write it is an
        unguarded mutation, which nothing in the spec contemplates and no
        product behaviour needs. ``NotVisibleError`` rather than
        ``PermissionDeniedError``: no floor exists that would let this caller
        past, so a 403 would confirm the row while promising nothing.
        """
        if not project_ids and not self.is_admin:
            raise NotVisibleError(
                actor_id=self.actor_id,
                entity=entity,
                entity_id=entity_id,
                projects=frozenset(),
            )
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
