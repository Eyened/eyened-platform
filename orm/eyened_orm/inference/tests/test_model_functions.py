"""Pure post-processing helpers of the torch models."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("torch")


class _Shift:
    """Transform whose inverse adds (10, 20) to ``(x, y)``."""

    def apply_inverse(self, points):
        return np.asarray(points) + [10, 20]


def test_keypoint_is_heatmap_maximum_mapped_to_original_pixels():
    from eyened_orm.inference.cfi_keypoints import get_coordinate

    heatmap = np.zeros((1, 8, 8))
    heatmap[0, 3, 5] = 1.0  # y=3, x=5

    assert get_coordinate(_Shift(), heatmap) == (15.5, 23.5)


def test_quality_score_is_expected_class_index_best_first():
    from eyened_orm.inference.cfi_quality import logits_to_continuous_score

    assert logits_to_continuous_score([100.0, 0.0, 0.0]) == pytest.approx(2.0)
    assert logits_to_continuous_score([0.0, 0.0, 100.0]) == pytest.approx(0.0)
    assert logits_to_continuous_score([0.0, 0.0, 0.0]) == pytest.approx(1.0)
