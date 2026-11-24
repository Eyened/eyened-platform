"""Who may change a set's status and comments, and which set "next" opens."""
from __future__ import annotations

import pytest

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import admin_scope, scope_for

from server.services.task_service import can_edit_status_and_comments

ME, OTHER = 1, 2
P, Q = 10, 20


@pytest.mark.parametrize(
    ("scope", "projects", "holder", "expected"),
    [
        pytest.param(scope_for(P, Q, actor_id=ME), {P, Q}, ME, True, id="my set"),
        pytest.param(scope_for(P, Q, actor_id=ME), {P, Q}, None, True, id="unclaimed"),
        pytest.param(
            scope_for(P, Q, actor_id=ME), {P, Q}, OTHER, False, id="another grader's set"
        ),
        pytest.param(
            scope_for(P, Q, role=ProjectRole.project_admin, actor_id=ME),
            {P, Q},
            OTHER,
            True,
            id="project admin in every project",
        ),
        pytest.param(
            scope_for(
                roles={P: ProjectRole.project_admin, Q: ProjectRole.grader}, actor_id=ME
            ),
            {P, Q},
            OTHER,
            False,
            id="project admin in one of two",
        ),
        pytest.param(admin_scope(actor_id=ME), {P, Q}, OTHER, True, id="global admin"),
        pytest.param(
            scope_for(P, Q, role=ProjectRole.read_only, actor_id=ME),
            {P, Q},
            None,
            False,
            id="read-only member, unclaimed",
        ),
        pytest.param(
            scope_for(P, actor_id=ME), set(), None, False, id="task declares no projects"
        ),
    ],
)
def test_who_may_change_status_and_comments(scope, projects, holder, expected):
    assert can_edit_status_and_comments(scope, projects, holder) is expected
