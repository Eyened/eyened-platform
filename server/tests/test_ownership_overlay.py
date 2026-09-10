"""The overlay is wired: modify calls require_owner, delete calls the other one.

The unit tests in ``orm/eyened_orm/tests/test_authz_ownership.py`` pin *what*
the overlay decides. This file pins that every annotation mutation actually
calls it, and calls the right one -- one case per enforcement statement, because
Task 15's first review found three of six floors shipping green when deleted.

Each table below is written so that exactly one check can refuse the request:

* ``_FLOORS`` acts as the row's **own author**, so the ownership overlay passes
  by construction and only the role floor is left to say no.
* ``_MODIFY`` and ``_DELETE`` act on a **stranger's** row with a role that
  clears the floor, so only the overlay is left to say no.
* ``_DELETE`` run again as ``project_admin`` must *succeed*, which is what
  separates ``require_owner_or_project_admin`` from ``require_owner``.

An actor who simply cannot *see* the row would prove none of this -- the
visibility filter would answer first. Note also that no assertion follows a 4xx
status assertion here: ``get_db`` rolls back on the raised authorization error
and the write is never attempted, so "the row is unchanged" could not fail.
"""
from __future__ import annotations

import io
import json

import numpy as np
import pytest

from eyened_orm.authz.roles import ProjectRole
from eyened_orm.utils.factories import admin_scope, scope_for


@pytest.fixture()
def owned(session):
    """One project holding every annotation shape twice: once authored by the
    acting user, once by a stranger.

    Both halves are load-bearing and neither substitutes for the other -- see
    the module docstring. ``Study`` and ``ImageInstance`` get *two* tags each
    rather than two rows, because a tag link's primary key is
    ``(TagID, parent id)`` and there is only one study and one image here.
    """
    from datetime import date

    from eyened_orm import (
        FormAnnotationTagLink,
        ImageInstanceTagLink,
        SegmentationTagLink,
        StudyTagLink,
    )
    from eyened_orm.tag import TagType
    from eyened_orm.utils.factories import (
        make_creator,
        make_device,
        make_feature,
        make_form_annotation,
        make_form_schema,
        make_image,
        make_patient,
        make_project,
        make_segmentation,
        make_series,
        make_storage_backend,
        make_study,
        make_tag,
    )

    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project = make_project(session, "P")
    patient = make_patient(session, project, "pat")
    study = make_study(session, patient, date(2024, 1, 1))
    series = make_series(session, study)
    image = make_image(session, series, device, backend, "img")
    feature = make_feature(session, "feat")
    schema = make_form_schema(session, "schema")

    actor = make_creator(session, "actor")
    other = make_creator(session, "other")

    segmentations = {
        "own": make_segmentation(session, image, feature, actor),
        "foreign": make_segmentation(session, image, feature, other),
    }
    annotations = {
        "own": make_form_annotation(session, schema, patient, actor, image=image),
        "foreign": make_form_annotation(session, schema, patient, other, image=image),
    }

    seg_tag = make_tag(session, "seg", TagType.Segmentation, other)
    seg_tag_free = make_tag(session, "seg-free", TagType.Segmentation, other)
    form_tag = make_tag(session, "form", TagType.FormAnnotation, other)
    form_tag_free = make_tag(session, "form-free", TagType.FormAnnotation, other)
    study_tags = {
        who: make_tag(session, f"study-{who}", TagType.Study, other)
        for who in ("own", "foreign")
    }
    study_tag_free = make_tag(session, "study-free", TagType.Study, other)
    image_tags = {
        who: make_tag(session, f"image-{who}", TagType.ImageInstance, other)
        for who in ("own", "foreign")
    }
    image_tag_free = make_tag(session, "image-free", TagType.ImageInstance, other)

    authors = {"own": actor, "foreign": other}
    for who, author in authors.items():
        session.add(
            SegmentationTagLink(
                SegmentationID=segmentations[who].SegmentationID,
                TagID=seg_tag.TagID,
                CreatorID=author.CreatorID,
            )
        )
        session.add(
            FormAnnotationTagLink(
                FormAnnotationID=annotations[who].FormAnnotationID,
                TagID=form_tag.TagID,
                CreatorID=author.CreatorID,
            )
        )
        session.add(
            StudyTagLink(
                StudyID=study.StudyID,
                TagID=study_tags[who].TagID,
                CreatorID=author.CreatorID,
            )
        )
        session.add(
            ImageInstanceTagLink(
                ImageInstanceID=image.ImageInstanceID,
                TagID=image_tags[who].TagID,
                CreatorID=author.CreatorID,
            )
        )

    # A link whose CreatorID differs from its parent row's -- the loop above
    # always makes them match, so on its own it cannot tell ``untag``'s
    # ownership argument (the link's author) apart from the parent's. This
    # tag links to the *own* segmentation/annotation (parent author: actor)
    # but the link itself is authored by ``other``.
    seg_tag_mismatched_owner = make_tag(
        session, "seg-mismatched-owner", TagType.Segmentation, other
    )
    session.add(
        SegmentationTagLink(
            SegmentationID=segmentations["own"].SegmentationID,
            TagID=seg_tag_mismatched_owner.TagID,
            CreatorID=other.CreatorID,
        )
    )
    form_tag_mismatched_owner = make_tag(
        session, "form-mismatched-owner", TagType.FormAnnotation, other
    )
    session.add(
        FormAnnotationTagLink(
            FormAnnotationID=annotations["own"].FormAnnotationID,
            TagID=form_tag_mismatched_owner.TagID,
            CreatorID=other.CreatorID,
        )
    )
    session.flush()

    # Read every id out before the commit: expire_on_commit=True, and an
    # expired instance re-loads through whatever session the test later has.
    data = {
        "project": project.ProjectID,
        "actor": actor.CreatorID,
        "other": other.CreatorID,
        "patient": patient.PatientID,
        "study": study.StudyID,
        "image": image.PublicID,
        "feature": feature.FeatureID,
        "schema": schema.FormSchemaID,
        "segmentation": {k: v.SegmentationID for k, v in segmentations.items()},
        "annotation": {k: v.FormAnnotationID for k, v in annotations.items()},
        "seg_tag": seg_tag.TagID,
        "seg_tag_free": seg_tag_free.TagID,
        "form_tag": form_tag.TagID,
        "form_tag_free": form_tag_free.TagID,
        "study_tag": {k: v.TagID for k, v in study_tags.items()},
        "study_tag_free": study_tag_free.TagID,
        "image_tag": {k: v.TagID for k, v in image_tags.items()},
        "image_tag_free": image_tag_free.TagID,
        "seg_tag_mismatched_owner": seg_tag_mismatched_owner.TagID,
        "form_tag_mismatched_owner": form_tag_mismatched_owner.TagID,
    }
    session.commit()
    return data


