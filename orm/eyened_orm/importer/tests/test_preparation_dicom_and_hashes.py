from __future__ import annotations

import io

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from eyened_orm.image_instance import ModalityType
from eyened_orm.importer.importer_dtos import ImportRow
from eyened_orm.importer.preparation.dicom_meta import dicom_header_patches_from_bytes
from eyened_orm.importer.preparation.hashes import md5_hex, sha256_bytes
from eyened_orm.importer.preparation.pipeline import PreparationOptions, prepare_rows


def _minimal_dicom_bytes() -> bytes:
    file_meta = FileMetaDataset()
    file_meta.FileMetaInformationVersion = b"\x00\x01"
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    file_meta.MediaStorageSOPInstanceUID = "1.2.3.4.5.6.7.8.9"
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = "1.2.3.4.5"

    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.Modality = "OP"
    ds.Rows = 64
    ds.Columns = 128
    ds.SeriesInstanceUID = "1.2.840.10008.1.2.3.4.5.6.1"
    ds.StudyInstanceUID = "1.2.840.10008.1.2.3.4.5.6.2"
    ds.SeriesNumber = 3
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    buf = io.BytesIO()
    ds.save_as(buf)
    return buf.getvalue()


def test_dicom_header_patches_from_bytes():
    raw = _minimal_dicom_bytes()
    p = dicom_header_patches_from_bytes(raw)
    assert p["sop_instance_uid"] == "1.2.3.4.5.6.7.8.9"
    assert p["dicom_modality"] == ModalityType.OP
    assert p["height"] == 64
    assert p["width"] == 128
    assert p["series_instance_uid"] == "1.2.840.10008.1.2.3.4.5.6.1"
    assert p["study_instance_uid"] == "1.2.840.10008.1.2.3.4.5.6.2"
    assert p["series_number"] == 3


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
        read_dicom_header=True,
        raw_loader=_loader,
    )
    out = prepare_rows([row], options=opts)[0]
    assert out.sop_instance_uid == "1.2.3.4.5.6.7.8.9"
    assert out.width == 128
    assert out.height == 64


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
