# %%
from random import sample
import json
import base64
import gzip
from io import BytesIO
import pandas as pd
import numpy as np
from PIL import Image
from tqdm import tqdm
from sqlalchemy import select, func
from eyened_orm import (
    Creator,
    ImageInstance,
    Modality,
    Feature,
    Annotation,
    AnnotationData,
    AnnotationType,
    Segmentation
)
from eyened_orm.Segmentation import Datatype, DataRepresentation
from eyened_orm.db import Database

# %%
database = Database('../dev/eyened_dev.env')
session = database.create_session()

# %%
def get_annotations_with_annotation_type(annotation_type_ids, where=None):
    #
    query = (
        select(Annotation, ImageInstance)
        # .join_from(Annotation, AnnotationData, isouter=True)
        .join_from(Annotation, ImageInstance, isouter=True)
        .join_from(Annotation, Creator)
        .where(
            ~Annotation.Inactive & 
            (Annotation.AnnotationTypeID.in_(annotation_type_ids)) &
            (Annotation.CreatorID != 1) &
            (Creator.IsHuman)
        )
    )
    
    if where is not None:
        query = query.where(where)
    
    all_annots = session.execute(
        query
        .order_by(func.random())
        # .limit(5)
    ).all()
    return all_annots

# %%
# 3	Segmentation OCT B-scan	R/G mask	9613
def open_data(dpath):

    im = Image.open(dpath)

    width, height = im.size
    im = np.array(im)
    new_im = np.zeros((1, height, width), np.uint8)
    if len(im.shape) == 3:
        # both red and green channels
        new_im[0, im[...,0] > 0] = 1
        new_im[0, im[...,1] > 0] = 2
        new_im[0, (im[...,0] > 0) & (im[...,1] > 0)] = 3
    else:
        # only R channel
        new_im[0, im > 0] = 1

    return new_im # DHW

def convert_annotations(annotation_type_id, where=None):
    elems = get_annotations_with_annotation_type([annotation_type_id], where=where)
    annotations = []
    segmentations = []
    # ignore Vessel masks here. They will be inserted with the Artery/Vein annotations
    for annot, image_instance in tqdm(elems):
        depth, height, width = image_instance.shape


        segmentation = Segmentation(
            Depth=depth,
            Height=height,
            Width=width,
            SparseAxis=0,
            ScanIndices=[],
            ImageProjectionMatrix=None,
            DataRepresentation=DataRepresentation.DualBitMask,
            DataType=Datatype.R8UI,
            ImageInstanceID=image_instance.ImageInstanceID,
            CreatorID=annot.CreatorID,
            FeatureID = annot.FeatureID
        )

        session.add(segmentation)
        session.flush([segmentation])

        try:
            if len(annot.AnnotationData) == 0:
                print(f"No annotation data for {annot.AnnotationID}")
                segmentation.write_empty()
            else:
                for annot_data in annot.AnnotationData:
                    im = open_data(annot_data.path)
                    if len(im.shape) != 3:
                        raise RuntimeError(f'Found shape {im.shape} for {annot_data.path}')

                    segmentation.write_data(im.squeeze(), axis=segmentation.SparseAxis, slice_index=annot_data.ScanNr)

            segmentations.append(segmentation)
            annotations.append(annot)
        except Exception as e:
            print(f'Error converting {annot.AnnotationID}: {e}')
            session.expunge(segmentation)
            continue

    session.commit()
    return annotations, segmentations

# %%
# elems = get_annotations_with_annotation_type([3])
# for annot, image_instance in tqdm(elems):
#     if len(annot.AnnotationData) == 0:
#         continue
#     if image_instance.NrOfFrames is None:
#         print(f"Found image_instance.NrOfFrames is None for annot_id: {annot.AnnotationID}, image_instance_id: {image_instance.ImageInstanceID}")

# %%
annotations, segmentations  = convert_annotations(3)
# for annot, seg in zip(annotations, segmentations):
#     print(annot.AnnotationID, seg.SegmentationID, seg.ImageInstanceID)

# %%


# %%


# %%


# %%