@pytest.fixture()
def foreign_segmentation(owned):
    """The brief's two named tests read a stranger's segmentation and its project."""
    return {"id": owned["segmentation"]["foreign"], "project": owned["project"]}


@pytest.fixture()
def tag_pair(session, owned):
    """Two tags with no project of their own and no link to anything: one
    owned by ``owned``'s actor, one by its stranger.

    ``Tag`` is deliberately absent from ``PROJECT_IDS_OF`` (see
    ``orm/eyened_orm/authz/scoping.py``) -- a tag carries no project of its
    own -- so ``delete_tag`` binds purely on ownership, and ``update_tag``
    binds on nothing at all. These
    tags stay unlinked to any study/image/segmentation/annotation so nothing
    about "which project can see this tag" is in play; ``owned["project"]``
    is used only as *the actor's* membership, to hold a role that must not
    matter.

    That promise is load-bearing for the tests below, so cases that need a
    tag *with* links use ``linked_tag`` instead of reaching in here.
    """
    from eyened_orm import Tag
    from eyened_orm.tag import TagType

    own = Tag(
        TagName="own-plain", TagType=TagType.Study, TagDescription="",
        CreatorID=owned["actor"],
    )
    foreign = Tag(
        TagName="foreign-plain", TagType=TagType.Study, TagDescription="",
        CreatorID=owned["other"],
    )
    session.add_all([own, foreign])
    session.flush()
    ids = {"own": own.TagID, "foreign": foreign.TagID}
    session.commit()
    return ids


