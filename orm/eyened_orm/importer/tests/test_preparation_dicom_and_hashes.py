from __future__ import annotations

import io
from datetime import date

import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian

from eyened_orm.image_instance import Modality, ModalityType
from eyened_orm.importer.importer_dtos import ImportRow
from eyened_orm.importer.preparation.dicom_meta import dicom_header_patches_from_bytes
from eyened_orm.importer.preparation.hashes import md5_hex, sha256_bytes
from eyened_orm.importer.preparation.pipeline import PreparationOptions, prepare_rows


def _save_ds(ds: FileDataset) -> bytes:
    buf = io.BytesIO()
    ds.save_as(buf)
    return buf.getvalue()


def _base_file_dataset(
    *,
    sop_instance_uid: str,
    sop_class_uid: str = "1.2.840.10008.5.1.4.1.1.7",
) -> FileDataset:
    file_meta = FileMetaDataset()
    file_meta.FileMetaInformationVersion = b"\x00\x01"
    file_meta.MediaStorageSOPClassUID = sop_class_uid
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = "1.2.3.4.5"

    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = sop_class_uid
    ds.SOPInstanceUID = sop_instance_uid
    return ds


def _minimal_dicom_bytes() -> bytes:
    ds = _base_file_dataset(sop_instance_uid="1.2.3.4.5.6.7.8.9")
    ds.Modality = "OP"
    ds.Rows = 64
    ds.Columns = 128
    ds.SeriesInstanceUID = "1.2.840.10008.1.2.3.4.5.6.1"
    ds.StudyInstanceUID = "1.2.840.10008.1.2.3.4.5.6.2"
    ds.SeriesNumber = 3
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    return _save_ds(ds)


def test_dicom_header_patches_from_bytes():
    raw = _minimal_dicom_bytes()
    p = dicom_header_patches_from_bytes(raw)
    assert p["sop_instance_uid"] == "1.2.3.4.5.6.7.8.9"
    assert p["dicom_modality"] == ModalityType.OP
    assert "modality" not in p  # OP without ImageType subtype
    assert p["height"] == 64
    assert p["width"] == 128
    assert p["series_instance_uid"] == "1.2.840.10008.1.2.3.4.5.6.1"
    assert p["study_instance_uid"] == "1.2.840.10008.1.2.3.4.5.6.2"
    assert p["series_number"] == 3


def test_dicom_header_patient_study_and_modality_opt():
    ds = _base_file_dataset(
        sop_instance_uid="1.2.840.10008.1.2.3.opt",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.4",
    )
    ds.PatientID = "21715"
    ds.StudyDate = "20250401"
    ds.Modality = "OPT"
    ds.ImageType = ["ORIGINAL", "PRIMARY"]
    ds.NumberOfFrames = 37
    ds.Rows = 496
    ds.Columns = 512
    ds.SeriesInstanceUID = "1.2.3.opt.series"
    ds.StudyInstanceUID = "1.2.3.study"
    ds.FrameOfReferenceUID = "1.2.3.for"
    raw = _save_ds(ds)
    p = dicom_header_patches_from_bytes(raw)
    assert p["patient_identifier"] == "21715"
    assert p["study_date"] == date(2025, 4, 1)
    assert p["dicom_modality"] == ModalityType.OPT
    assert p["modality"] == Modality.OCT
    assert p["depth"] == 37
    assert p["frame_of_reference_uid"] == "1.2.3.for"


def test_dicom_header_modality_op_red_and_af():
    for image_type, expected in (
        (["ORIGINAL", "PRIMARY", "", "RED"], Modality.InfraredReflectance),
        (["ORIGINAL", "PRIMARY", "", "AF"], Modality.Autofluorescence),
    ):
        ds = _base_file_dataset(sop_instance_uid=f"1.2.3.{image_type[-1]}")
        ds.Modality = "OP"
        ds.ImageType = image_type
        ds.Rows = 768
        ds.Columns = 768
        ds.SeriesInstanceUID = "1.2.3.op.series"
        p = dicom_header_patches_from_bytes(_save_ds(ds))
        assert p["dicom_modality"] == ModalityType.OP
        assert p["modality"] == expected


