"""get_etdrs_field must not re-guess F1/F2 when the stored field is WF/UWF."""

from types import SimpleNamespace

from eyened_orm.image_instance import ETDRSField
from eyened_orm.utils.registration import get_etdrs_field

# Geometry that would guess F1 if a WF/UWF label were ignored.
_KEYPOINTS_F1 = {"fovea_xy": (0.0, 0.0)}
_ROI = {"center": (100.0, 0.0), "radius": 10.0}


def test_stored_f1_or_f2_is_trusted():
    assert get_etdrs_field(SimpleNamespace(ETDRSField=ETDRSField.F1)) == "F1"
    assert get_etdrs_field(SimpleNamespace(ETDRSField=ETDRSField.F2)) == "F2"


def test_wf_uwf_are_not_re_guessed_from_keypoints():
    for field in (ETDRSField.WF, ETDRSField.UWF, ETDRSField.F3):
        image = SimpleNamespace(
            ETDRSField=field,
            CFKeypoints=_KEYPOINTS_F1,
            CFROI=_ROI,
        )
        assert get_etdrs_field(image) is None


def test_unlabeled_still_guesses_from_keypoints():
    image = SimpleNamespace(
        ETDRSField=None,
        CFKeypoints=_KEYPOINTS_F1,
        CFROI=_ROI,
        Modality=None,
    )
    assert get_etdrs_field(image) == "F1"
