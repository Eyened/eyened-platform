import torch
from rtnls_inference import RegressionEnsemble
from rtnls_inference.utils import decollate_batch
from eyened_orm import ImageInstance

from eyened_orm import (
    AttributesModel,
    AttributeDefinition,
    AttributeDataType,
    AttributeValue,
)
import os
from tqdm import tqdm

def run_odfd_model(database, device, batch_size, path, model_version, skip_existing):

    if device is None:
        device = "cpu"
    else:
        device = torch.device(device)

    with open(path, "r") as f:
        image_ids = {int(line.strip()) for line in f.readlines()}


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

        if skip_existing:

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
        else:
            print(f"Running {len(image_ids)} images")
        images = ImageInstance.by_ids(session, image_ids)
        
        # ids and paths need to be lists for the dataloader (corresponding indices)
        ids = list(images.keys())
        paths = [image.path for image in images.values()]
        

    print(f"Loading model {model_version} from {os.getenv('RTNLS_MODEL_RELEASES')}")
    ensemble = RegressionEnsemble.from_release(f"{model_version}.pt").to(device)

    dataloader = ensemble._make_inference_dataloader(
        paths,
        ids=ids,
        num_workers=batch_size,
        preprocess=True,
        batch_size=batch_size,
    )
    with torch.no_grad():
        # Note: DataLoader errors can be raised during iteration (__next__) before the loop body runs.
        # To be able to catch-and-continue, we need to manually call next() on the iterator.
        it = iter(dataloader)
        try:
            total = len(dataloader)
        except TypeError:
            total = None
        pbar = tqdm(total=total)

        while True:
            try:
                batch = next(it)
            except StopIteration:
                break
            except Exception as e:
                print(e)
                pbar.update(1)
                continue

            if len(batch) == 0:
                pbar.update(1)
                continue

            im = batch["image"].to(device)
            val = (
                ensemble.forward(im).mean(dim=0).detach().cpu()
            )  # average the model dimension

            batch["val"] = val
            items = decollate_batch(batch)

            for item in items:
                scaling_factor = item["metadata"]["bounds"]["radius"] / 512
                val = item["val"] * 1024 * scaling_factor
                image_id = item["id"]
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
            pbar.update(1)

        pbar.close()