"""``ModelSegmentation`` is the deliberate hole in the Task 16 ownership overlay.

The overlay reads "deny unless ``CreatorID == actor_id``". ``ModelSegmentation``
carries no ``CreatorID`` (``orm/eyened_orm/segmentation.py``: the column at the
concrete sibling ``Segmentation`` has no counterpart on the model side), so a
NULL author matches nobody and applying the overlay here would deny *every*
actor forever -- including the grader correcting model output on the live
``PUT /model-segmentations/{id}/data`` endpoint. The write is therefore gated by
scope plus ``grader`` and **nothing else**, and because the row cannot carry its
author, the audit trail has to.

The three route cases below are the three answers that gate can give -- 200,
403, 404 -- and the fourth test pins the compensation. The three route cases
take ``fake_store`` so a gate that regresses into actually running the write
hits an in-memory fake rather than the filesystem; only the 200 case reaches
it. The service-level audit case builds its own ``FakeSegmentationDataStore``
inline instead, since it never goes through the route or the factory.
"""
from __future__ import annotations

import io
from datetime import date

import numpy as np
import pytest
from sqlalchemy import select

from eyened_orm import AuditLog, ModelSegmentation
from eyened_orm.authz.roles import ProjectRole
from eyened_orm.repositories.segmentation_repository import (
    ModelSegmentationRepository,
)
from eyened_orm.segmentation import (
    DataRepresentation,
    Datatype,
    SegmentationModel,
)
from eyened_orm.utils.factories import (
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
    scope_for,
)

import server.services.segmentation_service as segmentation_service
from server.services.audit_service import AuditService
from server.services.segmentation_service import ModelSegmentationService
from server.tests.test_segmentation_service import FakeSegmentationDataStore


def _npy_body() -> bytes:
    """A 1x4x4 uint8 .npy payload matching the fixture row's shape."""
    buffer = io.BytesIO()
    np.save(buffer, np.zeros((1, 4, 4), dtype=np.uint8))
    return buffer.getvalue()


@pytest.fixture()
def fake_store(monkeypatch):
    """Override the zarr store seam for the whole request.

    The 200 case would otherwise be the first test in the suite to reach
    ``store.write`` through a route -- ``get_segmentation_data_store()`` returns
    a real ``ZarrSegmentationDataStore`` and no conftest overrides it -- and a
    200 that depends on a writable zarr path proves the filesystem, not the
    gate.

    Patched at the name the *factory* calls rather than through
    ``app_api.dependency_overrides``: ``get_model_segmentation_service`` invokes
    ``get_segmentation_data_store()`` itself, so it is a plain function call and
    not a ``Depends`` node FastAPI could intercept. Overriding the factory
    instead would take its ``audit=`` wiring out from under test, which is
    precisely what these route-level cases exist to cover.
    """
    store = FakeSegmentationDataStore()
    monkeypatch.setattr(
        segmentation_service, "get_segmentation_data_store", lambda: store
    )
    return store


@pytest.fixture()
def model_segmentation(session):
    """One ``ModelSegmentation`` in project A, plus a second project B.

    No factory exists for either half: ``ModelSegmentation.ModelID`` is NOT NULL
    and ``SegmentationModel`` is a joined-table subclass of ``Model`` whose
    ``ModelName``/``Version`` are NOT NULL, so the seeding is spelled out (the
    same block as
    ``orm/eyened_orm/tests/test_repository_read_scoping.py``'s).

    Project B exists so the non-member case can be run by an actor holding a
    *real* membership somewhere. An actor with no roles at all would 404 on
    every request in the suite and would prove nothing about this row.
    """
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project_a = make_project(session, "A")
    project_b = make_project(session, "B")
    patient = make_patient(session, project_a, "pat")
    study = make_study(session, patient, date(2024, 1, 1))
    series = make_series(session, study)
    image = make_image(session, series, device, backend, "img")

    model = SegmentationModel(ModelName="m", Version="1")
    session.add(model)
    session.flush()
    row = ModelSegmentation(
        ModelID=model.ModelID,
        ImageInstanceID=image.ImageInstanceID,
        DataType=Datatype.R8UI,
        DataRepresentation=DataRepresentation.Binary,
        Depth=1,
        Height=4,
        Width=4,
    )
    session.add(row)
    session.flush()
    # Read the ids out before the commit: expire_on_commit=True, and an expired
    # instance re-loads through whatever session the test later has.
    data = {
        "id": row.ModelSegmentationID,
        "project": project_a.ProjectID,
        "other_project": project_b.ProjectID,
    }
    session.commit()
    return data