@pytest.fixture()
def linked_tag(session, owned):
    """One stranger-authored tag that IS applied to ``owned``'s study.

    Deliberately not folded into ``tag_pair``: that fixture promises unlinked
    tags and other tests rest on the promise. The link is what makes this tag
    *resolvable* to a project (``StudyTagLink -> Study -> Patient.ProjectID``
    reaches ``owned["project"]``) and what makes deleting it hit the
    ``RESTRICT`` on ``StudyTag.TagID`` -- so a ``delete_tag`` that resolved a
    project set instead of passing the empty one, or that authorized after
    attempting the delete, would both be visible against it.
    """
    from eyened_orm import StudyTagLink, Tag
    from eyened_orm.tag import TagType

    tag = Tag(
        TagName="linked-foreign", TagType=TagType.Study, TagDescription="",
        CreatorID=owned["other"],
    )
    session.add(tag)
    session.flush()
    session.add(
        StudyTagLink(
            StudyID=owned["study"], TagID=tag.TagID, CreatorID=owned["other"]
        )
    )
    session.flush()
    # Read the id out before the commit: expire_on_commit=True.
    tag_id = tag.TagID
    session.commit()
    return tag_id


def _npy_body() -> bytes:
    """A 1x4x4 uint8 .npy payload matching the fixture image's shape."""
    buffer = io.BytesIO()
    np.save(buffer, np.zeros((1, 4, 4), dtype=np.uint8))
    return buffer.getvalue()


def _send(client, spec):
    """Issue one case-table request. ``spec`` is (method, url, kwargs)."""
    method, url, kwargs = spec
    return client.request(method, url, **kwargs)


# --- The case tables -------------------------------------------------------
#
# Each entry is name -> f(data, who) -> (method, url, httpx kwargs). ``who``
# selects the own-authored or the stranger-authored row, so one table serves
# both the floor pass (own) and the overlay pass (foreign).

# Every mutation whose role floor is a statement of its own. Keys that end in
# ``_create`` have no ownership dimension -- the row does not exist yet -- so
# they appear here and nowhere else.
_FLOORS = {
    "segmentation_create": lambda d, who: (
        "POST",
        "/segmentations",
        {
            "data": {
                "metadata": json.dumps(
                    {
                        "image_id": d["image"],
                        "depth": 1,
                        "height": 4,
                        "width": 4,
                        "data_type": "R8UI",
                        "data_representation": "Binary",
                        "feature_id": d["feature"],
                    }
                )
            }
        },
    ),
    "segmentation_data": lambda d, who: (
        "PUT",
        f"/segmentations/{d['segmentation'][who]}/data",
        {
            "content": _npy_body(),
            "headers": {"Content-Type": "application/octet-stream"},
        },
    ),
    "segmentation_patch": lambda d, who: (
        "PATCH",
        f"/segmentations/{d['segmentation'][who]}",
        {"json": {"threshold": 0.5}},
    ),
    "segmentation_delete": lambda d, who: (
        "DELETE",
        f"/segmentations/{d['segmentation'][who]}",
        {},
    ),
    "segmentation_tag_create": lambda d, who: (
        "POST",
        f"/segmentations/{d['segmentation'][who]}/tags",
        {"json": {"tag_id": d["seg_tag_free"]}},
    ),
    "segmentation_untag": lambda d, who: (
        "DELETE",
        f"/segmentations/{d['segmentation'][who]}/tags/{d['seg_tag']}",
        {},
    ),
    "form_annotation_create": lambda d, who: (
        "POST",
        "/form-annotations",
        {
            "json": {
                "form_schema_id": d["schema"],
                "patient_id": d["patient"],
                "form_data": {"a": 1},
            }
        },
    ),
    "form_annotation_patch": lambda d, who: (
        "PATCH",
        f"/form-annotations/{d['annotation'][who]}",
        {"json": {"form_data": {"b": 2}}},
    ),
    "form_annotation_value": lambda d, who: (
        "PUT",
        f"/form-annotations/{d['annotation'][who]}/value",
        {"json": {"c": 3}},
    ),
    "form_annotation_delete": lambda d, who: (
        "DELETE",
        f"/form-annotations/{d['annotation'][who]}",
        {},
    ),
    "form_annotation_tag_create": lambda d, who: (
        "POST",
        f"/form-annotations/{d['annotation'][who]}/tags",
        {"json": {"tag_id": d["form_tag_free"]}},
    ),
    "form_annotation_tag_patch": lambda d, who: (
        "PATCH",
        f"/form-annotations/{d['annotation'][who]}/tags/{d['form_tag']}",
        {"json": {"comment": "rewritten"}},
    ),
    "form_annotation_untag": lambda d, who: (
        "DELETE",
        f"/form-annotations/{d['annotation'][who]}/tags/{d['form_tag']}",
        {},
    ),
    "study_tag_create": lambda d, who: (
        "POST",
        f"/studies/{d['study']}/tags",
        {"json": {"tag_id": d["study_tag_free"]}},
    ),
    "study_tag_patch": lambda d, who: (
        "PATCH",
        f"/studies/{d['study']}/tags/{d['study_tag'][who]}",
        {"json": {"comment": "rewritten"}},
    ),
    "study_untag": lambda d, who: (
        "DELETE",
        f"/studies/{d['study']}/tags/{d['study_tag'][who]}",
        {},
    ),
    "instance_tag_create": lambda d, who: (
        "POST",
        f"/instances/{d['image']}/tags",
        {"json": {"tag_id": d["image_tag_free"]}},
    ),
    "instance_tag_patch": lambda d, who: (
        "PATCH",
        f"/instances/{d['image']}/tags/{d['image_tag'][who]}",
        {"json": {"comment": "rewritten"}},
    ),
    "instance_untag": lambda d, who: (
        "DELETE",
        f"/instances/{d['image']}/tags/{d['image_tag'][who]}",
        {},
    ),
}

