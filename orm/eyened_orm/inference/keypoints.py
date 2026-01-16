from eyened_orm import (
    AttributesModel,
    AttributeDefinition,
    AttributeDataType,
    AttributeValue,
    ImageInstance,
)
from rtnls_fundusprep.mask_extraction import get_cfi_bounds
from rtnls_inference.utils import load_image
from rtnls_inference.ensembles import HeatmapRegressionEnsemble
from multi_process_inference import MultiProcessInference, InferencePipeline

from os import PathLike
from typing import List, Tuple, Any, TypeAlias

import torch
import numpy as np
from tqdm import tqdm

# Type aliases for CFIKeypointsPipeline
PreprocessedItem: TypeAlias = Tuple[Any, np.ndarray]
GPUOutput: TypeAlias = Tuple[np.ndarray, np.ndarray]
KeypointResult: TypeAlias = Tuple[Tuple[float, float], Tuple[float, float]]


def normalize(im, ce=None):
    mean = 0.485, 0.456, 0.406
    std = 0.229, 0.224, 0.225
    assert im.dtype == np.uint8

    im_norm = (im / 255.0 - mean) / std
    if ce is not None:
        ce_norm = (ce / 255.0 - mean) / std
        return np.concatenate([im_norm, ce_norm], axis=2)
    return im_norm


def preprocess_image(image_path, resize=512, apply_ce=True):
    image = load_image(image_path)
    bounds = get_cfi_bounds(image)
    T, bounds_cropped = bounds.crop(resize)
    im = bounds_cropped.image
    ce = bounds_cropped.contrast_enhanced_5 if apply_ce else None
    return T, normalize(im, ce)


def extract_max_keypoint(heatmap_ensemble):
    res_ensemble_mean = heatmap_ensemble.mean(axis=0)
    _, h, w = res_ensemble_mean.shape
    return np.unravel_index(res_ensemble_mean[0].argmax(), (h, w))


def get_coordinate(T, heatmap):
    y, x = extract_max_keypoint(heatmap)
    x, y = T.apply_inverse([[x + 0.5, y + 0.5]])[0]  # + 0.5 to center the pixel
    return (float(x), float(y))


class CFIKeypointsPipeline(
    InferencePipeline[PreprocessedItem, GPUOutput, KeypointResult]
):
    """Concrete implementation of InferencePipeline for CFI keypoints detection.

    This pipeline processes fundus images to detect fovea and disc edge keypoints
    using ensemble models.
    """

    def __init__(
        self,
        ensemble_fovea: HeatmapRegressionEnsemble,
        ensemble_discedge: HeatmapRegressionEnsemble,
        device: torch.device,
        resize: int,
        apply_ce: bool,
    ):
        """Initialize the CFI keypoints pipeline.

        Args:
            ensemble_fovea: Ensemble model for fovea detection
            ensemble_discedge: Ensemble model for disc edge detection
            device: PyTorch device to run inference on
            resize: Target resize dimension for preprocessing
            apply_ce: Whether to apply contrast enhancement
        """
        self.ensemble_fovea = ensemble_fovea
        self.ensemble_discedge = ensemble_discedge
        self.device = device
        self.resize = resize
        self.apply_ce = apply_ce

    def preprocess(self, image_path: PathLike[str]) -> PreprocessedItem:
        """Preprocess a single image path.

        Returns:
            Tuple of (T, x_im) where T is the transformation matrix and
            x_im is the normalized HWC numpy array
        """
        return preprocess_image(image_path, resize=self.resize, apply_ce=self.apply_ce)

    def gpu_batch_process(self, prep_batch: List[PreprocessedItem]) -> List[GPUOutput]:
        """Process a batch of preprocessed images on GPU.

        Args:
            prep_batch: List of (T, x_im) tuples where x_im is HWC numpy array

        Returns:
            List of (fovea_heatmap, disc_edge_heatmap) tuples
        """
        # Stack images and convert to CHW format for PyTorch
        x_np = np.stack([x_im.transpose(2, 0, 1) for _, x_im in prep_batch], axis=0)
        x_in = torch.from_numpy(x_np).to(device=self.device, dtype=torch.float32)

        with torch.no_grad():
            fovea_heatmap = self.ensemble_fovea.forward(x_in)
            disc_edge_heatmap = self.ensemble_discedge.forward(x_in)

        fovea_heatmap = fovea_heatmap.detach().cpu().numpy()
        disc_edge_heatmap = disc_edge_heatmap.detach().cpu().numpy()

        return list(zip(fovea_heatmap, disc_edge_heatmap))

    def postprocess(
        self,
        prep_item: PreprocessedItem,
        gpu_output: GPUOutput,
    ) -> KeypointResult:
        """Postprocess GPU outputs to extract keypoint coordinates.

        Args:
            prep_item: The (T, x_im) tuple from preprocessing
            gpu_output: The (fovea_heatmap, disc_edge_heatmap) tuple from GPU processing

        Returns:
            Tuple of ((fovea_x, fovea_y), (disc_edge_x, disc_edge_y))
        """
        fovea_heatmap, disc_edge_heatmap = gpu_output
        T, _ = prep_item
        fovea_xy = get_coordinate(T, fovea_heatmap)
        disc_edge_xy = get_coordinate(T, disc_edge_heatmap)
        return fovea_xy, disc_edge_xy


class CFIKeypoints:

    def __init__(self, session):
        self.session = session
        self.model = AttributesModel.get_or_create(
            session,
            match_by={"ModelName": "CFI_Keypoints", "Version": "july24"},
            create_kwargs={
                "Description": "https://github.com/Eyened/retinalysis-inference Eyened/vascx:fovea Eyened/vascx:discedge"
            },
        )
        self.attr_definition = AttributeDefinition.get_or_create(
            session,
            match_by={
                "AttributeName": "CFI_Keypoints",
                "AttributeDataType": AttributeDataType.JSON,
            },
        )

    def run(self, image_ids: List[int], device: torch.device):
        print("loading fovea models")
        ensemble_fovea = HeatmapRegressionEnsemble.from_huggingface(
            "Eyened/vascx:fovea/fovea_july24.pt"
        ).to(device)

        print("loading discedge models")
        ensemble_discedge = HeatmapRegressionEnsemble.from_huggingface(
            "Eyened/vascx:discedge/discedge_july24.pt"
        ).to(device)

        resize = ensemble_fovea.config["datamodule"]["test_transform"]["resize"]
        apply_ce = ensemble_fovea.config["datamodule"]["test_transform"][
            "contrast_enhance"
        ]

        images = ImageInstance.by_ids(self.session, image_ids)
        items = [(iid, image.path) for iid, image in images.items()]

        # Create pipeline instance
        pipeline = CFIKeypointsPipeline(
            ensemble_fovea=ensemble_fovea,
            ensemble_discedge=ensemble_discedge,
            device=device,
            resize=resize,
            apply_ce=apply_ce,
        )

        mpi = MultiProcessInference(
            items,
            pipeline=pipeline,
            n_workers=4,
            batch_size=8,
        )

        for iid, (fovea_xy, disc_edge_xy) in tqdm(
            mpi.run(),
            total=len(image_ids),
        ):
            value = {
                "fovea_xy": fovea_xy,
                "disc_edge_xy": disc_edge_xy,
            }
            AttributeValue.upsert(
                self.session,
                match_by={
                    "AttributeID": self.attr_definition.AttributeID,
                    "ModelID": self.model.ModelID,
                    "ImageInstanceID": iid,
                },
                update_values={"ValueJSON": value},
            )
