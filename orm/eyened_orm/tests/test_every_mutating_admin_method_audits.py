"""Every mutating administration method writes an audit row; the read-only ones write none.

The constructor requires an ``Actor``, and the guard that checked for a per-call
``actor`` parameter is gone because ``__init__`` enforces it for free. Neither
covers this: a method can accept a perfectly good actor and simply forget to
write the row. That is invisible to any signature check and is exactly the
failure this whole change exists to prevent, so it is checked behaviorally.

Parametrized over the nine mutating methods, not a sample of them; the two
read-only methods each get their own dedicated test below instead. A tenth
mutating method added without a row must fail here, and adding it to the table
is how the author is made to think about it.
"""
from __future__ import annotations

import inspect

import pytest
from sqlalchemy import func, select

from eyened_orm import AuditLog
from eyened_orm.audit_writer import AuditWriter
from eyened_orm.authz.account_admin import AccountAdministration
from eyened_orm.authz.actor import TrustedPath
from eyened_orm.authz.membership_admin import MembershipAdministration, TaskGrantPlan
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.repositories import (
    CreatorRepository,
    ProjectMemberRepository,
    ProjectRepository,
    TaskRepository,
)
from eyened_orm.utils.factories import admin_scope, make_creator, make_project


@pytest.fixture()
def seeded(session):
    """One creator, one project, and both administration classes over them."""
    make_creator(session, "alice")
    project = make_project(session, "A")
    session.commit()
    project_id = project.ProjectID  # captured before the fixture returns

    scope = admin_scope()
    audit = AuditWriter(session)
    actor = TrustedPath("eorm test")
    return {
        "project_id": project_id,
        "membership": MembershipAdministration(
            CreatorRepository(session, scope=scope),
            ProjectRepository(session, scope=scope),
            ProjectMemberRepository(session),
            TaskRepository(session, scope=scope),
            audit=audit,
            actor=actor,
        ),
        "account": AccountAdministration(
            CreatorRepository(session, scope=scope), audit=audit, actor=actor
        ),
    }


def _one_project_plan(project_id: int) -> TaskGrantPlan:
    """A plan built directly rather than through `plan_grant_for_tasks`.

    What is under test here is that *applying* a plan writes rows. Building one
    the normal way needs the `spanning` task fixture, and a guard that dragged
    it in could fail for reasons that have nothing to do with the property.
    """
    return TaskGrantPlan(
        username="alice",
        task_ids=(),
        to_grant=((project_id, "A", ProjectRole.grader),),
        already_held=(),
    )


# (label, which class, arrange, act) for every state-changing method.
#
# Arrange and act are SEPARATE on purpose. Three of these methods need existing
# state to change -- you cannot revoke what was never granted -- and the arrange
# step writes audit rows of its own. A guard that only asserted "some row
# exists" after running both would pass for `revoke`, `reactivate` and
# `apply_revoke_all` even with their audit writes deleted, because the setup's
# rows satisfy it. The count is taken between the two.
_MUTATING = [
    ("grant", "membership",
     lambda a, pid: None,
     lambda a, pid: a.grant(username="alice", project_name="A", role=ProjectRole.grader)),
    ("revoke", "membership",
     lambda a, pid: a.grant(username="alice", project_name="A", role=ProjectRole.grader),
     lambda a, pid: a.revoke(username="alice", project_name="A")),
    ("grant_all", "membership",
     lambda a, pid: None,
     lambda a, pid: a.grant_all()),
    ("apply_grant_plan", "membership",
     lambda a, pid: None,
     lambda a, pid: a.apply_grant_plan(plan=_one_project_plan(pid))),
    ("apply_revoke_all", "membership",
     lambda a, pid: a.grant(username="alice", project_name="A", role=ProjectRole.grader),
     lambda a, pid: a.apply_revoke_all(
         username="alice", held=a.memberships_of(username="alice"))),
    ("deactivate", "account",
     lambda a, pid: None,
     lambda a, pid: a.deactivate(username="alice")),
    ("reactivate", "account",
     lambda a, pid: a.deactivate(username="alice"),
     lambda a, pid: a.reactivate(username="alice")),
    ("set_admin", "account",
     lambda a, pid: None,
     lambda a, pid: a.set_admin(username="alice", is_admin=True)),
    ("set_password", "account",
     lambda a, pid: None,
     lambda a, pid: a.set_password(username="alice", password="pw")),
]