# Mutations that rewrite an existing row or link: ``require_owner``. The three
# ``_tag_post_comment`` entries are POST, not PATCH, on purpose -- the create
# handlers fall through to an "update the comment" branch when the link already
# exists, which is a modify wearing a create's verb and would otherwise be a
# standing bypass of the PATCH check beside it.
_MODIFY = {
    key: _FLOORS[key]
    for key in (
        "segmentation_data",
        "segmentation_patch",
        "form_annotation_patch",
        "form_annotation_value",
        "form_annotation_tag_patch",
        "study_tag_patch",
        "instance_tag_patch",
    )
}
_MODIFY.update(
    {
        "form_annotation_tag_post_comment": lambda d, who: (
            "POST",
            f"/form-annotations/{d['annotation'][who]}/tags",
            {"json": {"tag_id": d["form_tag"], "comment": "rewritten"}},
        ),
        "study_tag_post_comment": lambda d, who: (
            "POST",
            f"/studies/{d['study']}/tags",
            {"json": {"tag_id": d["study_tag"][who], "comment": "rewritten"}},
        ),
        "instance_tag_post_comment": lambda d, who: (
            "POST",
            f"/instances/{d['image']}/tags",
            {"json": {"tag_id": d["image_tag"][who], "comment": "rewritten"}},
        ),
    }
)

# Mutations that remove a row or link: ``require_owner_or_project_admin``.
_DELETE = {
    key: _FLOORS[key]
    for key in (
        "segmentation_delete",
        "segmentation_untag",
        "form_annotation_delete",
        "form_annotation_untag",
        "study_untag",
        "instance_untag",
    )
}
# The two cases above target the ``own``/``foreign`` row-authored links, where
# a tag link's own author always matches its parent row's -- so they cannot
# tell ``untag``'s ``owner_id=link.CreatorID`` apart from a parent-authored
# stand-in. These two add a link on the *own* row authored by ``other``: the
# actor owns the parent segmentation/annotation but did not create the link,
# so ``require_owner_or_project_admin`` must still refuse a mere grader.
_DELETE.update(
    {
        "segmentation_untag_link_owned_by_other": lambda d, who: (
            "DELETE",
            f"/segmentations/{d['segmentation']['own']}"
            f"/tags/{d['seg_tag_mismatched_owner']}",
            {},
        ),
        "form_annotation_untag_link_owned_by_other": lambda d, who: (
            "DELETE",
            f"/form-annotations/{d['annotation']['own']}"
            f"/tags/{d['form_tag_mismatched_owner']}",
            {},
        ),
    }
)


