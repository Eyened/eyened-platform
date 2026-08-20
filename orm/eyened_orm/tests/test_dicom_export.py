from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pydicom
import pytest
from pydicom.uid import (
    MultiFrameGrayscaleByteSecondaryCaptureImageStorage,
    SecondaryCaptureImageStorage,
)

from eyened_orm.export.dicom_export import (
    DicomExportConfig,
    build_export_filename,
    export_instances_to_dicom,
    fetch_instances_for_export,
    normalize_pixel_array,
    patient_date_offset_days,
    pick_series_localizers,
    pixel_spacing_mm,
    pseudonymize_patient_identifier,
    select_secondary_capture_sop_class,
    series_description_for_instance,
    validate_export_config,
)
from eyened_orm.image_instance import (
    ETDRSField,
    ImageInstance,
    Laterality,
    Modality,
    ModalityType,
    Scan,
)
from eyened_orm.patient import SexEnum
from eyened_orm.utils.factories import (
    make_device,
    make_image,
    make_patient,
    make_project,
    make_series,
    make_storage_backend,
    make_study,
)


def _patch_pixel_arrays(monkeypatch, mapping: dict[int, np.ndarray]) -> None:
    monkeypatch.setattr(
        ImageInstance,
        "pixel_array",
        property(lambda self: mapping[self.ImageInstanceID]),
    )


def _export_world(session, *, identifier: str = "PAT-1"):
    backend = make_storage_backend(session, f"be-{identifier}")
    project = make_project(session, f"Proj-{identifier}")
    patient = make_patient(
        session, project, identifier, date(1980, 5, 20), SexEnum.F
    )
    study = make_study(session, patient, date(2024, 3, 15))
    series = make_series(session, study)
    series.SeriesInstanceUid = "1.2.840.999999.1.2"
    series.StudyInstanceUid = "1.2.840.999999.1.1"
    device = make_device(session, f"dev-{identifier}")
    return backend, project, patient, study, series, device


def _config(tmp_path: Path, **overrides) -> DicomExportConfig:
    values = {
        "output_dir": tmp_path / "dicoms",
        "export_per_patient_subdir": False,
    }
    values.update(overrides)
    return DicomExportConfig(**values)


def _deid_config(tmp_path: Path, **overrides) -> DicomExportConfig:
    values = {
        "output_dir": tmp_path / "dicoms",
        "export_per_patient_subdir": True,
        "pseudonymize_patient_ids": True,
        "pseudonym_salt": "test-pseudonym-salt",
        "pseudonym_prefix": "PID",
        "offset_dates_per_patient": True,
        "date_offset_salt": "test-date-salt",
        "date_offset_min_days": -30,
        "date_offset_max_days": 30,
        "keyfile_path": tmp_path / "patient_keys.csv",
        "image_keyfile_path": tmp_path / "image_keys.csv",
    }
    values.update(overrides)
    return DicomExportConfig(**values)


def test_normalize_pixel_array_keeps_uint8_and_uint16():
    u8 = np.arange(6, dtype=np.uint8).reshape(2, 3)
    out8, spp8, bits8, *_ = normalize_pixel_array(u8)
    assert out8.dtype == np.uint8
    assert spp8 == 1 and bits8 == 8
    np.testing.assert_array_equal(out8, u8)

    u16 = np.array([[0, 40000]], dtype=np.uint16)
    out16, spp16, bits16, *_ = normalize_pixel_array(u16)
    assert out16.dtype == np.uint16
    assert spp16 == 1 and bits16 == 16


def test_normalize_pixel_array_rgb_and_float():
    rgb = np.zeros((4, 5, 3), dtype=np.uint8)
    out, spp, bits, *_ = normalize_pixel_array(rgb)
    assert out.shape == (4, 5, 3)
    assert spp == 3 and bits == 8

    floats = np.array([[0.0, 1.0], [0.5, 0.25]], dtype=np.float32)
    out_f, spp_f, bits_f, _, slope, intercept = normalize_pixel_array(floats)
    assert out_f.dtype == np.uint16
    assert spp_f == 1 and bits_f == 16
    assert out_f.max() == 65535
    assert slope == pytest.approx(1.0 / 65535.0)
    assert intercept == pytest.approx(0.0)

    volume_rgb = np.zeros((3, 4, 5, 3), dtype=np.uint8)
    out_v, spp_v, bits_v, *_ = normalize_pixel_array(volume_rgb)
    assert out_v.shape == (3, 4, 5, 3)
    assert spp_v == 3
    assert select_secondary_capture_sop_class(out_v, 3, 8).endswith(".7.4")