def _audit_count(session) -> int:
    return session.scalar(select(func.count()).select_from(AuditLog))


def _public_method_names(cls: type) -> set[str]:
    """Methods defined directly on the class body, dunder and `_`-prefixed
    helpers excluded. `vars()`, not `dir()`/`inspect.getmembers`: those walk
    the MRO and would also report `object`'s methods on a class with none of
    its own."""
    return {
        name
        for name, value in vars(cls).items()
        if not name.startswith("_") and inspect.isfunction(value)
    }


def test_the_administration_classes_have_no_unclassified_public_method():
    """`_MUTATING` above is a hardcoded list; nothing before this test checked
    that it was exhaustive. A public method added to either class and left off
    both this file's read-only tests and the `_MUTATING` table -- audited or
    not -- fails here instead of shipping unclassified, which is what makes
    this module's docstring claim ("a tenth mutating method ... must fail
    here") actually true.
    """
    assert _public_method_names(MembershipAdministration) == {
        *(label for label, which, _, _ in _MUTATING if which == "membership"),
        "memberships_of",
        "plan_grant_for_tasks",
    }
    assert _public_method_names(AccountAdministration) == {
        label for label, which, _, _ in _MUTATING if which == "account"
    }


@pytest.mark.parametrize(
    "label,which,arrange,act", _MUTATING, ids=[m[0] for m in _MUTATING]
)
def test_every_mutating_method_writes_an_audit_row(
    session, seeded, label, which, arrange, act
):
    """Nine methods, no sample. Accepting an Actor and then not writing the row
    passes every signature check there is, and the constructor cannot see it.

    The assertion is on the *delta*, not on "a row exists": the arrange step
    writes rows for the three methods that need existing state, and an absolute
    check would be satisfied by those alone.
    """
    admin, project_id = seeded[which], seeded["project_id"]
    arrange(admin, project_id)
    session.flush()
    before = _audit_count(session)

    act(admin, project_id)
    session.flush()

    assert _audit_count(session) > before, f"{label} wrote no audit row"


def test_the_read_only_methods_write_nothing(session, seeded):
    """The negative direction. A read that started writing rows would inflate
    the audit trail with events that never happened, and only this catches it.

    `plan_grant_for_tasks` is the other read-only method; it needs the
    `spanning` task fixture, which builds its own project "A" and collides
    with this fixture's, so it is covered separately by
    `test_plan_grant_for_tasks_writes_nothing` below instead of here.
    """
    before = _audit_count(session)
    seeded["membership"].memberships_of(username="alice")
    session.flush()
    assert _audit_count(session) == before


def test_plan_grant_for_tasks_writes_nothing(session, spanning):
    """The other read-only method. It cannot share `seeded`: `spanning`
    creates its own project "A" (ProjectName is unique), so this gets its own
    arrange instead of reusing that fixture.

    The call must land on the real success path, not just raise past
    `AdminEntityNotFound` -- a call that errors before reaching any point
    where a write could occur would prove nothing about whether one happens.
    `spanning`'s task touches two projects that alice holds no membership in,
    so a correct call returns a plan with both in `to_grant`; asserting that
    is what shows the resolution work actually ran before the audit count is
    checked.
    """
    make_creator(session, "alice")
    session.commit()

    scope = admin_scope()
    admin = MembershipAdministration(
        CreatorRepository(session, scope=scope),
        ProjectRepository(session, scope=scope),
        ProjectMemberRepository(session),
        TaskRepository(session, scope=scope),
        audit=AuditWriter(session),
        actor=TrustedPath("eorm test"),
    )

    before = _audit_count(session)
    plan = admin.plan_grant_for_tasks(
        username="alice", task_ids=[spanning["task"]], role=ProjectRole.grader
    )
    session.flush()

    assert {name for _, name, _ in plan.to_grant} == {"A", "B"}, (
        "plan resolved no projects -- success path not reached"
    )
    assert _audit_count(session) == before