# --- The brief's two named cases -------------------------------------------
#
# Deliberately kept alongside the tables even though ``_MODIFY`` and the
# project-admin half of ``_DELETE`` re-run the same two requests: these are the
# cases the task was specified in terms of, and they read as prose where a
# parametrize id does not.


def test_an_administrator_cannot_modify_another_users_segmentation(
    client_scoped, foreign_segmentation
):
    """`require_owner` on the modify path -- an admin scope is the strongest
    thing that must still be refused, so it fails if the call is missing."""
    client, set_scope = client_scoped
    set_scope(admin_scope(actor_id=1))
    resp = client.patch(
        f"/segmentations/{foreign_segmentation['id']}", json={"threshold": 0.5}
    )
    assert resp.status_code == 403


def test_a_project_admin_can_delete_another_users_segmentation(
    client_scoped, foreign_segmentation
):
    """`require_owner_or_project_admin` on the delete path -- it would 403 if
    delete reused the modify helper."""
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            foreign_segmentation["project"],
            role=ProjectRole.project_admin,
            actor_id=1,
        )
    )
    assert client.delete(
        f"/segmentations/{foreign_segmentation['id']}"
    ).status_code == 204


# --- TagService: delete binds on ownership, update does not ----------------
#
# A Tag carries no project of its own (see the ``tag_pair`` fixture): it is
# deliberately absent from both ``_PARENT_OF`` and ``PROJECT_IDS_OF``, so the
# one check here passes ``projects=frozenset()``. The two verbs deliberately
# differ:
#
# ``delete_tag`` calls ``require_owner_or_project_admin`` over that empty set,
# which ``AccessScope.require``'s fail-closed guard turns into a 404 for every
# non-owner except an administrator.
#
# ``update_tag`` has no check at all. A tag *definition* is application-wide
# data, not an annotation -- applying a tag is the annotation, and those links
# are guarded above -- so renaming a shared label is unrestricted (§4.3). The
# two "can update" cases below are the positive pin on that decision: put the
# ownership overlay back on this path and they fail.
#
# The refused actors below hold project_admin in ``owned["project"]``, a real
# membership, so a refusal can only be coming from ownership -- an actor with
# no role anywhere would prove nothing (the same trap the module docstring
# warns about for visibility).


def test_the_owner_can_update_their_tag(client_scoped, owned, tag_pair):
    """No role floor exists on a Tag: read_only is enough to rename one."""
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            owned["project"], role=ProjectRole.read_only, actor_id=owned["actor"]
        )
    )
    resp = client.patch(f"/tags/{tag_pair['own']}", json={"name": "renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed"


def test_a_project_admin_can_update_another_users_tag(client_scoped, owned, tag_pair):
    """Renaming a shared label is unrestricted -- a tag definition is
    application-wide data, so authorship does not bind on this path."""
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            owned["project"], role=ProjectRole.project_admin, actor_id=owned["actor"]
        )
    )
    resp = client.patch(f"/tags/{tag_pair['foreign']}", json={"name": "renamed"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "renamed"


def test_an_administrator_can_update_another_users_tag(client_scoped, owned, tag_pair):
    """Bound to ownership instead, a label whose author is deactivated would be
    un-renameable by everyone -- administrators are not a special case here
    because there is no check on this path to except them from."""
    client, set_scope = client_scoped
    set_scope(admin_scope(actor_id=owned["actor"]))
    resp = client.patch(f"/tags/{tag_pair['foreign']}", json={"name": "renamed"})
    assert resp.status_code == 200, resp.text


def test_the_owner_can_delete_their_tag(client_scoped, owned, tag_pair):
    """`require_owner_or_project_admin`'s ownership clause returns early for
    the author, no role needed."""
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            owned["project"], role=ProjectRole.read_only, actor_id=owned["actor"]
        )
    )
    assert client.delete(f"/tags/{tag_pair['own']}").status_code == 204