def test_dicom_header_ot_skips_modality_fields():
    ds = _base_file_dataset(sop_instance_uid="1.2.3.ot")
    ds.PatientID = "P1"
    ds.StudyDate = "20200101"
    ds.Modality = "OT"
    ds.SeriesInstanceUID = "1.2.3.ot.series"
    p = dicom_header_patches_from_bytes(_save_ds(ds))
    assert p["patient_identifier"] == "P1"
    assert p["study_date"] == date(2020, 1, 1)
    assert "dicom_modality" not in p
    assert "modality" not in p


def test_dicom_header_pixel_spacing_top_level():
    ds = _base_file_dataset(sop_instance_uid="1.2.840.10008.1.2.3.op.ps")
    ds.Modality = "OP"
    ds.ImageType = ["ORIGINAL", "PRIMARY", "", "RED"]
    ds.Rows = 768
    ds.Columns = 768
    ds.SeriesInstanceUID = "1.2.840.10008.1.2.3.op.ps.series"
    ds.PixelSpacing = [0.021261, 0.021261]
    p = dicom_header_patches_from_bytes(_save_ds(ds))
    assert p["resolution_vertical"] == pytest.approx(0.021261)
    assert p["resolution_horizontal"] == pytest.approx(0.021261)


def test_dicom_header_pixel_measures_from_shared_functional_groups():
    ds = _base_file_dataset(
        sop_instance_uid="1.2.840.10008.1.2.3.opt.pm",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.4",
    )
    ds.Modality = "OPT"
    ds.Rows = 496
    ds.Columns = 512
    ds.NumberOfFrames = 37
    ds.SeriesInstanceUID = "1.2.840.10008.1.2.3.opt.pm.series"
    pm = Dataset()
    pm.PixelSpacing = [0.003872, 0.011891]
    pm.SliceThickness = 0.125710
    shared = Dataset()
    shared.PixelMeasuresSequence = Sequence([pm])
    ds.SharedFunctionalGroupsSequence = Sequence([shared])
    p = dicom_header_patches_from_bytes(_save_ds(ds))
    assert p["resolution_vertical"] == pytest.approx(0.003872)
    assert p["resolution_horizontal"] == pytest.approx(0.011891)
    assert p["resolution_axial"] == pytest.approx(0.125710)


def test_dicom_header_referenced_sop_from_shared_fg():
    enface_sop = "1.2.3.enface.sop"
    ds = _base_file_dataset(
        sop_instance_uid="1.2.3.opt.sop",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.4",
    )
    ds.Modality = "OPT"
    ds.SeriesInstanceUID = "1.2.3.opt.series"
    ds.FrameOfReferenceUID = "1.2.3.for"

    ref_item = Dataset()
    ref_item.ReferencedSOPClassUID = "1.2.840.10008.5.1.4.1.1.77.1.5.1"
    ref_item.ReferencedSOPInstanceUID = enface_sop
    shared = Dataset()
    shared.ReferencedImageSequence = Sequence([ref_item])
    ds.SharedFunctionalGroupsSequence = Sequence([shared])

    p = dicom_header_patches_from_bytes(_save_ds(ds))
    assert p["referenced_sop_instance_uids"] == [enface_sop]


def test_prepare_rows_dicom_header_via_raw_loader():
    raw = _minimal_dicom_bytes()

    def _loader(_row: ImportRow) -> bytes | None:
        return raw

    row = ImportRow(
        project_name="p",
        storage_backend_key="missing",
        object_key="missing.dcm",
        patient_identifier="x",
        image_storage_format="dicom",
    )
    opts = PreparationOptions(
        infer_image_format=False,
        defaults=None,
        infer_metadata_from_dicom_header=True,
        raw_loader=_loader,
    )
    out = prepare_rows([row], options=opts)[0]
    assert out.sop_instance_uid == "1.2.3.4.5.6.7.8.9"
    assert out.width == 128
    assert out.height == 64