def test_select_secondary_capture_sop_class_2d_and_volume():
    frame = np.zeros((8, 8), dtype=np.uint8)
    volume = np.zeros((5, 8, 8), dtype=np.uint8)
    volume16 = np.zeros((5, 8, 8), dtype=np.uint16)
    rgb = np.zeros((8, 8, 3), dtype=np.uint8)

    assert select_secondary_capture_sop_class(frame, 1, 8) == str(
        SecondaryCaptureImageStorage
    )
    assert select_secondary_capture_sop_class(rgb, 3, 8) == str(
        SecondaryCaptureImageStorage
    )
    assert select_secondary_capture_sop_class(volume, 1, 8) == str(
        MultiFrameGrayscaleByteSecondaryCaptureImageStorage
    )
    assert select_secondary_capture_sop_class(volume16, 1, 16).endswith(".7.3")


def test_pseudonym_and_date_offset_are_deterministic():
    assert pseudonymize_patient_identifier("A", "salt") == pseudonymize_patient_identifier(
        "A", "salt"
    )
    assert pseudonymize_patient_identifier("A", "salt") != pseudonymize_patient_identifier(
        "B", "salt"
    )
    offset = patient_date_offset_days("A", "salt", -10, 10)
    assert -10 <= offset <= 10
    assert offset == patient_date_offset_days("A", "salt", -10, 10)
    with pytest.raises(ValueError, match="date_offset_min_days"):
        patient_date_offset_days("A", "salt", 5, -1)


def test_build_export_filename_sanitizes_components():
    name = build_export_filename("pat/1", date(2024, 1, 2), "L", "S 1")
    assert name == "pat_1_20240102_L_S_1.dcm"


def test_pixel_spacing_uses_axial_for_volumes_and_vertical_for_2d():
    volume = type(
        "Img",
        (),
        {
            "ResolutionAxial": 0.0039,
            "ResolutionHorizontal": 0.0119,
            "ResolutionVertical": 0.030,
        },
    )()
    frame = type(
        "Img",
        (),
        {
            "ResolutionAxial": 0.0039,
            "ResolutionHorizontal": 0.0119,
            "ResolutionVertical": 0.030,
        },
    )()
    assert pixel_spacing_mm(volume, is_volume=True) == (0.0039, 0.0119)
    assert pixel_spacing_mm(frame, is_volume=False) == (0.030, 0.0119)


def test_series_description_includes_scan_mode_and_anatomy():
    instance = type(
        "Img",
        (),
        {
            "Scan": type("Scan", (), {"ScanMode": "Volume"})(),
            "Modality": Modality.OCT,
            "ETDRSField": ETDRSField.F1,
            "AnatomicRegion": 2,
        },
    )()
    assert series_description_for_instance(instance) == "Volume F1 Macula"