def test_a_grader_can_correct_model_output(
    session, client_scoped, model_segmentation, fake_store
):
    """The exemption itself: a grader who is not (and cannot be) the author
    still gets through. Put the ownership overlay on this path and nobody ever
    does, because the row has no ``CreatorID`` to match."""
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            model_segmentation["project"], role=ProjectRole.grader, actor_id=7
        )
    )
    resp = client.put(
        f"/model-segmentations/{model_segmentation['id']}/data",
        content=_npy_body(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 200
    assert len(fake_store.data) == 1
    # The exemption and its compensation ship together or not at all, and only
    # a route-level case reaches the factory that wires them that way: the
    # audit test below constructs the service itself, so it would stay green
    # against a live endpoint whose ``audit`` is None. Safe to assert after a
    # 200 -- ``get_db`` commits -- and unconditional because
    # ``settings.db_log.enabled`` defaults to True.
    assert session.scalars(select(AuditLog)).one().Entity == "ModelSegmentation"


def test_a_read_only_member_cannot_correct_model_output(
    client_scoped, model_segmentation, fake_store
):
    """403, not 404: the actor holds the row's project, just under the floor."""
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            model_segmentation["project"], role=ProjectRole.read_only, actor_id=7
        )
    )
    resp = client.put(
        f"/model-segmentations/{model_segmentation['id']}/data",
        content=_npy_body(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 403
    assert fake_store.data == {}


def test_a_non_member_gets_a_404(client_scoped, model_segmentation, fake_store):
    """The Task 11 read scope still answers first: a non-member 404s on
    ``get_by_id`` before the ``grader`` floor is ever reached, so the new gate
    does not turn that 404 into a 403. This pins the status code, not this
    task's gate -- it already passed before Task 17 and survives deleting the
    gate outright."""
    client, set_scope = client_scoped
    set_scope(
        scope_for(
            model_segmentation["other_project"],
            role=ProjectRole.project_admin,
            actor_id=7,
        )
    )
    resp = client.put(
        f"/model-segmentations/{model_segmentation['id']}/data",
        content=_npy_body(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp.status_code == 404
    assert fake_store.data == {}


def test_the_write_is_attributed_in_the_audit_trail(session, model_segmentation):
    """The compensation for the exemption.

    The persisted row is the contract, not the fact that ``record()`` was
    called: it is the only place this write's author is recorded, since the
    entity cannot carry one. Built directly rather than through the route
    because ``get_audit_service`` keys on ``settings.db_log.enabled``, which is
    a deployment setting and not this task's subject.
    """
    scope = scope_for(
        model_segmentation["project"], role=ProjectRole.grader, actor_id=7
    )
    service = ModelSegmentationService(
        ModelSegmentationRepository(session, scope=scope),
        FakeSegmentationDataStore(),
        scope=scope,
        audit=AuditService(session),
    )

    service.write_data(
        model_segmentation["id"], np.zeros((1, 4, 4), dtype=np.uint8)
    )

    row = session.scalars(select(AuditLog)).one()
    assert row.Entity == "ModelSegmentation"
    assert row.Action == "UPDATE"
    assert row.ActorID == 7
    assert row.EntityID == str(model_segmentation["id"])
    assert row.ProjectID == model_segmentation["project"]