def test_prepare_rows_fills_patient_study_modality_from_dicom():
    ds = _base_file_dataset(
        sop_instance_uid="1.2.3.opt",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.4",
    )
    ds.PatientID = "21715"
    ds.StudyDate = "20250401"
    ds.Modality = "OPT"
    ds.SeriesInstanceUID = "1.2.3.series"
    raw = _save_ds(ds)

    def _loader(_row: ImportRow) -> bytes | None:
        return raw

    row = ImportRow(
        project_name="p",
        storage_backend_key="sb",
        object_key="vol.dcm",
        image_storage_format="dicom",
    )
    out = prepare_rows(
        [row],
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=True,
            raw_loader=_loader,
        ),
    )[0]
    assert out.patient_identifier == "21715"
    assert out.study_date == date(2025, 4, 1)
    assert out.dicom_modality == ModalityType.OPT
    assert out.modality == Modality.OCT


def test_prepare_rows_does_not_override_caller_patient_modality_series():
    ds = _base_file_dataset(sop_instance_uid="1.2.3.opt")
    ds.PatientID = "WRONG"
    ds.StudyDate = "20200101"
    ds.Modality = "OPT"
    ds.SeriesInstanceUID = "1.2.3.from.dicom"
    raw = _save_ds(ds)

    def _loader(_row: ImportRow) -> bytes | None:
        return raw

    row = ImportRow(
        project_name="p",
        storage_backend_key="sb",
        object_key="vol.dcm",
        image_storage_format="dicom",
        patient_identifier="RPE65014",
        modality=Modality.OCTA,
        series_instance_uid="1.2.3.caller",
    )
    out = prepare_rows(
        [row],
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=True,
            raw_loader=_loader,
        ),
    )[0]
    assert out.patient_identifier == "RPE65014"
    assert out.modality == Modality.OCTA
    assert out.series_instance_uid == "1.2.3.caller"
    assert out.study_date == date(2020, 1, 1)  # still filled when missing


def test_prepare_rows_link_oct_enface_via_referenced_sop():
    enface_sop = "1.2.3.enface"
    oct_sop = "1.2.3.oct"
    oct_series = "1.2.3.oct.series"
    enface_series = "1.2.3.enface.series"
    for_uid = "1.2.3.for"

    enface_ds = _base_file_dataset(
        sop_instance_uid=enface_sop,
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.1",
    )
    enface_ds.Modality = "OP"
    enface_ds.ImageType = ["ORIGINAL", "PRIMARY", "", "RED"]
    enface_ds.SeriesInstanceUID = enface_series
    enface_ds.FrameOfReferenceUID = for_uid
    enface_ds.Rows = 768
    enface_ds.Columns = 768
    enface_raw = _save_ds(enface_ds)

    oct_ds = _base_file_dataset(
        sop_instance_uid=oct_sop,
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.4",
    )
    oct_ds.Modality = "OPT"
    oct_ds.SeriesInstanceUID = oct_series
    oct_ds.FrameOfReferenceUID = for_uid
    oct_ds.NumberOfFrames = 37
    ref_item = Dataset()
    ref_item.ReferencedSOPClassUID = "1.2.840.10008.5.1.4.1.1.77.1.5.1"
    ref_item.ReferencedSOPInstanceUID = enface_sop
    shared = Dataset()
    shared.ReferencedImageSequence = Sequence([ref_item])
    oct_ds.SharedFunctionalGroupsSequence = Sequence([shared])
    oct_raw = _save_ds(oct_ds)

    by_key = {"enface.dcm": enface_raw, "oct.dcm": oct_raw}

    def _loader(row: ImportRow) -> bytes | None:
        return by_key.get(row.object_key or "")

    rows = [
        ImportRow(
            project_name="p",
            storage_backend_key="sb",
            object_key="enface.dcm",
            image_storage_format="dicom",
        ),
        ImportRow(
            project_name="p",
            storage_backend_key="sb",
            object_key="oct.dcm",
            image_storage_format="dicom",
        ),
    ]
    out = prepare_rows(
        rows,
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=True,
            link_oct_enface_series=True,
            raw_loader=_loader,
        ),
    )
    assert out[0].sop_instance_uid == enface_sop
    assert out[1].sop_instance_uid == oct_sop
    assert out[0].series_instance_uid == oct_series
    assert out[1].series_instance_uid == oct_series
    assert out[0].modality == Modality.InfraredReflectance
    assert out[1].modality == Modality.OCT


