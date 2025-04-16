import json
import warnings
import numpy as np

from sqlalchemy import select
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.exc import MultipleResultsFound

from eyened_orm import (
    ImageInstance,
    Annotation,
    Feature, Creator)

from .annotation_export import get_center_of_gravity_3d, load_segmentation_3d

def measure_thickness_subfovea_2d(session, annotation, diameter_mm=1.0, creatorname=None):
    imageinstance = annotation.ImageInstance
    fovea_x = find_fovea_x_location(session, imageinstance, creatorname=creatorname)
    segmentation = load_segmentation_3d(annotation)
    segmentation = segmentation[0]
    thickness = np.sum(segmentation, axis=0) * imageinstance.ResolutionAxial
    diameter_pix = 0.5 * diameter_mm / imageinstance.ResolutionHorizontal
    start_x = int(np.round(fovea_x - diameter_pix))
    end_x = int(np.round(fovea_x + diameter_pix))
    thickness_around_fovea = np.mean(thickness[start_x:end_x])
    return thickness_around_fovea

def find_fovea_x_location(session, instance: ImageInstance, creatorname=None):

    ## Could be annotated as ETDRS grid or as Fovea
    etrds_grids = get_all_etrds_grids(session, instance, creatorname)
    fovea_segmentations  = get_all_fovea_segmentations(session, instance, creatorname)
    if len(etrds_grids) + len(fovea_segmentations) > 1:
        warnings.warn(f"Multiple fovea locations found for {instance.ImageInstanceID}.", UserWarning)
    if len(fovea_segmentations) > 0:
        return fovea_x_from_segmentation(fovea_segmentations[0])
    elif len(etrds_grids) > 0:
        return fovea_x_from_ETDRS(etrds_grids[0])
    else:
        raise ValueError(f"No fovea location found for {instance.ImageInstanceID}")

def get_all_etrds_grids(session, instance: ImageInstance, creatorname=None):
    query = (select(Annotation)
                .join(ImageInstance)
                .join(Feature)
                .where(Feature.FeatureName == 'ETDRS grid',
                    ImageInstance.ImageInstanceID == instance.ImageInstanceID,
                    Annotation.Inactive == None))
    if creatorname is not None:
        query = query.join(Creator).where(Creator.CreatorName == creatorname)
    return session.execute(query).scalars().all()

def get_all_fovea_segmentations(session, instance: ImageInstance, creatorname=None):
    query = (select(Annotation)
                .join(ImageInstance)
                .join(Feature)
                .where(Feature.FeatureName == 'Fovea',
                    ImageInstance.ImageInstanceID == instance.ImageInstanceID,
                    Annotation.Inactive == None))
    if creatorname is not None:
        query = query.join(Creator).where(Creator.CreatorName == creatorname)
    return session.execute(query).scalars().all()

def fovea_x_from_segmentation(annotation):
    _, _, x = get_center_of_gravity_3d(annotation)
    return x

def fovea_x_from_ETDRS(annotation):
    annotation_path = annotation.AnnotationData[0].get_path()
    with open(annotation_path) as f:
        data = json.load(f)
    if 'fovea' in data:	
        fovea = data['fovea']['location']['x']
        return fovea
    else:
        raise KeyError(f'No fovea found in ETDRS grid')
    