def test_validate_export_config_requires_salt_and_keyfile(tmp_path):
    output_dir = tmp_path / "out"
    validate_export_config(DicomExportConfig(output_dir=output_dir))
    with pytest.raises(ValueError, match="requires pseudonymize_patient_ids"):
        validate_export_config(
            DicomExportConfig(
                output_dir=output_dir,
                offset_dates_per_patient=True,
                date_offset_salt="abc",
                keyfile_path=tmp_path / "keys.csv",
                image_keyfile_path=tmp_path / "images.csv",
            )
        )
    with pytest.raises(ValueError, match="pseudonym_salt"):
        validate_export_config(
            DicomExportConfig(
                output_dir=output_dir,
                pseudonymize_patient_ids=True,
                keyfile_path=tmp_path / "keys.csv",
                image_keyfile_path=tmp_path / "images.csv",
            )
        )
    with pytest.raises(ValueError, match="date_offset_salt"):
        validate_export_config(
            DicomExportConfig(
                output_dir=output_dir,
                pseudonymize_patient_ids=True,
                pseudonym_salt="abc",
                offset_dates_per_patient=True,
                keyfile_path=tmp_path / "keys.csv",
                image_keyfile_path=tmp_path / "images.csv",
            )
        )
    with pytest.raises(ValueError, match="keyfile_path is required"):
        validate_export_config(
            DicomExportConfig(
                output_dir=output_dir,
                pseudonymize_patient_ids=True,
                pseudonym_salt="abc",
            )
        )
    with pytest.raises(ValueError, match="image_keyfile_path is required"):
        validate_export_config(
            DicomExportConfig(
                output_dir=output_dir,
                pseudonymize_patient_ids=True,
                pseudonym_salt="abc",
                keyfile_path=tmp_path / "keys.csv",
            )
        )
    with pytest.raises(ValueError, match="patient keyfile_path must be outside"):
        validate_export_config(
            DicomExportConfig(
                output_dir=output_dir,
                pseudonymize_patient_ids=True,
                pseudonym_salt="abc",
                keyfile_path=output_dir / "patient_id_keyfile.csv",
                image_keyfile_path=tmp_path / "images.csv",
            )
        )
    with pytest.raises(ValueError, match="image_keyfile_path must be outside"):
        validate_export_config(
            DicomExportConfig(
                output_dir=output_dir,
                pseudonymize_patient_ids=True,
                pseudonym_salt="abc",
                keyfile_path=tmp_path / "keys.csv",
                image_keyfile_path=output_dir / "image_filename_keyfile.csv",
            )
        )
    with pytest.raises(ValueError, match="reuse_source_uids"):
        validate_export_config(
            DicomExportConfig(
                output_dir=output_dir,
                reuse_source_uids=True,
                pseudonymize_patient_ids=True,
                pseudonym_salt="abc",
                offset_dates_per_patient=True,
                date_offset_salt="abc",
                keyfile_path=tmp_path / "keys.csv",
                image_keyfile_path=tmp_path / "images.csv",
            )
        )


def test_export_rgb_sets_planar_configuration(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session, identifier="rgb")
    img = make_image(session, series, device, backend, "img-rgb")
    _patch_pixel_arrays(
        monkeypatch, {img.ImageInstanceID: np.zeros((6, 7, 3), dtype=np.uint8)}
    )
    result = export_instances_to_dicom(session, [img], _config(tmp_path))
    ds = pydicom.dcmread(result.exported_paths[0])
    assert ds.SamplesPerPixel == 3
    assert ds.PhotometricInterpretation == "RGB"
    assert ds.PlanarConfiguration == 0
    assert ds.SOPClassUID == SecondaryCaptureImageStorage


def test_export_uses_secondary_capture_and_new_uids(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session)
    img = make_image(
        session,
        series,
        device,
        backend,
        "img-sc",
        Laterality=Laterality.L,
        SOPInstanceUid="1.2.840.999999.1.3",
        AcquisitionDateTime=datetime(2024, 3, 15, 8, 30, 0),
    )
    pixels = {img.ImageInstanceID: np.zeros((8, 8), dtype=np.uint8)}
    _patch_pixel_arrays(monkeypatch, pixels)

    result = export_instances_to_dicom(
        session, [img], _config(tmp_path)
    )
    ds = pydicom.dcmread(result.exported_paths[0])

    assert ds.SOPClassUID == SecondaryCaptureImageStorage
    assert ds.ConversionType == "WSD"
    assert ds.ImageLaterality == "L"
    assert ds.SOPInstanceUID != "1.2.840.999999.1.3"
    assert ds.StudyInstanceUID != "1.2.840.999999.1.1"
    assert ds.SeriesInstanceUID != "1.2.840.999999.1.2"
    assert ds.PatientBirthDate == "19800520"
    assert ds.PatientSex == "F"
    assert ds.Manufacturer == "Mf-dev-PAT-1"
    assert list(ds.ImageType) == ["DERIVED", "SECONDARY"]
    assert ds.AcquisitionDate == "20240315"
    assert ds.BurnedInAnnotation == "YES"
    assert ds.PhotometricInterpretation == "MONOCHROME2"


