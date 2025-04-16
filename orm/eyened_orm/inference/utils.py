from datetime import datetime

import torch
import torch.nn.functional as F
from sqlalchemy import update
from tqdm import tqdm

from eyened_orm import (
    ImageInstance,
)


def transform_kps(colname):
    from rtnls_fundusprep.cfi_bounds import CFIBounds

    def transform_fn(row):
        bounds = row["bounds"]
        bounds = CFIBounds(**bounds)

        M = bounds.get_cropping_transform(1024)
        kps = M.apply_inverse([[row[f"prep_{colname}_x"], row[f"prep_{colname}_y"]]])
        return kps[0].tolist()

    return transform_fn


def logits_to_continuous_score(logits, temperature=3.0):
    logits = torch.tensor(logits, dtype=torch.float32) / temperature
    probs = F.softmax(logits, dim=-1)
    num_classes = len(logits)
    class_indices = torch.arange(num_classes, dtype=torch.float32).flip(dims=[0])
    continuous_score = torch.sum(probs * class_indices).item()
    return continuous_score


def postprocess(df):
    # df["bounds"] = df.apply(add_hw_to_bounds, axis=1)
    df["discedge"] = df.apply(transform_kps("discedge"), axis=1)
    df["fovea"] = df.apply(transform_kps("fovea"), axis=1)
    df["score"] = df[["q1", "q2", "q3"]].apply(
        lambda row: logits_to_continuous_score(row.values), axis=1
    )
    return df


def update_database(session, df, commit=True, N=10000):
    from rtnls_fundusprep.cfi_bounds import CFIBounds

    updates = [
        {
            "ImageInstanceID": index,
            "CFROI": CFIBounds(**row["bounds"]).to_dict_all(),
            "CFKeypoints": {
                "fovea_xy": row["fovea"],
                "disc_edge_xy": row["discedge"],
                "prep_fovea_xy": [row["prep_fovea_x"], row["prep_fovea_y"]],
                "prep_disc_edge_xy": [row["prep_discedge_x"], row["prep_discedge_y"]],
            },
            "DatePreprocessed": datetime.now(),
            "CFQuality": row["score"],
        }
        for index, row in tqdm(df.iterrows())
    ]

    for i in range(0, len(updates), N):
        print(f"Processing {i} to {i + N}")
        session.execute(update(ImageInstance), updates[i : i + N])
        if commit:
            session.commit()


def clear_unsuccessfull(session, df, commit=True):
    # if the bounds detection is unsuccessfull:
    # - set DatePreprocessed to now
    # - set CFROI to {success: False}
    # - clear all the derived fields
    updates = [
        {
            "ImageInstanceID": index,
            "CFROI": {"success": False},
            "CFKeypoints": None,
            "DatePreprocessed": datetime.now(),
            "CFQuality": None,
        }
        for index, row in tqdm(df.iterrows())
    ]

    session.execute(update(ImageInstance), updates)
    if commit:
        session.commit()
