from pathlib import Path

import pandas as pd
import torch
from rtnls_inference.ensembles import HeatmapRegressionEnsemble
from rtnls_inference.ensembles.ensemble_classification import ClassificationEnsemble
from rtnls_inference.ensembles.ensemble_keypoints import KeypointsEnsemble
from rtnls_inference.utils import decollate_batch, extract_keypoints_from_heatmaps
from sqlalchemy import select
from tqdm import tqdm

from eyened_orm import ImageInstance, Modality
from .utils import auto_device


def run_basic_models(fpaths, ids, device: torch.device = None):
    if device is None:
        device = auto_device()
    ensemble_fovea = HeatmapRegressionEnsemble.from_huggingface('Eyened/vascx:fovea/fovea_july24.pt').to(
        device
    )
    ensemble_discedge = KeypointsEnsemble.from_huggingface('Eyened/vascx:discedge/discedge.pt').to(device)

    dataloader = ensemble_fovea._make_inference_dataloader(
        fpaths,
        ids=ids,
        num_workers=8,
        preprocess=False,
        batch_size=8,
    )

    output_ids, outputs = [], []
    with torch.no_grad():
        for batch in tqdm(dataloader):
            if len(batch) == 0:
                continue

            im = batch["image"].to(device)
            im_rgb = im[..., :3, :, :]  # only rgb part

            # FOVEA DETECTION
            with torch.autocast(device_type=device.type):
                heatmap = ensemble_fovea.forward(im)
            keypoints = extract_keypoints_from_heatmaps(heatmap)

            kp_fovea = torch.mean(keypoints, dim=1)  # average over models

            # DISC EDGE
            keypoints = ensemble_discedge.forward(im_rgb)

            keypoints = keypoints[
                :, :, None, :
            ]  # MNC2 (models, batch_size, num_keypoints, 2)

            if ensemble_discedge.config["datamodule"].get("normalize_keypoints", True):
                n, c, h, w = batch["image"].shape
                keypoints[..., 0] = (keypoints[..., 0]) * w
                keypoints[..., 1] = (keypoints[..., 1]) * h

            kp_discedge = torch.mean(keypoints, dim=0)  # average over models
            # we make a pseudo-batch with the outputs and everything needed for undoing transforms

            # join keypoints
            keypoints = torch.cat([kp_fovea, kp_discedge], dim=1)

            items = {"id": batch["id"], "keypoints": keypoints}
            if "bounds" in batch:
                items["bounds"] = batch["bounds"]
            items = decollate_batch(items)

            items = [dataloader.dataset.transform.undo_item(item) for item in items]

            for item in items:
                output_ids.append(item["id"])
                outputs.append(
                    [
                        *item["keypoints"][0].tolist(),
                        *item["keypoints"][1].tolist(),
                    ]
                )
    return pd.DataFrame(
        outputs,
        index=output_ids,
        columns=["x_fovea", "y_fovea", "x_disc", "y_disc"],
    )


def run_quality_model(fpaths, ids, device: torch.device = None):
    if device is None:
        device = auto_device()
    ensemble_quality = ClassificationEnsemble.from_release('Eyened/vascx:quality/quality.pt').to(device)
    dataloader = ensemble_quality._make_inference_dataloader(
        fpaths,
        ids=ids,
        num_workers=8,
        preprocess=False,
        batch_size=16,
    )

    output_ids, outputs = [], []
    with torch.no_grad():
        for batch in tqdm(dataloader):
            if len(batch) == 0:
                continue

            im = batch["image"].to(device)

            # QUALITY
            quality = ensemble_quality.predict_step(im)
            quality = torch.mean(quality, dim=0)

            items = {"id": batch["id"], "quality": quality}
            items = decollate_batch(items)

            for item in items:
                output_ids.append(item["id"])
                outputs.append(item["quality"].tolist())

    return pd.DataFrame(
        outputs,
        index=output_ids,
        columns=["q1", "q2", "q3"],
    )


def run_inference_for_images(session, images, device: torch.device = None, cfi_cache_path=None):
    from rtnls_fundusprep.preprocessor import parallel_preprocess
    if device is None:
        device = auto_device()
    

    ids = [im.ImageInstanceID for im in images]
    paths = [im.path for im in images]

    bounds = parallel_preprocess(
        paths,  # List of image files
        ids,
        rgb_path=cfi_cache_path / "rgb"
        if cfi_cache_path is not None
        else None,  # Output path for RGB images
        ce_path=cfi_cache_path / "ce"
        if cfi_cache_path is not None
        else None,  # Output path for Contrast Enhanced images
        n_jobs=8,  # number of preprocessing workers
    )

    df_bounds = pd.DataFrame(bounds).set_index("id")

    # Continue only with successfully preprocessed images
    ids = df_bounds[
        df_bounds["success"]
    ].index.tolist()  # only run on successfully preprocessed images
    fpaths = [
        (
            cfi_cache_path / "rgb" / f"{id}.png",
            cfi_cache_path / "ce" / f"{id}.png",
        )
        for id in ids
    ]

    # Run the models
    df_model_outputs = run_basic_models(fpaths, ids, device)
    fpaths = [fp[0] for fp in fpaths]
    df_quality = run_quality_model(fpaths, ids, device)

    # Update the DB
    from .utils import clear_unsuccessfull, postprocess, update_database

    df = pd.merge(
        df_bounds, df_model_outputs, left_index=True, right_index=True, how="left"
    )
    df = pd.merge(df, df_quality, left_index=True, right_index=True, how="left")
    df = df.rename(
        columns={
            "x_fovea": "prep_fovea_x",
            "y_fovea": "prep_fovea_y",
            "x_disc": "prep_discedge_x",
            "y_disc": "prep_discedge_y",
        }
    )

    df_successfull = df[df["success"]]
    df_unsucessfull = df[~df["success"]]

    df_successfull = postprocess(df_successfull)
    update_database(session, df_successfull)
    clear_unsuccessfull(session, df_unsucessfull)


def run_inference(session, device: torch.device = None, cfi_cache_path=None):
    if device is None:
        device = auto_device()
        
    # We run preprocessing + inference on all ColorFundus images with DatePreprocessed==None
    images = (
        session.execute(
            select(ImageInstance).where(
                (ImageInstance.Modality == Modality.ColorFundus)
                & (ImageInstance.DatePreprocessed == None)
            )
        )
        .scalars()
        .all()
    )

    if len(images) == 0:
        print("No images to process")
        return
    print(f"Found {len(images)} CFI images to process")

    # Run inference
    run_inference_for_images(session, images, device, cfi_cache_path=cfi_cache_path)