def test_prepare_rows_link_oct_enface_via_frame_of_reference_fallback():
    enface_sop = "1.2.3.enface.for"
    oct_sop = "1.2.3.oct.for"
    oct_series = "1.2.3.oct.series.for"
    for_uid = "1.2.3.shared.for"

    enface_ds = _base_file_dataset(sop_instance_uid=enface_sop)
    enface_ds.Modality = "OP"
    enface_ds.ImageType = ["ORIGINAL", "PRIMARY", "", "RED"]
    enface_ds.SeriesInstanceUID = "1.2.3.enface.series.for"
    enface_ds.FrameOfReferenceUID = for_uid
    enface_raw = _save_ds(enface_ds)

    oct_ds = _base_file_dataset(
        sop_instance_uid=oct_sop,
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.4",
    )
    oct_ds.Modality = "OPT"
    oct_ds.SeriesInstanceUID = oct_series
    oct_ds.FrameOfReferenceUID = for_uid
    oct_raw = _save_ds(oct_ds)

    by_key = {"e.dcm": enface_raw, "o.dcm": oct_raw}

    def _loader(row: ImportRow) -> bytes | None:
        return by_key.get(row.object_key or "")

    out = prepare_rows(
        [
            ImportRow(
                project_name="p",
                storage_backend_key="sb",
                object_key="e.dcm",
                image_storage_format="dicom",
            ),
            ImportRow(
                project_name="p",
                storage_backend_key="sb",
                object_key="o.dcm",
                image_storage_format="dicom",
            ),
        ],
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=True,
            link_oct_enface_series=True,
            raw_loader=_loader,
        ),
    )
    assert out[0].series_instance_uid == oct_series
    assert out[1].series_instance_uid == oct_series


def test_prepare_rows_link_despite_series_anonymous_identity():
    """FoR/ref-SOP confirmed pairs still share series_instance_uid even with anon id."""
    enface_sop = "1.2.3.enface.anon"
    oct_sop = "1.2.3.oct.anon"
    oct_series = "1.2.3.oct.series.anon"
    for_uid = "1.2.3.for.anon"

    enface_ds = _base_file_dataset(sop_instance_uid=enface_sop)
    enface_ds.Modality = "OP"
    enface_ds.ImageType = ["ORIGINAL", "PRIMARY", "", "RED"]
    enface_ds.SeriesInstanceUID = "1.2.3.enface.series.anon"
    enface_ds.FrameOfReferenceUID = for_uid
    enface_raw = _save_ds(enface_ds)

    oct_ds = _base_file_dataset(sop_instance_uid=oct_sop)
    oct_ds.Modality = "OPT"
    oct_ds.SeriesInstanceUID = oct_series
    oct_ds.FrameOfReferenceUID = for_uid
    ref_item = Dataset()
    ref_item.ReferencedSOPInstanceUID = enface_sop
    shared = Dataset()
    shared.ReferencedImageSequence = Sequence([ref_item])
    oct_ds.SharedFunctionalGroupsSequence = Sequence([shared])
    oct_raw = _save_ds(oct_ds)

    by_key = {"e.dcm": enface_raw, "o.dcm": oct_raw}

    def _loader(row: ImportRow) -> bytes | None:
        return by_key.get(row.object_key or "")

    out = prepare_rows(
        [
            ImportRow(
                project_name="p",
                storage_backend_key="sb",
                object_key="e.dcm",
                image_storage_format="dicom",
                series_anonymous_identity=7,
            ),
            ImportRow(
                project_name="p",
                storage_backend_key="sb",
                object_key="o.dcm",
                image_storage_format="dicom",
                series_anonymous_identity=7,
            ),
        ],
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=True,
            link_oct_enface_series=True,
            raw_loader=_loader,
        ),
    )
    assert out[0].series_instance_uid == oct_series
    assert out[1].series_instance_uid == oct_series
    assert out[0].series_anonymous_identity == 7
    assert out[1].series_anonymous_identity == 7