def test_export_instance_numbers_are_per_series(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session)
    img1 = make_image(
        session, series, device, backend, "img-1", Laterality=Laterality.L
    )
    img2 = make_image(
        session, series, device, backend, "img-2", Laterality=Laterality.R
    )
    pixels = {
        img1.ImageInstanceID: np.zeros((4, 4), dtype=np.uint8),
        img2.ImageInstanceID: np.zeros((4, 4), dtype=np.uint8),
    }
    _patch_pixel_arrays(monkeypatch, pixels)

    result = export_instances_to_dicom(session, [img1, img2], _config(tmp_path))
    numbers = sorted(pydicom.dcmread(path).InstanceNumber for path in result.exported_paths)
    assert numbers == [1, 2]


def test_export_writes_geometry_and_ophthalmic_metadata(session, tmp_path, monkeypatch):
    backend, project, patient, study, series, device = _export_world(
        session, identifier="meta"
    )
    study.StudyDescription = "follow-up"
    study.StudyRound = 3
    device.SerialNumber = "SN-42"
    scan = Scan(ScanMode="Volume")
    session.add(scan)
    session.flush()

    img = make_image(
        session,
        series,
        device,
        backend,
        "img-meta",
        Modality=Modality.OCT,
        DICOMModality=ModalityType.OPT,
        NrOfFrames=4,
        Laterality=Laterality.R,
        ScanID=scan.ScanID,
        ETDRSField=ETDRSField.F2,
        AnatomicRegion=2,
        AcquisitionDateTime=datetime(2024, 3, 15, 11, 15, 0),
        ResolutionAxial=0.0039,
        ResolutionHorizontal=0.0119,
        ResolutionVertical=0.030,
        SliceThickness=0.029,
        HorizontalFieldOfView=30.0,
        PupilDilated=True,
    )
    _patch_pixel_arrays(
        monkeypatch, {img.ImageInstanceID: np.zeros((4, 8, 8), dtype=np.uint8)}
    )

    result = export_instances_to_dicom(session, [img], _config(tmp_path))
    ds = pydicom.dcmread(result.exported_paths[0])

    assert "StudyDescription" not in ds
    assert "StudyID" not in ds
    assert ds.SeriesDescription == "Volume F2 Macula"
    assert ds.Laterality == "R"
    assert [float(x) for x in ds.PixelSpacing] == pytest.approx([0.0039, 0.0119])
    assert float(ds.SliceThickness) == pytest.approx(0.029)
    assert float(ds.SpacingBetweenSlices) == pytest.approx(0.030)
    assert float(ds.HorizontalFieldOfView) == pytest.approx(30.0)
    assert ds.PupilDilated == "YES"
    assert ds.DeviceSerialNumber == "SN-42"
    assert ds.AcquisitionDate == "20240315"
    assert ds.FrameIncrementPointer
    assert float(ds.RescaleSlope) == pytest.approx(1.0)

    deid = export_instances_to_dicom(
        session,
        [img],
        _deid_config(
            tmp_path / "deid",
            date_offset_min_days=5,
            date_offset_max_days=5,
        ),
    )
    deid_ds = pydicom.dcmread(deid.exported_paths[0])
    assert "DeviceSerialNumber" not in deid_ds
    assert "StudyDescription" not in deid_ds
    assert deid_ds.AcquisitionDate == "20240320"
    assert deid_ds.PatientID != "meta"
    assert deid_ds.PatientIdentityRemoved == "YES"


