"""Containment is a database constraint, not a convention."""
from __future__ import annotations

from eyened_orm import ImageInstance
from eyened_orm.utils.factories import make_project


def test_moving_a_patient_carries_its_images_project(session, spanning):
    """ON UPDATE CASCADE down four levels, so no copy can go stale."""
    other = make_project(session, "C")
    image = session.get(ImageInstance, spanning["images"]["A"])
    patient = image.Series.Study.Patient
    patient.ProjectID = other.ProjectID
    session.flush()
    session.expunge_all()
    assert session.get(ImageInstance, spanning["images"]["A"]).ProjectID == other.ProjectID