def test_prepare_rows_link_respects_explicit_series_id():
    """Rows pinned to an existing series_id are not rewritten."""
    enface_sop = "1.2.3.enface.sid"
    oct_sop = "1.2.3.oct.sid"
    for_uid = "1.2.3.for.sid"

    enface_ds = _base_file_dataset(sop_instance_uid=enface_sop)
    enface_ds.Modality = "OP"
    enface_ds.ImageType = ["ORIGINAL", "PRIMARY", "", "RED"]
    enface_ds.SeriesInstanceUID = "1.2.3.enface.series.sid"
    enface_ds.FrameOfReferenceUID = for_uid
    enface_raw = _save_ds(enface_ds)

    oct_ds = _base_file_dataset(sop_instance_uid=oct_sop)
    oct_ds.Modality = "OPT"
    oct_ds.SeriesInstanceUID = "1.2.3.oct.series.sid"
    oct_ds.FrameOfReferenceUID = for_uid
    ref_item = Dataset()
    ref_item.ReferencedSOPInstanceUID = enface_sop
    shared = Dataset()
    shared.ReferencedImageSequence = Sequence([ref_item])
    oct_ds.SharedFunctionalGroupsSequence = Sequence([shared])
    oct_raw = _save_ds(oct_ds)

    by_key = {"e.dcm": enface_raw, "o.dcm": oct_raw}

    def _loader(row: ImportRow) -> bytes | None:
        return by_key.get(row.object_key or "")

    out = prepare_rows(
        [
            ImportRow(
                project_name="p",
                storage_backend_key="sb",
                object_key="e.dcm",
                image_storage_format="dicom",
                series_id=42,
            ),
            ImportRow(
                project_name="p",
                storage_backend_key="sb",
                object_key="o.dcm",
                image_storage_format="dicom",
                series_id=42,
            ),
        ],
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=True,
            link_oct_enface_series=True,
            raw_loader=_loader,
        ),
    )
    assert out[0].series_instance_uid == "1.2.3.enface.series.sid"
    assert out[1].series_instance_uid == "1.2.3.oct.series.sid"
    assert out[0].series_id == 42
    assert out[1].series_id == 42


def test_prepare_rows_hashes_via_raw_loader():
    raw = b"hello-world"

    def _loader(_row: ImportRow) -> bytes | None:
        return raw

    row = ImportRow(
        project_name="p",
        storage_backend_key="sb",
        object_key="k.bin",
        patient_identifier="x",
    )
    opts = PreparationOptions(
        infer_image_format=False,
        compute_storage_hash=True,
        compute_storage_checksum=True,
        raw_loader=_loader,
    )
    out = prepare_rows([row], options=opts)[0]
    assert out.image_storage_hash == sha256_bytes(raw)
    assert out.image_storage_checksum == md5_hex(raw)


def test_prepare_rows_does_not_override_existing_hash():
    raw = b"x"

    def _loader(_row: ImportRow) -> bytes | None:
        return raw

    existing = b"\x01" * 32
    row = ImportRow(
        project_name="p",
        storage_backend_key="sb",
        object_key="k.bin",
        patient_identifier="x",
        image_storage_hash=existing,
    )
    opts = PreparationOptions(
        infer_image_format=False,
        compute_storage_hash=True,
        raw_loader=_loader,
    )
    out = prepare_rows([row], options=opts)[0]
    assert out.image_storage_hash == existing