def test_oct_localizer_reference_uses_new_sop_uid(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session)
    ir = make_image(
        session,
        series,
        device,
        backend,
        "img-ir",
        Modality=Modality.InfraredReflectance,
        DICOMModality=ModalityType.OP,
        NrOfFrames=1,
        Laterality=Laterality.L,
        SOPInstanceUid="1.2.840.999999.1.4",
    )
    oct_img = make_image(
        session,
        series,
        device,
        backend,
        "img-oct",
        Modality=Modality.OCT,
        DICOMModality=ModalityType.OPT,
        NrOfFrames=5,
        Laterality=Laterality.L,
        SOPInstanceUid="1.2.840.999999.1.5",
    )
    ir.primary_storage.ObjectKey = "scan-a/ir.png"
    oct_img.primary_storage.ObjectKey = "scan-a/oct.dcm"
    session.flush()

    pixels = {
        ir.ImageInstanceID: np.zeros((8, 8), dtype=np.uint8),
        oct_img.ImageInstanceID: np.zeros((5, 8, 8), dtype=np.uint8),
    }
    _patch_pixel_arrays(monkeypatch, pixels)

    result = export_instances_to_dicom(session, [oct_img], _config(tmp_path))
    assert result.exported_count == 2

    by_public_id = {}
    with result.image_keyfile_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_public_id[row["image_public_id"]] = row

    oct_ds = pydicom.dcmread(tmp_path / "dicoms" / by_public_id["img-oct"]["exported_filename"])
    ir_uid = by_public_id["img-ir"]["sop_instance_uid"]

    assert oct_ds.SOPClassUID == MultiFrameGrayscaleByteSecondaryCaptureImageStorage
    assert oct_ds.NumberOfFrames == 5
    assert ir_uid != "1.2.840.999999.1.4"
    refs = [str(item.ReferencedSOPInstanceUID) for item in oct_ds.ReferencedImageSequence]
    assert refs == [ir_uid]


def test_deid_requires_keyfile_outside_output_dir(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session)
    img = make_image(session, series, device, backend, "img-deid")
    _patch_pixel_arrays(
        monkeypatch, {img.ImageInstanceID: np.zeros((4, 4), dtype=np.uint8)}
    )
    output_dir = tmp_path / "share"
    with pytest.raises(ValueError, match="keyfile_path is required"):
        export_instances_to_dicom(
            session,
            [img],
            DicomExportConfig(
                output_dir=output_dir,
                pseudonymize_patient_ids=True,
                pseudonym_salt="secret",
            ),
        )
    with pytest.raises(ValueError, match="image_keyfile_path is required"):
        export_instances_to_dicom(
            session,
            [img],
            DicomExportConfig(
                output_dir=output_dir,
                pseudonymize_patient_ids=True,
                pseudonym_salt="secret",
                keyfile_path=tmp_path / "keys.csv",
            ),
        )


def test_deid_omits_birth_date_and_does_not_shift_content_date(
    session, tmp_path, monkeypatch
):
    backend, _, _, _, series, device = _export_world(session)
    img = make_image(
        session,
        series,
        device,
        backend,
        "img-dates",
        Laterality=Laterality.R,
        AcquisitionDateTime=datetime(2024, 3, 15, 9, 0, 0),
    )
    _patch_pixel_arrays(
        monkeypatch, {img.ImageInstanceID: np.zeros((4, 4), dtype=np.uint8)}
    )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 8, 18, 12, 0, 0)

    monkeypatch.setattr("eyened_orm.export.dicom_export.datetime", FrozenDateTime)

    result = export_instances_to_dicom(
        session,
        [img],
        _deid_config(
            tmp_path,
            date_offset_min_days=10,
            date_offset_max_days=10,
        ),
    )
    ds = pydicom.dcmread(result.exported_paths[0])
    assert ds.PatientBirthDate == ""
    assert ds.StudyDate == "20240325"
    assert ds.ContentDate == "20260818"
    assert ds.PatientID != "PAT-1"
    assert result.keyfile_path == tmp_path / "patient_keys.csv"
    assert not str(result.keyfile_path).startswith(str(tmp_path / "dicoms"))
    with result.keyfile_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["original_patient_id"] == "PAT-1"
    assert rows[0]["pseudonymized_patient_id"] == ds.PatientID
    assert rows[0]["date_offset_days"] == "10"
    assert (result.keyfile_path.stat().st_mode & 0o777) == 0o600


def test_study_date_time_consistent_across_instances(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session)
    img1 = make_image(
        session,
        series,
        device,
        backend,
        "img-am",
        AcquisitionDateTime=datetime(2024, 3, 15, 8, 0, 0),
    )
    img2 = make_image(
        session,
        series,
        device,
        backend,
        "img-pm",
        AcquisitionDateTime=datetime(2024, 3, 15, 16, 0, 0),
    )
    _patch_pixel_arrays(
        monkeypatch,
        {
            img1.ImageInstanceID: np.zeros((4, 4), dtype=np.uint8),
            img2.ImageInstanceID: np.zeros((4, 4), dtype=np.uint8),
        },
    )

    result = export_instances_to_dicom(session, [img1, img2], _config(tmp_path))
    datasets = [pydicom.dcmread(path) for path in result.exported_paths]
    assert {ds.StudyDate for ds in datasets} == {"20240315"}
    assert {ds.StudyTime for ds in datasets} == {"080000"}
    assert {ds.StudyInstanceUID for ds in datasets} == {datasets[0].StudyInstanceUID}


