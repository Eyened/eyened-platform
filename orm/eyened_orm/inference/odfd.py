import os
from os import PathLike
from typing import Any, List, Tuple, TypeAlias

import numpy as np
import torch
from tqdm import tqdm

from rtnls_inference import RegressionEnsemble

from eyened_orm import ImageInstance
from eyened_orm import (
    AttributesModel,
    AttributeDefinition,
    AttributeDataType,
    AttributeValue,
)
from eyened_orm.inference.keypoints import preprocess_image
from eyened_orm.inference.multi_process_inference import (
    InferencePipeline,
    MultiProcessInference,
)

PreprocessedItem: TypeAlias = Tuple[Any, np.ndarray]
GPUOutput: TypeAlias = float


class ODFDPipeline(InferencePipeline[PreprocessedItem, GPUOutput, float]):
    def __init__(self, ensemble: RegressionEnsemble, device: torch.device, resize: int):
        self.ensemble = ensemble
        self.device = device
        self.resize = resize

    def preprocess(self, image_path: PathLike[str]) -> PreprocessedItem:
        return preprocess_image(image_path, resize=self.resize, apply_ce=False)

    def gpu_batch_process(self, prep_batch: List[PreprocessedItem]) -> List[GPUOutput]:
        x_np = np.stack([x_im.transpose(2, 0, 1) for _, x_im in prep_batch], axis=0)
        x_in = torch.from_numpy(x_np).to(device=self.device, dtype=torch.float32)
        with torch.no_grad():
            result = self.ensemble.forward(x_in)
        return result.mean(dim=0).detach().cpu().numpy()[:, 0].tolist()

    def postprocess(self, prep_item: PreprocessedItem, gpu_output: GPUOutput) -> float:
        T, _ = prep_item
        x = self.resize * gpu_output
        # get distance from origin in original image
        # assume x/y scale is the same
        p0, p1 = T.apply_inverse(((0, 0), (x, 0)))
        return float(np.linalg.norm(p1 - p0))


def run_odfd_model(database, device, batch_size, path, model_version, overwrite):
    if device is None:
        device = "cpu"
    else:
        device = torch.device(device)

    with open(path, "r") as f:
        image_ids = {int(line.strip()) for line in f.readlines()}

    print(f"Loading model {model_version} from {os.getenv('RTNLS_MODEL_RELEASES')}")
    ensemble = RegressionEnsemble.from_release(f"{model_version}.pt").to(device)
    resize = 512

    with database.get_session() as session:
        model = AttributesModel.get_or_create(
            session,
            match_by={"ModelName": "ODFD", "Version": model_version},
            create_kwargs={
                "Description": "Estimates the distance from the fovea to optic disc border in pixels"
            },
        )
        attr_definition = AttributeDefinition.get_or_create(
            session,
            match_by={
                "AttributeName": "ODFD",
                "AttributeDataType": AttributeDataType.Float,
            },
        )
        model_id = model.ModelID
        attr_id = attr_definition.AttributeID

        if not overwrite:
            existing_ids = set(
                AttributeValue.select(
                    session,
                    "ImageInstanceID",
                    AttributeID=attr_id,
                    ModelID=model_id,
                    ImageInstanceID=image_ids,
                )
            )
            print(f"Skipping {len(existing_ids)} existing images")
            image_ids = image_ids - existing_ids

        if not image_ids:
            print("No images to run on")
            return

        print(f"Running {len(image_ids)} images")
        images = ImageInstance.by_ids(session, image_ids)
        items = [(iid, image.path) for iid, image in images.items()]

        pipeline = ODFDPipeline(ensemble=ensemble, device=device, resize=resize)
        mpi = MultiProcessInference(
            items,
            pipeline=pipeline,
            n_workers=batch_size,
            batch_size=batch_size,
        )

        for image_id, val in tqdm(mpi.run(), total=len(image_ids)):
            AttributeValue.upsert(
                session,
                match_by={
                    "AttributeID": attr_id,
                    "ModelID": model_id,
                    "ImageInstanceID": image_id,
                },
                update_values={"ValueFloat": val},
            )
            session.commit()
