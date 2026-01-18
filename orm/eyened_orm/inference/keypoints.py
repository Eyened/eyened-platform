from os import PathLike
from typing import Any, Iterable, List, Optional, Tuple

import numpy as np
import torch

from eyened_orm import AttributeDataType
from eyened_orm.inference.attribute_inference import AttributeInferencePipeline
from eyened_orm.inference.utils import preprocess_image
from rtnls_inference.ensembles import HeatmapRegressionEnsemble


def extract_max_keypoint(heatmap):
    """Extract the maximum keypoint location from heatmap.

    Args:
        heatmap: Heatmap array with shape (h, w) or (1, h, w)

    Returns:
        Tuple of (y, x) coordinates of maximum value
    """
    # Handle both (h, w) and (1, h, w) shapes
    if len(heatmap.shape) == 3:
        heatmap = heatmap[0]
    h, w = heatmap.shape
    return np.unravel_index(heatmap.argmax(), (h, w))


def get_coordinate(T, heatmap):
    """Transform keypoint coordinate from resized to original image coordinates."""
    y, x = extract_max_keypoint(heatmap)
    x, y = T.apply_inverse([[x + 0.5, y + 0.5]])[0]  # + 0.5 to center the pixel
    return (float(x), float(y))


class CFIKeypoints(AttributeInferencePipeline):
    """CFI keypoints detection pipeline - detects fovea and disc edge locations."""

    model_name = "CFI_Keypoints"
    model_version = "july24"
    model_description = "https://github.com/Eyened/retinalysis-inference Eyened/vascx:fovea Eyened/vascx:discedge"
    attribute_name = "CFI_Keypoints"
    attribute_data_type = AttributeDataType.JSON

    def __init__(
        self,
        session,
        device: torch.device,
        n_workers: int = 4,
        batch_size: int = 8,
    ):
        super().__init__(
            session, n_workers=n_workers, batch_size=batch_size, device=device
        )
        self.ensemble_fovea: Optional[HeatmapRegressionEnsemble] = None
        self.ensemble_discedge: Optional[HeatmapRegressionEnsemble] = None
        self.resize: Optional[int] = None
        self.apply_ce: Optional[bool] = None

    def _load_models(self) -> None:
        """Load both fovea and disc edge ensemble models."""
        print("loading fovea models")
        self.ensemble_fovea = HeatmapRegressionEnsemble.from_huggingface(
            "Eyened/vascx:fovea/fovea_july24.pt"
        ).to(self.device)

        print("loading discedge models")
        self.ensemble_discedge = HeatmapRegressionEnsemble.from_huggingface(
            "Eyened/vascx:discedge/discedge_july24.pt"
        ).to(self.device)

        assert (
            self.ensemble_fovea.config["datamodule"]["test_transform"]["resize"] == 512
        )
        assert (
            self.ensemble_discedge.config["datamodule"]["test_transform"]["resize"]
            == 512
        )
        assert self.ensemble_fovea.config["datamodule"]["test_transform"][
            "contrast_enhance"
        ]
        assert self.ensemble_discedge.config["datamodule"]["test_transform"][
            "contrast_enhance"
        ]

        self.resize = 512
        self.apply_ce = True

    def preprocess(self, image_path: PathLike[str]) -> Tuple[Any, np.ndarray]:
        """Preprocess image for keypoint detection."""
        return preprocess_image(image_path, resize=self.resize, apply_ce=self.apply_ce)

    def process_batch(
        self, prep_batch: List[Tuple[Any, np.ndarray]]
    ) -> Iterable[Tuple[np.ndarray, np.ndarray]]:
        """Process batch with two ensembles (fovea and disc edge)."""
        x_in = self._prepare_torch_batch(prep_batch)

        fovea_heatmap = self._run_torch_forward(x_in, self.ensemble_fovea.forward)
        disc_edge_heatmap = self._run_torch_forward(
            x_in, self.ensemble_discedge.forward
        )

        # Average over ensemble dimension (axis=1) to get (batch_size, _, h, w)
        fovea_heatmap = fovea_heatmap.mean(axis=1)
        disc_edge_heatmap = disc_edge_heatmap.mean(axis=1)

        return zip(fovea_heatmap, disc_edge_heatmap)

    def postprocess(
        self,
        prep_item: Tuple[Any, np.ndarray],
        batch_output: Tuple[np.ndarray, np.ndarray],
    ) -> dict:
        """Extract coordinates from heatmaps and return as dictionary."""
        fovea_heatmap, disc_edge_heatmap = batch_output
        T, _ = prep_item
        return {
            "fovea_xy": get_coordinate(T, fovea_heatmap),
            "disc_edge_xy": get_coordinate(T, disc_edge_heatmap),
        }