def test_image_keyfile_includes_uids(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session)
    img = make_image(session, series, device, backend, "img-key")
    _patch_pixel_arrays(
        monkeypatch, {img.ImageInstanceID: np.zeros((4, 4), dtype=np.uint8)}
    )
    result = export_instances_to_dicom(session, [img], _config(tmp_path))
    assert result.image_keyfile_path == tmp_path / "image_filename_keyfile.csv"
    assert not str(result.image_keyfile_path).startswith(str(tmp_path / "dicoms"))
    with result.image_keyfile_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["image_public_id"] == "img-key"
    assert rows[0]["sop_instance_uid"]
    ds = pydicom.dcmread(result.exported_paths[0])
    assert rows[0]["sop_instance_uid"] == ds.SOPInstanceUID
    assert rows[0]["series_instance_uid"] == ds.SeriesInstanceUID
    assert rows[0]["study_instance_uid"] == ds.StudyInstanceUID


def test_reuse_source_uids_when_not_deidentifying(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session)
    img = make_image(
        session,
        series,
        device,
        backend,
        "img-reuse",
        SOPInstanceUid="1.2.840.999999.1.6",
    )
    _patch_pixel_arrays(
        monkeypatch, {img.ImageInstanceID: np.zeros((4, 4), dtype=np.uint8)}
    )
    result = export_instances_to_dicom(
        session, [img], _config(tmp_path, reuse_source_uids=True)
    )
    ds = pydicom.dcmread(result.exported_paths[0])
    assert ds.SOPInstanceUID == "1.2.840.999999.1.6"
    assert ds.SeriesInstanceUID == "1.2.840.999999.1.2"
    assert ds.StudyInstanceUID == "1.2.840.999999.1.1"
    assert ds.SOPClassUID == SecondaryCaptureImageStorage


def test_pick_series_localizers_prefers_same_directory(session):
    backend, _, _, _, series, device = _export_world(session)
    oct_img = make_image(
        session,
        series,
        device,
        backend,
        "oct",
        Modality=Modality.OCT,
        NrOfFrames=3,
    )
    same_dir = make_image(
        session,
        series,
        device,
        backend,
        "ir-same",
        Modality=Modality.InfraredReflectance,
        DICOMModality=ModalityType.OP,
    )
    other_dir = make_image(
        session,
        series,
        device,
        backend,
        "ir-other",
        Modality=Modality.InfraredReflectance,
        DICOMModality=ModalityType.OP,
    )
    oct_img.primary_storage.ObjectKey = "vol/oct.dcm"
    same_dir.primary_storage.ObjectKey = "vol/ir.png"
    other_dir.primary_storage.ObjectKey = "other/ir.png"
    session.flush()

    chosen = pick_series_localizers(oct_img, [oct_img, same_dir, other_dir])
    assert [im.PublicID for im in chosen] == ["ir-same"]

    heuristic = pick_series_localizers(oct_img, [oct_img, other_dir])
    assert [im.PublicID for im in heuristic] == ["ir-other"]


def test_fetch_instances_for_export_filters_inactive(session):
    backend, project, _, _, series, device = _export_world(session, identifier="fetch")
    active = make_image(session, series, device, backend, "active")
    make_image(session, series, device, backend, "gone", inactive=True)
    found = fetch_instances_for_export(session, project.ProjectName, limit=50)
    assert [im.PublicID for im in found] == [active.PublicID]
    by_patient = fetch_instances_for_export(
        session, project.ProjectName, patient_identifier="fetch", limit=50
    )
    assert [im.PublicID for im in by_patient] == [active.PublicID]
    including_inactive = fetch_instances_for_export(
        session, project.ProjectName, limit=50, include_inactive=True
    )
    assert {im.PublicID for im in including_inactive} == {"active", "gone"}


