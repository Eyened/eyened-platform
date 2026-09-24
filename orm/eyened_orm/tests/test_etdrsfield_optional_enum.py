"""WF/UWF must round-trip through OptionalEnum(ETDRSField).

Alembic's MySQL type compare only flags ENUM member lists of equal length, so
schema-sync and autogenerate cannot catch enum drift. Loading a WF/UWF row
without the Python members raises LookupError.
"""

from datetime import date

import pytest

from eyened_orm.image_instance import ETDRSField, ImageInstance
from eyened_orm.utils.factories import (
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
)


@pytest.mark.parametrize("field", [ETDRSField.WF, ETDRSField.UWF])
def test_wf_uwf_round_trip_through_optional_enum(session, field):
    backend = make_storage_backend(session)
    device = make_device(session, "d")
    project = make_project(session, "p")
    patient = make_patient(session, project, "pat")
    study = make_study(session, patient, date(2024, 1, 1))
    series = make_series(session, study)
    img = make_image(
        session, series, device, backend, "imgwf000001", ETDRSField=field
    )
    session.flush()
    session.expire(img)

    loaded = session.get(ImageInstance, img.ImageInstanceID)
    assert loaded.ETDRSField is field
