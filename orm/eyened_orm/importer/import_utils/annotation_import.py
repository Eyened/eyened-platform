import os
import shutil
from typing import Optional
from sqlalchemy.orm import select
from eyened_orm import (
    ImageInstance,
    Segmentation,
    Feature, Creator, SegmentationType, SegmentationData)


def find_annotation(instance: ImageInstance,
                    creator: Creator,
                    annotationtype: SegmentationType,
                    feature: Feature,
                    session) -> Optional[Segmentation]:
    statement = (select(Segmentation)
                 .where(Segmentation.ImageInstanceID == instance.ImageInstanceID,
                        Segmentation.AnnotationTypeID == annotationtype.AnnotationTypeID,
                        Segmentation.FeatureID == feature.FeatureID,
                        Segmentation.CreatorID == creator.CreatorID)
                 )
    result = session.scalars(statement)
    if len(result) == 1:
        return result.one()
    elif len(result) > 1:
        raise ValueError(
            f'Multiple annotations found for {instance.ImageInstanceID} {annotationtype.AnnotationTypeID} {feature.FeatureID} {creator.CreatorID}')
    else:
        return None


def import_annotation_from_file(
        instance: ImageInstance,
        creator: Creator,
        annotationtype: SegmentationType,
        feature: Feature,
        filepath,
        session,
        mode="create",
        ScanNr=0):
    """Import an annotation from a file into the database.
    Attaches to existing annotation/annotation data if found, otherwise creates a new one if mode is "create".
    
    Args:
        instance (ImageInstance): The image instance to associate the annotation with.
        creator (Creator): The creator of the annotation.
        annotationtype (AnnotationType): The type of annotation.
        feature (Feature): The feature represented in the file.
        filepath (str): Path to the annotation file to import.
        session (Session): SQLAlchemy database session.
        mode (str, optional): Operation mode - "create" creates if not found, otherwise errors. Defaults to "create".
        ScanNr (int, optional): Scan number for the annotation data. Defaults to 0.

    Raises:
        ValueError: If annotation not found and mode is not "create".
        ValueError: If annotation data not found and mode is not "create".

    Returns:
        Annotation: The created or updated annotation object.
    """
    annotation = find_annotation(
        instance, creator, annotationtype, feature, session)

    if annotation is None:
        if mode == "create":
            annotation = Segmentation.create(
                instance, feature, creator, annotationtype)
            session.add(annotation)
            session.flush()
        else:
            raise ValueError(
                f'Annotation {instance.ImageInstanceID} {annotationtype.AnnotationTypeID} {feature.FeatureID} {creator.CreatorID} not found')

    annotationdata = next(
        (a for a in annotation.AnnotationData if a.ScanNr == ScanNr), None)
    extension = os.path.splitext(filepath)[1]
    if annotationdata is None:
        if mode == "create":
            annotationdata = SegmentationData.create(
                annotation, extension, ScanNr)
            session.add(annotationdata)
            session.commit()
        else:
            raise ValueError(
                f'AnnotationData {instance.ImageInstanceID} {annotationtype.AnnotationTypeID} {feature.FeatureID} {creator.CreatorID} not found')
    new_filepath = annotationdata.path
    directory = os.path.dirname(new_filepath)
    os.makedirs(directory, exist_ok=True)
    shutil.copyfile(filepath, new_filepath)

    return annotation