def _share_bytes(output_dir: Path) -> bytes:
    chunks: list[bytes] = []
    for path in sorted(output_dir.rglob("*")):
        chunks.append(str(path.relative_to(output_dir)).encode("utf-8"))
        if path.is_file():
            chunks.append(path.read_bytes())
    return b"\n".join(chunks)


def test_deid_share_contains_no_source_identifiers(session, tmp_path, monkeypatch):
    identifier = "PAT-SECRET-99"
    backend, _, patient, _, series, device = _export_world(
        session, identifier=identifier
    )
    device.SerialNumber = "SN-LEAK"
    device.DeviceModel.Manufacturer = "Heidelberg"
    device.DeviceModel.ManufacturerModelName = "Spectralis"
    img = make_image(
        session,
        series,
        device,
        backend,
        "img-secret",
        Laterality=Laterality.L,
        SOPInstanceUid="1.2.840.999999.1.9",
        AcquisitionDateTime=datetime(2024, 3, 15, 9, 0, 0),
        PhotometricInterpretation="PALETTE COLOR",
    )
    _patch_pixel_arrays(
        monkeypatch, {img.ImageInstanceID: np.zeros((4, 4), dtype=np.uint8)}
    )

    result = export_instances_to_dicom(session, [img], _deid_config(tmp_path))
    ds = pydicom.dcmread(result.exported_paths[0])
    blob = _share_bytes(tmp_path / "dicoms")

    assert identifier.encode() not in blob
    assert b"19800520" not in blob
    assert b"1.2.840.999999.1.9" not in blob
    assert b"1.2.840.999999.1.1" not in blob
    assert b"1.2.840.999999.1.2" not in blob
    assert b"SN-LEAK" not in blob
    assert ds.PatientID != identifier
    assert ds.PatientIdentityRemoved == "YES"
    assert ds.PhotometricInterpretation == "MONOCHROME2"
    assert identifier not in str(result.exported_paths[0])
    assert result.keyfile_path is not None
    assert not str(result.keyfile_path).startswith(str(tmp_path / "dicoms"))
    assert not str(result.image_keyfile_path).startswith(str(tmp_path / "dicoms"))

    with result.keyfile_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["original_patient_id"] == identifier
    assert rows[0]["pseudonymized_patient_id"] == ds.PatientID
    offset = int(rows[0]["date_offset_days"])
    assert -30 <= offset <= 30
    assert offset == patient_date_offset_days(
        identifier, "test-date-salt", -30, 30
    )


def test_inactive_localizers_are_not_exported(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session, identifier="inact")
    oct_img = make_image(
        session,
        series,
        device,
        backend,
        "oct-live",
        Modality=Modality.OCT,
        NrOfFrames=3,
        Laterality=Laterality.L,
    )
    ir = make_image(
        session,
        series,
        device,
        backend,
        "ir-retired",
        Modality=Modality.InfraredReflectance,
        DICOMModality=ModalityType.OP,
        inactive=True,
    )
    oct_img.primary_storage.ObjectKey = "vol/oct.dcm"
    ir.primary_storage.ObjectKey = "vol/ir.png"
    session.flush()
    _patch_pixel_arrays(
        monkeypatch,
        {
            oct_img.ImageInstanceID: np.zeros((3, 8, 8), dtype=np.uint8),
            ir.ImageInstanceID: np.zeros((8, 8), dtype=np.uint8),
        },
    )
    result = export_instances_to_dicom(session, [oct_img], _config(tmp_path))
    assert result.exported_count == 1


def test_export_rgb_volume_does_not_crash(session, tmp_path, monkeypatch):
    backend, _, _, _, series, device = _export_world(session, identifier="rgbvol")
    img = make_image(
        session, series, device, backend, "img-rgbvol", NrOfFrames=3
    )
    _patch_pixel_arrays(
        monkeypatch,
        {img.ImageInstanceID: np.zeros((3, 6, 7, 3), dtype=np.uint8)},
    )
    result = export_instances_to_dicom(session, [img], _config(tmp_path))
    ds = pydicom.dcmread(result.exported_paths[0])
    assert ds.NumberOfFrames == 3
    assert ds.SamplesPerPixel == 3
    assert ds.PhotometricInterpretation == "RGB"
    assert ds.SOPClassUID.endswith(".7.4")
    assert ds.FrameIncrementPointer
