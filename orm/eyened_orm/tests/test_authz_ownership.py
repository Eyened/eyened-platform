"""The ownership overlay: not role-derived, and it binds administrators too."""
from __future__ import annotations

import pytest

from eyened_orm.authz.errors import NotVisibleError, PermissionDeniedError
from eyened_orm.authz.ownership import require_owner, require_owner_or_project_admin
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.authz.scope import AccessScope

ALICE = AccessScope(
    actor_id=7, username="alice", is_admin=False,
    roles={1: ProjectRole.project_admin},
)
ROOT = AccessScope(actor_id=1, username="root", is_admin=True, roles={})


def test_the_owner_may_modify():
    require_owner(ALICE, owner_id=7, entity="Segmentation", entity_id=5, projects={1})


def test_a_project_admin_may_not_modify_another_users_annotation():
    with pytest.raises(PermissionDeniedError):
        require_owner(ALICE, owner_id=99, entity="Segmentation", entity_id=5, projects={1})


def test_an_administrator_may_not_modify_another_users_annotation():
    """v0.3's 'modify other users' annotations' is a cross for all three roles."""
    with pytest.raises(PermissionDeniedError):
        require_owner(ROOT, owner_id=99, entity="Segmentation", entity_id=5, projects={1})


def test_a_null_author_is_modifiable_by_nobody():
    """Attribution-only creators (Consensus, RETOUCH-MUW, ...) hold no credentials.

    Their work, and any deactivated user's, is permanently unmodifiable.
    Deletion remains, and only for project_admin. Bulk correction of imported
    material is a CLI job, which v0.3 places outside enforcement.
    """
    with pytest.raises(PermissionDeniedError):
        require_owner(ROOT, owner_id=None, entity="Segmentation", entity_id=5, projects={1})


def test_a_project_admin_may_delete_another_users_annotation():
    require_owner_or_project_admin(
        ALICE, owner_id=99, entity="Segmentation", entity_id=5, projects={1}
    )


def test_the_author_may_delete_their_own_annotation():
    """The delete helper's *ownership* clause, which its role clause hides.

    Not in the plan's list, and the omission was load-bearing: a grader
    deleting a row they authored is the only shape that reads this clause --
    every other case here either fails the role clause or is satisfied by it.
    Verified by mutation: without this test, deleting
    ``if owner_id == scope.actor_id: return`` outright leaves the whole suite
    green, and a grader silently loses the right to delete their own work.
    """
    grader = AccessScope(
        actor_id=7, username="alice", is_admin=False, roles={1: ProjectRole.grader}
    )
    require_owner_or_project_admin(
        grader, owner_id=7, entity="Segmentation", entity_id=5, projects={1}
    )


def test_a_grader_may_not_delete_another_users_annotation():
    grader = AccessScope(
        actor_id=7, username="alice", is_admin=False, roles={1: ProjectRole.grader}
    )
    with pytest.raises(PermissionDeniedError):
        require_owner_or_project_admin(
            grader, owner_id=99, entity="Segmentation", entity_id=5, projects={1}
        )


def test_an_administrator_may_delete_another_users_annotation():
    """Satisfied by the empty-set guard's ``is_admin`` arm, or by
    ``effective_role``'s short-circuit -- which one depends on whether the
    entity resolved to any projects. Here it resolved to one, so it is the
    latter."""
    require_owner_or_project_admin(
        ROOT, owner_id=99, entity="Segmentation", entity_id=5, projects={1}
    )


def test_a_non_owner_cannot_delete_an_annotation_that_touches_no_projects():
    """Pins Task 15 Step 3a's fail-closed empty set reaching the delete helper.

    ``require`` used to treat an empty ``projects`` as vacuously true, so this
    call passed for any authenticated caller; it now raises ``NotVisibleError``
    (404) before any role is consulted. The plan's original test list has no
    such case because it was written while the empty set was still vacuous.
    """
    with pytest.raises(NotVisibleError):
        require_owner_or_project_admin(
            ALICE, owner_id=99, entity="Segmentation", entity_id=5, projects=set()
        )


def test_an_administrator_still_deletes_an_annotation_that_touches_no_projects():
    """The other half of Step 3a's contract: fail-closed must not lock the data
    superuser out. This is the arm that never reaches ``effective_role``."""
    require_owner_or_project_admin(
        ROOT, owner_id=99, entity="Segmentation", entity_id=5, projects=set()
    )