def test_prepare_rows_explicit_none_pins_blank_against_dicom():
    ds = _base_file_dataset(sop_instance_uid="1.2.3.pin")
    ds.PatientID = "FROM_DICOM"
    ds.StudyDate = "20200101"
    ds.Modality = "OPT"
    ds.SeriesInstanceUID = "1.2.3.pin.series"
    raw = _save_ds(ds)

    row = ImportRow(
        project_name="p",
        storage_backend_key="sb",
        object_key="vol.dcm",
        image_storage_format="dicom",
        patient_identifier=None,
    )
    assert "patient_identifier" in row.model_fields_set
    out = prepare_rows(
        [row],
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=True,
            raw_loader=lambda _r: raw,
        ),
    )[0]
    assert out.patient_identifier is None
    assert out.study_date == date(2020, 1, 1)


def test_prepare_rows_omitted_patient_filled_from_dicom():
    ds = _base_file_dataset(sop_instance_uid="1.2.3.fill")
    ds.PatientID = "FROM_DICOM"
    ds.SeriesInstanceUID = "1.2.3.fill.series"
    raw = _save_ds(ds)

    row = ImportRow(
        project_name="p",
        storage_backend_key="sb",
        object_key="vol.dcm",
        image_storage_format="dicom",
    )
    assert "patient_identifier" not in row.model_fields_set
    out = prepare_rows(
        [row],
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=True,
            raw_loader=lambda _r: raw,
        ),
    )[0]
    assert out.patient_identifier == "FROM_DICOM"


def test_prepare_rows_link_without_full_header_infer():
    """link_oct_enface_series reads linkage keys only when infer flag is False."""
    enface_sop = "1.2.3.enface.linkonly"
    oct_sop = "1.2.3.oct.linkonly"
    oct_series = "1.2.3.oct.series.linkonly"
    for_uid = "1.2.3.for.linkonly"

    enface_ds = _base_file_dataset(sop_instance_uid=enface_sop)
    enface_ds.PatientID = "SHOULD_NOT_FILL"
    enface_ds.Modality = "OP"
    enface_ds.ImageType = ["ORIGINAL", "PRIMARY", "", "RED"]
    enface_ds.SeriesInstanceUID = "1.2.3.enface.series.linkonly"
    enface_ds.FrameOfReferenceUID = for_uid
    enface_ds.Rows = 768
    enface_ds.Columns = 768
    enface_raw = _save_ds(enface_ds)

    oct_ds = _base_file_dataset(
        sop_instance_uid=oct_sop,
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.4",
    )
    oct_ds.PatientID = "SHOULD_NOT_FILL"
    oct_ds.Modality = "OPT"
    oct_ds.SeriesInstanceUID = oct_series
    oct_ds.FrameOfReferenceUID = for_uid
    oct_ds.NumberOfFrames = 37
    oct_ds.Rows = 496
    oct_ds.Columns = 512
    ref_item = Dataset()
    ref_item.ReferencedSOPClassUID = "1.2.840.10008.5.1.4.1.1.77.1.5.1"
    ref_item.ReferencedSOPInstanceUID = enface_sop
    shared = Dataset()
    shared.ReferencedImageSequence = Sequence([ref_item])
    oct_ds.SharedFunctionalGroupsSequence = Sequence([shared])
    oct_raw = _save_ds(oct_ds)

    by_key = {"enface.dcm": enface_raw, "oct.dcm": oct_raw}

    out = prepare_rows(
        [
            ImportRow(
                project_name="p",
                storage_backend_key="sb",
                object_key="enface.dcm",
                image_storage_format="dicom",
            ),
            ImportRow(
                project_name="p",
                storage_backend_key="sb",
                object_key="oct.dcm",
                image_storage_format="dicom",
            ),
        ],
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=False,
            link_oct_enface_series=True,
            raw_loader=lambda r: by_key.get(r.object_key or ""),
        ),
    )
    assert out[0].series_instance_uid == oct_series
    assert out[1].series_instance_uid == oct_series
    assert out[0].patient_identifier is None
    assert out[1].patient_identifier is None
    assert out[0].width is None
    assert out[1].width is None
    assert out[0].modality is None
    assert out[1].modality is None
    assert out[0].dicom_modality is None
    assert out[1].dicom_modality is None
    assert out[0].sop_instance_uid == enface_sop
    assert out[1].sop_instance_uid == oct_sop


