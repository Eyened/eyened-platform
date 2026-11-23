"""Feature and tag writes need Grader or above in some project, or administrator."""
from __future__ import annotations

import pytest

from eyened_orm import Creator, Feature, Tag
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.tag import TagType
from eyened_orm.utils.factories import make_project, scope_for


# The three Accounts: no project role, read_only only, and a Grader in a
# project the feature or tag has nothing to do with (the control).
ACCOUNTS = [
    pytest.param("none", 403, id="no-access"),
    pytest.param(ProjectRole.read_only, 403, id="read-only"),
    pytest.param(ProjectRole.grader, None, id="grader-elsewhere"),
]


@pytest.fixture()
def act_as(session, client_scoped):
    """Seed the acting Creator and return a client scoped to ``role``."""
    client, set_scope = client_scoped
    creator = Creator(CreatorName="alice", IsHuman=True)
    session.add(creator)
    session.commit()
    project_id = make_project(session, "Unrelated").ProjectID
    session.commit()

    def _act_as(role):
        roles = {} if role == "none" else {project_id: role}
        set_scope(scope_for(roles=roles, actor_id=creator.CreatorID))
        return client

    _act_as.creator_id = creator.CreatorID
    return _act_as


def _feature(session) -> int:
    feature = Feature(FeatureName="F1")
    session.add(feature)
    session.commit()
    return feature.FeatureID


def _tag(session, creator_id: int) -> int:
    tag = Tag(TagName="T1", TagType=TagType.Study, TagDescription="", CreatorID=creator_id)
    session.add(tag)
    session.commit()
    return tag.TagID


@pytest.mark.parametrize("role, denied", ACCOUNTS)
def test_create_feature(act_as, role, denied):
    resp = act_as(role).post("/features", json={"name": "F2"})
    assert resp.status_code == (denied or 200), resp.text


@pytest.mark.parametrize("role, denied", ACCOUNTS)
def test_rename_feature(session, act_as, role, denied):
    feature_id = _feature(session)
    resp = act_as(role).patch(f"/features/{feature_id}", json={"name": "renamed"})
    assert resp.status_code == (denied or 200), resp.text


@pytest.mark.parametrize("role, denied", ACCOUNTS)
def test_delete_feature(session, act_as, role, denied):
    feature_id = _feature(session)
    resp = act_as(role).delete(f"/features/{feature_id}")
    assert resp.status_code == (denied or 204), resp.text


@pytest.mark.parametrize("role, denied", ACCOUNTS)
def test_create_tag(act_as, role, denied):
    resp = act_as(role).post(
        "/tags", json={"name": "T2", "tag_type": "Study", "description": ""}
    )
    assert resp.status_code == (denied or 200), resp.text


@pytest.mark.parametrize("role, denied", ACCOUNTS)
def test_rename_tag(session, act_as, role, denied):
    tag_id = _tag(session, act_as.creator_id)
    resp = act_as(role).patch(f"/tags/{tag_id}", json={"name": "renamed"})
    assert resp.status_code == (denied or 200), resp.text


@pytest.mark.parametrize("path", ["/features", "/tags"])
def test_no_access_account_still_reads(act_as, path):
    assert act_as("none").get(path).status_code == 200


def test_no_access_account_still_stars_a_tag(session, act_as):
    tag_id = _tag(session, act_as.creator_id)
    assert act_as("none").post(f"/tags/{tag_id}/star").status_code == 204
