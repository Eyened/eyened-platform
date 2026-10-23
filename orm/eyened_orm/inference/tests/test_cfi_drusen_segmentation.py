"""CFI drusen segmentation storage and Processor wiring."""

from __future__ import annotations

import numpy as np

from eyened_orm import Feature, ModelSegmentation, SegmentationModel
from eyened_orm.commands.tests.test_targets import _import_images
from eyened_orm.inference.cfi_drusen_segmentation import CFI_Drusen, run_for_image_ids

DESCRIPTION = "https://github.com/Eyened/amd-features"
MATRIX = [[1.0, 0.0, 2.0], [0.0, 1.0, 3.0], [0.0, 0.0, 1.0]]


class _NativeProcessor:
    def __init__(self):
        self.calls = []

    def process(self, image):
        raise AssertionError("native run must keep the 1024 field of view")

    def process_with_transform(self, image):
        self.calls.append(("fov", tuple(image.shape)))
        mask = np.full((8, 8), 0.8, dtype=np.float32)
        return {"M": MATRIX, "hw": [image.shape[0], image.shape[1]]}, mask


class _UpscaleProcessor:
    def __init__(self):
        self.calls = []

    def process(self, image):
        self.calls.append(("full", tuple(image.shape)))
        return np.full(image.shape[:2], 0.9, dtype=np.float32)

    def process_with_transform(self, image):
        raise AssertionError("upscale run must restore the original photo")


def _prepare_image(image, *, height: int, width: int) -> None:
    image.Rows_y = height
    image.Columns_x = width
    image.NrOfFrames = 1


def _pipeline(session, processor, *, undo_transform: bool, overwrite: bool = False):
    pipeline = CFI_Drusen(
        session,
        device="cpu",
        undo_transform=undo_transform,
        overwrite=overwrite,
    )
    pipeline.processor = processor
    pipeline._models_loaded = True
    return pipeline


def _capture_writes(monkeypatch):
    written = []

    def fake_write_data(self, data, axis=None, slice_index=None):
        written.append(np.asarray(data))
        return 0

    monkeypatch.setattr(ModelSegmentation, "write_data", fake_write_data)
    return written


def test_registers_drusen_feature_and_model_version_4(session):
    pipeline = CFI_Drusen(session, device="cpu")

    assert pipeline.feature.FeatureName == "Drusen"
    assert pipeline.model.ModelName == "Drusen"
    assert pipeline.model.Version == "4"
    assert pipeline.model.Description == DESCRIPTION
    assert pipeline.model.FeatureID == pipeline.feature.FeatureID

    again = CFI_Drusen(session, device="cpu")
    assert again.model.ModelID == pipeline.model.ModelID
    assert (
        session.query(SegmentationModel)
        .filter_by(ModelName="Drusen", Version="4")
        .count()
        == 1
    )
    assert session.query(Feature).filter_by(FeatureName="Drusen").count() == 1


def test_run_loads_pixels_through_orm_not_raw_path(session, monkeypatch):
    """DICOM and other formats are decoded via ``ImageInstance.pixel_array``."""
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=8, width=8)
    session.commit()

    seen: list[int] = []
    monkeypatch.setattr(
        "eyened_orm.inference.utils.load_fundus_rgb",
        lambda inst: seen.append(inst.ImageInstanceID)
        or np.zeros((8, 8, 3), dtype=np.uint8),
    )
    pipeline = _pipeline(session, _NativeProcessor(), undo_transform=False)
    pipeline.run([image.ImageInstanceID])
    assert seen == [image.ImageInstanceID]