def test_prepare_rows_csv_empty_patient_still_filled_from_dicom(tmp_path):
    from eyened_orm.importer.import_csv import read_import_rows_csv

    ds = _base_file_dataset(sop_instance_uid="1.2.3.csv")
    ds.PatientID = "FROM_DICOM"
    ds.SeriesInstanceUID = "1.2.3.csv.series"
    raw = _save_ds(ds)

    csv_path = tmp_path / "rows.csv"
    csv_path.write_text(
        "project_name,storage_backend_key,object_key,image_storage_format,patient_identifier\n"
        "p,sb,vol.dcm,dicom,\n",
        encoding="utf-8",
    )
    rows = read_import_rows_csv(csv_path)
    assert "patient_identifier" not in rows[0].model_fields_set

    out = prepare_rows(
        rows,
        options=PreparationOptions(
            infer_image_format=False,
            infer_metadata_from_dicom_header=True,
            raw_loader=lambda _r: raw,
        ),
    )[0]
    assert out.patient_identifier == "FROM_DICOM"


def test_prepare_rows_warns_when_link_cannot_read_headers(caplog):
    row = ImportRow(
        project_name="p",
        storage_backend_key="missing",
        object_key="missing.dcm",
        image_storage_format="dicom",
    )
    with caplog.at_level("WARNING", logger="eyened_orm.importer.preparation.pipeline"):
        prepare_rows(
            [row],
            options=PreparationOptions(
                infer_image_format=False,
                infer_metadata_from_dicom_header=True,
                link_oct_enface_series=True,
                raw_loader=lambda _r: None,
            ),
        )
    assert any("no DICOM headers were read" in r.message for r in caplog.records)


def test_prepare_rows_warns_opt_mapped_to_oct_not_octa(caplog):
    ds = _base_file_dataset(
        sop_instance_uid="1.2.840.10008.1.2.3.opt.warn",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.4",
    )
    ds.Modality = "OPT"
    ds.SeriesInstanceUID = "1.2.840.10008.1.2.3.opt.warn.series"
    raw = _save_ds(ds)

    with caplog.at_level("WARNING", logger="eyened_orm.importer.preparation.pipeline"):
        prepare_rows(
            [
                ImportRow(
                    project_name="p",
                    storage_backend_key="sb",
                    object_key="opt.dcm",
                    image_storage_format="dicom",
                )
            ],
            options=PreparationOptions(
                infer_image_format=False,
                infer_metadata_from_dicom_header=True,
                raw_loader=lambda _r: raw,
            ),
        )
    assert any("OCTA is not inferred" in r.message for r in caplog.records)


def test_prepare_rows_warns_op_without_viewer_modality(caplog):
    ds = _base_file_dataset(sop_instance_uid="1.2.840.10008.1.2.3.op.warn")
    ds.Modality = "OP"
    ds.Rows = 64
    ds.Columns = 64
    ds.SeriesInstanceUID = "1.2.840.10008.1.2.3.op.warn.series"
    raw = _save_ds(ds)

    with caplog.at_level("WARNING", logger="eyened_orm.importer.preparation.pipeline"):
        prepare_rows(
            [
                ImportRow(
                    project_name="p",
                    storage_backend_key="sb",
                    object_key="op.dcm",
                    image_storage_format="dicom",
                )
            ],
            options=PreparationOptions(
                infer_image_format=False,
                infer_metadata_from_dicom_header=True,
                raw_loader=lambda _r: raw,
            ),
        )
    assert any("without a recognized ImageType subtype" in r.message for r in caplog.records)
