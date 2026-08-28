"""Tests for ETDRS grid summaries."""

from __future__ import annotations

import numpy as np
from skimage import measure

from eyened_orm.reports.etdrs_masks import ETDRS_masks


def _masks() -> ETDRS_masks:
    # 0.05 mm/pix: CSF r=10px, inner r=30px, outer r=60px
    return ETDRS_masks(h=200, w=200, fovea_x=100, fovea_y=100, resolution=0.05, laterality="R")


def _blob(h, w, cy, cx, radius=2):
    yy, xx = np.ogrid[:h, :w]
    return (yy - cy) ** 2 + (xx - cx) ** 2 <= radius**2


def _per_field_summary(masks: ETDRS_masks, binary, fields, **kwargs):
    """Original per-field label/regionprops implementation (reference)."""
    include_area = kwargs.get("include_area", True)
    include_count = kwargs.get("include_count", True)
    include_largest = kwargs.get("include_largest", True)
    skip_zero = kwargs.get("skip_zero", True)
    result = {}
    for field in fields:
        masked = getattr(masks, field) & binary
        if include_area:
            result[f"{field}_area"] = masks.calculate_area(masked)
        if include_largest or include_count:
            labeled = measure.label(masked)
            if include_count:
                result[f"{field}_count"] = int(np.max(labeled))
            if include_largest:
                regions = measure.regionprops(labeled)
                result[f"{field}_largest"] = float(
                    max((r.area for r in regions), default=0) * masks.pixel_area
                )
    if skip_zero:
        result = {k: v for k, v in result.items() if v}
    return result


def test_rings_partition_3mm_grid():
    masks = _masks()
    np.testing.assert_array_equal(
        masks.center | masks.inner | masks.outer, masks.grid
    )
    assert not (masks.center & masks.inner).any()
    assert not (masks.center & masks.outer).any()
    assert not (masks.inner & masks.outer).any()


def test_ring_pixel_counts_pin_sqrt_distance_boundaries():
    # Golden pin at resolution=0.075 / 200x200 / fovea (100,100).
    # At this spacing, 12 Pythagorean-triple offsets sit exactly on the 1.5 mm
    # ring boundary under np.sqrt(dx*dx + dy*dy); a hypot-based distance flips
    # those pixels across rings on some NumPy builds. Counts are from the
    # long-standing sqrt formulation and must stay stable.
    masks = ETDRS_masks(
        h=200, w=200, fovea_x=100, fovea_y=100, resolution=0.075, laterality="R"
    )
    assert int(masks.center.sum()) == 137
    assert int(masks.inner.sum()) == 1108
    assert int(masks.outer.sum()) == 3768
    assert int(masks.grid.sum()) == 5013
    np.testing.assert_array_equal(
        masks.center | masks.inner | masks.outer, masks.grid
    )
    # Pixels at exact 1.5 mm (sqrt) belong to outer, not inner.
    boundary_yx = [
        (80, 100),
        (84, 88),
        (84, 112),
        (88, 84),
        (88, 116),
        (100, 80),
        (100, 120),
        (112, 84),
        (112, 116),
        (116, 88),
        (116, 112),
        (120, 100),
    ]
    for y, x in boundary_yx:
        assert masks.outer[y, x] and not masks.inner[y, x], (y, x)


def test_grid_does_not_materialize_rings():
    masks = _masks()
    _ = masks.grid
    assert "center" not in masks.__dict__
    assert "inner" not in masks.__dict__
    assert "outer" not in masks.__dict__


def test_get_summary_matches_per_field_for_compact_lesions():
    masks = _masks()
    binary = np.zeros((200, 200), dtype=bool)
    binary |= _blob(200, 200, 100, 100, radius=3)  # CSF
    binary |= _blob(200, 200, 80, 100, radius=2)  # superior inner
    binary |= _blob(200, 200, 100, 130, radius=2)  # temporal or nasal inner (R: right=nasal)

    expected = _per_field_summary(masks, binary, ETDRS_masks.all_fields)
    actual = masks.get_summary(binary, ETDRS_masks.all_fields)
    assert actual == expected


def test_get_summary_labels_and_regionprops_once(monkeypatch):
    masks = _masks()
    binary = np.zeros((200, 200), dtype=bool)
    binary |= _blob(200, 200, 100, 100, radius=3)
    binary |= _blob(200, 200, 80, 100, radius=2)

    label_calls = []
    regionprops_calls = []
    real_label = measure.label
    real_regionprops = measure.regionprops

    def counting_label(image, *args, **kwargs):
        label_calls.append(np.asarray(image).shape)
        return real_label(image, *args, **kwargs)

    def counting_regionprops(label_image, *args, **kwargs):
        regionprops_calls.append(np.asarray(label_image).shape)
        return real_regionprops(label_image, *args, **kwargs)

    monkeypatch.setattr(
        "eyened_orm.reports.etdrs_masks.measure.label", counting_label
    )
    monkeypatch.setattr(
        "eyened_orm.reports.etdrs_masks.measure.regionprops", counting_regionprops
    )

    masks.get_summary(binary, ETDRS_masks.all_fields)

    assert len(label_calls) == 1
    assert len(regionprops_calls) == 1