def test_run_stores_field_of_view_mask_and_transform(session, monkeypatch):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=32, width=32)
    session.commit()

    written = _capture_writes(monkeypatch)
    processor = _NativeProcessor()
    rgb = np.zeros((32, 32, 3), dtype=np.uint8)
    monkeypatch.setattr(
        "eyened_orm.inference.utils.load_fundus_rgb",
        lambda _image: rgb,
    )
    pipeline = _pipeline(session, processor, undo_transform=False)
    pipeline.run([image.ImageInstanceID])

    assert processor.calls == [("fov", (32, 32, 3))]
    row = ModelSegmentation.by_column(
        session,
        ImageInstanceID=image.ImageInstanceID,
        ModelID=pipeline.model.ModelID,
    )
    assert row.Height == 8
    assert row.Width == 8
    assert row.Depth == 1
    assert row.ImageProjectionMatrix == MATRIX
    assert len(written) == 1
    assert written[0].shape == (8, 8)
    assert written[0].dtype == np.uint8
    assert written[0][0, 0] == 204


def test_run_upscale_stores_original_size_without_matrix(session, monkeypatch):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=16, width=20)
    session.commit()

    written = _capture_writes(monkeypatch)
    processor = _UpscaleProcessor()
    monkeypatch.setattr(
        "eyened_orm.inference.utils.load_fundus_rgb",
        lambda _image: np.zeros((16, 20, 3), dtype=np.uint8),
    )
    pipeline = _pipeline(session, processor, undo_transform=True)
    pipeline.run([image.ImageInstanceID])

    assert processor.calls == [("full", (16, 20, 3))]
    row = ModelSegmentation.by_column(
        session,
        ImageInstanceID=image.ImageInstanceID,
        ModelID=pipeline.model.ModelID,
    )
    assert row.Height == 16
    assert row.Width == 20
    assert row.ImageProjectionMatrix is None
    assert written[0][0, 0] == 229


def test_run_skips_pixels_below_threshold(session, monkeypatch):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=8, width=8)
    session.commit()

    written = _capture_writes(monkeypatch)

    class _Quiet(_NativeProcessor):
        def process_with_transform(self, image):
            mask = np.full((4, 4), 0.1, dtype=np.float32)
            return {"M": MATRIX, "hw": [8, 8]}, mask

    pipeline = _pipeline(session, _Quiet(), undo_transform=False)
    monkeypatch.setattr(
        "eyened_orm.inference.utils.load_fundus_rgb",
        lambda _image: np.zeros((8, 8, 3), dtype=np.uint8),
    )
    pipeline.run([image.ImageInstanceID])
    assert written == []


def test_run_for_image_ids_skips_images_that_already_have_drusen(
    session, monkeypatch
):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=16, width=16)
    session.commit()

    _capture_writes(monkeypatch)
    processor = _NativeProcessor()
    monkeypatch.setattr(
        "eyened_orm.inference.cfi_drusen_segmentation._make_processor",
        lambda device: processor,
    )
    monkeypatch.setattr(
        "eyened_orm.inference.utils.load_fundus_rgb",
        lambda _image: np.zeros((16, 16, 3), dtype=np.uint8),
    )

    run_for_image_ids(session, [image.ImageInstanceID], device="cpu", upscale=False)
    assert len(processor.calls) == 1

    run_for_image_ids(session, [image.ImageInstanceID], device="cpu", upscale=False)
    assert len(processor.calls) == 1


def test_run_for_image_ids_upscale_flag_uses_full_resolution(session, monkeypatch):
    _proj, images = _import_images(session, count=1)
    image = images[0]
    _prepare_image(image, height=12, width=12)
    session.commit()

    _capture_writes(monkeypatch)
    processor = _UpscaleProcessor()
    monkeypatch.setattr(
        "eyened_orm.inference.cfi_drusen_segmentation._make_processor",
        lambda device: processor,
    )
    monkeypatch.setattr(
        "eyened_orm.inference.utils.load_fundus_rgb",
        lambda _image: np.zeros((12, 12, 3), dtype=np.uint8),
    )

    run_for_image_ids(session, [image.ImageInstanceID], device="cpu", upscale=True)
    assert processor.calls == [("full", (12, 12, 3))]
