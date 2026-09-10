"""Project reads for the administration path.

`get_by_name` is a passthrough over a scoped select and is covered by the
administration tests that use it. What is tested here is the part with logic:
the bulk name lookup, and the fail-closed scope behavior that a decorative
`scope` parameter would hide.
"""
from __future__ import annotations

import pytest

from eyened_orm.repositories import ProjectRepository
from eyened_orm.utils.factories import admin_scope, make_project, scope_for


def test_names_for_returns_the_pairs_in_one_lookup(session):
    a = make_project(session, "A")
    b = make_project(session, "B")
    session.commit()

    repo = ProjectRepository(session, scope=admin_scope())
    assert repo.names_for([a.ProjectID, b.ProjectID]) == {
        a.ProjectID: "A",
        b.ProjectID: "B",
    }


def test_names_for_no_ids_queries_nothing_and_returns_empty(session):
    """The callers pass a set that can legitimately be empty (a task touching
    no projects), and an empty IN is a query with a knowable answer."""
    assert ProjectRepository(session, scope=admin_scope()).names_for([]) == {}


def test_all_ids_lists_every_project_for_the_cutover_grant(session):
    a = make_project(session, "A")
    b = make_project(session, "B")
    session.commit()

    assert ProjectRepository(session, scope=admin_scope()).all_ids() == sorted(
        [a.ProjectID, b.ProjectID]
    )


def test_a_non_admin_scope_fails_closed_rather_than_reading_unfiltered(session):
    """Project is in none of scoping.py's three registries, so apply_scope
    raises for any scope it cannot short-circuit. That is the designed
    behavior: a repository that took a scope and ignored it would look filtered
    while returning every row. Registering Project is what would change this,
    and that is a read-policy decision, not part of this refactor.
    """
    project = make_project(session, "A")
    session.commit()

    repo = ProjectRepository(session, scope=scope_for(project.ProjectID))
    with pytest.raises(KeyError, match="Project"):
        repo.get_by_name("A")
