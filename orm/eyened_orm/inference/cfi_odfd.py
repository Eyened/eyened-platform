import os
from os import PathLike
from typing import Any, Iterable, List, Optional, Tuple

import numpy as np
import torch

from eyened_orm import AttributeDataType
from eyened_orm.inference.attribute_inference import AttributeInferencePipeline
from eyened_orm.inference.utils import preprocess_image
from rtnls_inference import RegressionEnsemble


class CFI_ODFD(AttributeInferencePipeline):
    """CFI Optic Disc to Fovea Distance estimation pipeline."""

    model_name = "CFI_ODFD"
    model_version = "odfd_march25"
    model_description = (
        "Estimates the distance from the fovea to optic disc border in pixels"
    )
    attribute_name = "CFI_ODFD"
    attribute_data_type = AttributeDataType.Float

    def __init__(
        self,
        session,
        device: torch.device,
        n_workers: int = 8,
        batch_size: int = 8,
        **kwargs,
    ):
        super().__init__(
            session,
            n_workers=n_workers,
            batch_size=batch_size,
            device=device,
        )
        self.ensemble: Optional[RegressionEnsemble] = None
        self.resize: Optional[int] = None

    def _load_models(self) -> None:
        """Load regression ensemble model."""
        print(
            f"Loading model {self.model_version} from {os.getenv('RTNLS_MODEL_RELEASES')}"
        )
        self.ensemble = RegressionEnsemble.from_release(f"{self.model_version}.pt").to(
            self.device
        )
        assert self.ensemble.config["datamodule"]["test_transform"]["resize"] == 512
        self.resize = 512

    def preprocess(self, image_path: PathLike[str]) -> Tuple[Any, np.ndarray]:
        """Preprocess image for ODFD estimation."""
        return preprocess_image(image_path, resize=self.resize)

    def process_batch(
        self, prep_batch: List[Tuple[Any, np.ndarray]]
    ) -> Iterable[float]:
        """Process batch: ensemble averaging and extract first channel."""
        x_in = self._prepare_torch_batch(prep_batch)
        result = self._run_torch_forward(x_in, self.ensemble.forward)

        # Ensemble averaging: result is (num_models, batch_size, 1)
        # Average over ensemble (axis=0), extract channel [:, 0]
        return result.mean(axis=0)[:, 0]

    def postprocess(
        self, prep_item: Tuple[Any, np.ndarray], batch_output: float
    ) -> float:
        """Transform distance from resized coordinates to original image coordinates."""
        T, _ = prep_item
        x = self.resize * batch_output
        # Get distance from origin in original image
        # Assume x/y scale is the same
        p0, p1 = T.apply_inverse(((0, 0), (x, 0)))
        return float(np.linalg.norm(p1 - p0))
