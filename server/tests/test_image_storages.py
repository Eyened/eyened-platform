"""ImageGET.storages listing and /images/{id}/data?storage_id= selection."""

from datetime import datetime

import pytest
from eyened_orm import ImageStorage
from eyened_orm.utils.factories import (
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
)


@pytest.fixture()
def client_authed(client):
    """Pixel routes also require ``is_authenticated`` (JWT), not only CurrentUser."""
    from server.main import app_api
    from server.routes.auth import is_authenticated

    app_api.dependency_overrides[is_authenticated] = lambda: True
    yield client
    app_api.dependency_overrides.pop(is_authenticated, None)


@pytest.fixture()
def octa_dual_image(session):
    """One ImageInstance with a structural DICOM and an angio_flow DICOM."""
    backend = make_storage_backend(session, "octa-backend")
    device = make_device(session, "octa-dev")
    project = make_project(session, "octa")
    patient = make_patient(session, project, "pat-octa")
    series = make_series(session, make_study(session, patient, datetime(2024, 1, 1)))
    image = make_image(session, series, device, backend, "octa-1")
    # make_image creates a primary Format=png storage; retarget it to dicom.
    primary = image.primary_storage
    primary.Format = "dicom"
    primary.ObjectKey = "octa/struct.dcm"
    flow = ImageStorage(
        ImageInstanceID=image.ImageInstanceID,
        StorageBackendID=backend.StorageBackendID,
        ObjectKey="octa/flow.dcm",
        Format="dicom",
        IsPrimary=False,
        Role="angio_flow",
    )
    session.add(flow)
    other = make_image(session, series, device, backend, "octa-2")
    session.commit()
    session.refresh(image)
    session.refresh(flow)
    session.refresh(other)
    return {
        "public_id": image.PublicID,
        "project_id": project.ProjectID,
        "primary_id": primary.ImageStorageID,
        "flow_id": flow.ImageStorageID,
        "foreign_storage_id": other.primary_storage.ImageStorageID,
    }


def test_image_get_lists_storages_primary_first(client, octa_dual_image):
    public_id = octa_dual_image["public_id"]
    resp = client.get(f"/images/{public_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_format"] == "dicom"
    storages = body["storages"]
    assert len(storages) == 2
    assert storages[0]["id"] == octa_dual_image["primary_id"]
    assert storages[0]["is_primary"] is True
    assert storages[0]["format"] == "dicom"
    assert storages[0]["role"] is None
    assert storages[1]["id"] == octa_dual_image["flow_id"]
    assert storages[1]["is_primary"] is False
    assert storages[1]["format"] == "dicom"
    assert storages[1]["role"] == "angio_flow"


def test_data_default_redirects_primary(client_authed, octa_dual_image):
    public_id = octa_dual_image["public_id"]
    resp = client_authed.get(f"/images/{public_id}/data")
    assert resp.status_code == 200
    assert resp.headers["X-Accel-Redirect"] == "/data/octa-backend/octa/struct.dcm"


def test_data_storage_id_redirects_angio_flow(client_authed, octa_dual_image):
    public_id = octa_dual_image["public_id"]
    flow_id = octa_dual_image["flow_id"]
    resp = client_authed.get(
        f"/images/{public_id}/data", params={"storage_id": flow_id}
    )
    assert resp.status_code == 200
    assert resp.headers["X-Accel-Redirect"] == "/data/octa-backend/octa/flow.dcm"


def test_data_unknown_storage_id_is_422(client_authed, octa_dual_image):
    public_id = octa_dual_image["public_id"]
    resp = client_authed.get(
        f"/images/{public_id}/data", params={"storage_id": 999_999}
    )
    assert resp.status_code == 422


def test_data_storage_id_from_another_image_is_422(client_authed, octa_dual_image):
    public_id = octa_dual_image["public_id"]
    resp = client_authed.get(
        f"/images/{public_id}/data",
        params={"storage_id": octa_dual_image["foreign_storage_id"]},
    )
    assert resp.status_code == 422