def test_a_project_admin_cannot_delete_another_users_tag(
    client_scoped, owned, tag_pair
):
    """A non-owner is refused even holding project_admin somewhere: the empty
    project set fails closed for every non-administrator, so this is a 404 --
    while the same actor renaming the same tag above succeeds."""
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            owned["project"], role=ProjectRole.project_admin, actor_id=owned["actor"]
        )
    )
    assert client.delete(f"/tags/{tag_pair['foreign']}").status_code == 404


def test_an_administrator_can_delete_another_users_tag(client_scoped, owned, tag_pair):
    """The empty-set guard's `is_admin` arm lets an administrator through
    without a separate ownership case, so delete has an escape hatch for a
    label whose author can no longer act. Rename needs none: it has no check."""
    client, set_scope = client_scoped
    set_scope(admin_scope(actor_id=owned["actor"]))
    assert client.delete(f"/tags/{tag_pair['foreign']}").status_code == 204


def test_a_project_admin_cannot_delete_a_linked_tag_they_do_not_own(
    client_scoped, owned, linked_tag
):
    """``projects=frozenset()`` is the decision, and the check runs *before* the
    delete: a non-owner project_admin -- holding that role in the very project
    this tag's link resolves to -- still gets a bare 404, never the 409 that
    would tell them the tag exists, is in use, and is called what it is."""
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            owned["project"], role=ProjectRole.project_admin, actor_id=owned["actor"]
        )
    )
    resp = client.delete(f"/tags/{linked_tag}")
    assert resp.status_code == 404, resp.text
    assert resp.json() == {"detail": "Not found"}


# --- One case per enforcement statement ------------------------------------


@pytest.mark.parametrize("case", sorted(_FLOORS))
def test_a_read_only_member_cannot_mutate_their_own_annotation(
    client_scoped, owned, case
):
    """Every role floor, on a row the actor owns and can fully see.

    Ownership passes by construction and the project is visible, so neither the
    overlay nor the read filter can be what refuses -- only ``ProjectRole.grader``
    stands between this request and the write. Delete any one floor and its
    case here turns 2xx.
    """
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            owned["project"], role=ProjectRole.read_only, actor_id=owned["actor"]
        )
    )
    assert _send(client, _FLOORS[case](owned, "own")).status_code == 403


@pytest.mark.parametrize("case", sorted(_MODIFY))
def test_an_administrator_cannot_modify_another_users_row(client_scoped, owned, case):
    """Every ``require_owner``, probed with the strongest scope there is.

    An administrator sees every project and clears every floor, so the overlay
    is the only thing that can refuse -- which is exactly what makes this fail
    when the call is deleted.
    """
    client, set_scope = client_scoped
    set_scope(admin_scope(actor_id=owned["actor"]))
    assert _send(client, _MODIFY[case](owned, "foreign")).status_code == 403


@pytest.mark.parametrize("case", sorted(_DELETE))
def test_a_grader_cannot_delete_another_users_row(client_scoped, owned, case):
    """Every ``require_owner_or_project_admin``, from under its role clause.

    ``grader`` clears the floor and holds the only project involved, so the
    request dies on the ownership clause alone.
    """
    client, set_scope = client_scoped
    set_scope(
        scope_for(owned["project"], role=ProjectRole.grader, actor_id=owned["actor"])
    )
    assert _send(client, _DELETE[case](owned, "foreign")).status_code == 403


@pytest.mark.parametrize("case", sorted(_DELETE))
def test_a_project_admin_can_delete_another_users_row(client_scoped, owned, case):
    """The other half: a delete must NOT be using the modify helper.

    Same request as the case above with the role raised one step. Swap any of
    these call sites to ``require_owner`` and this turns 403 -- the mutation the
    grader case cannot see, because ``require_owner`` refuses both roles alike.
    """
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            owned["project"], role=ProjectRole.project_admin, actor_id=owned["actor"]
        )
    )
    assert _send(client, _DELETE[case](owned, "foreign")).status_code in (200, 204)
