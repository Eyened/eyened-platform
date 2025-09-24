from eyened_orm import (
    ImageInstance, Tag, ImageInstanceTagLink,
    Series, Study, Patient, Project, DeviceInstance, DeviceModel, Scan,
    Segmentation, ModelSegmentation, Model, Feature, FormAnnotation,
)
from eyened_orm.Tag import SegmentationTagLink, FormAnnotationTagLink
from eyened_orm.Tag import TagType
from fastapi import APIRouter, Depends, HTTPException, Response

from sqlalchemy.orm import Session, selectinload

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_instances import InstanceGET
from ..dtos.dtos_aux import ObjectTagPOST, TagMeta

from .auth import CurrentUser, get_current_user
from ..db import get_db

router = APIRouter()

@router.get("/instances/{instance_id}", response_model=InstanceGET)
async def get_instance(
    instance_id: int,
    with_segmentations: bool = False,
    with_form_annotations: bool = False,
    with_model_segmentations: bool = False,
    with_tag_metadata: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    opts = [
        # base graph
        selectinload(ImageInstance.Series).selectinload(Series.Study).selectinload(Study.Patient).selectinload(Patient.Project),
        selectinload(ImageInstance.DeviceInstance).selectinload(DeviceInstance.DeviceModel),
        selectinload(ImageInstance.Scan),
        # instance tags
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Tag),
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Creator),
    ]
    if with_segmentations:
        opts += [
            selectinload(ImageInstance.Segmentations).selectinload(Segmentation.Feature),
            selectinload(ImageInstance.Segmentations).selectinload(Segmentation.Creator),
            selectinload(ImageInstance.Segmentations).selectinload(Segmentation.SegmentationTagLinks).selectinload(SegmentationTagLink.Tag),
            selectinload(ImageInstance.Segmentations).selectinload(Segmentation.SegmentationTagLinks).selectinload(SegmentationTagLink.Creator),
        ]
    if with_form_annotations:
        opts += [
            selectinload(ImageInstance.FormAnnotations).selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(FormAnnotationTagLink.Tag),
            selectinload(ImageInstance.FormAnnotations).selectinload(FormAnnotation.FormAnnotationTagLinks).selectinload(FormAnnotationTagLink.Creator),
        ]
    if with_model_segmentations:
        opts += [
            selectinload(ImageInstance.ModelSegmentations).selectinload(ModelSegmentation.Model),
            # optional if Model.Feature relationship is added later:
            # selectinload(ImageInstance.ModelSegmentations).selectinload(ModelSegmentation.Model).selectinload(Model.Feature),
        ]

    item = db.get(ImageInstance, instance_id, options=tuple(opts))
    if not item:
        raise HTTPException(404, "ImageInstance not found")

    return DTOConverter.image_instance_to_get(
        item,
        with_tag_metadata=with_tag_metadata,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )


@router.get("/instances/images/{dataset_identifier:path}")
async def get_file(
    dataset_identifier: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    # Set X-Accel-Redirect header to tell NGINX to serve the file
    response = Response()
    response.headers["X-Accel-Redirect"] = "/files/" + dataset_identifier
    return response


@router.get("/instances/thumbnails/{thumbnail_identifier:path}")
async def get_thumb(
    thumbnail_identifier: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    response = Response()
    response.headers["X-Accel-Redirect"] = "/thumbnails/" + thumbnail_identifier
    return response


@router.post("/instances/{instance_id}/tags", response_model=TagMeta)
async def tag_instance(instance_id: int, body: ObjectTagPOST, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)) -> TagMeta:
    """Attach a Tag to an ImageInstance by tag ID (idempotent)."""
    instance = db.get(ImageInstance, instance_id)
    if not instance:
        raise HTTPException(404, "ImageInstance not found")
    tag = db.get(Tag, body.tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag.TagType != TagType.ImageInstance:
        raise HTTPException(400, "Tag type must be ImageInstance")

    link = db.get(ImageInstanceTagLink, {"TagID": tag.TagID, "ImageInstanceID": instance_id})
    if not link:
        link = ImageInstanceTagLink(TagID=tag.TagID, ImageInstanceID=instance_id, CreatorID=current_user.id)
        db.add(link); db.commit(); db.refresh(link)
        link.Tag = tag  # optional: avoid Tag lazy-load

    return DTOConverter.link_to_tag_metadata(link)

@router.delete("/instances/{instance_id}/tags/{tag_id}", status_code=204)
async def untag_instance(instance_id: int, tag_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    """Remove a Tag from an ImageInstance (idempotent)."""
    instance = db.get(ImageInstance, instance_id)
    if not instance:
        raise HTTPException(404, "ImageInstance not found")
    link = db.get(ImageInstanceTagLink, {"TagID": tag_id, "ImageInstanceID": instance_id})
    if link:
        db.delete(link); db.commit()
    return Response(status_code=204)
