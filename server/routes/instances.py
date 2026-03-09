from typing import Optional

from eyened_orm import (
    ImageInstance,
    ImageStorage,
    Tag,
    ImageInstanceTagLink,
    Series,
    Study,
    Patient,
    DeviceInstance,
    Segmentation,
    ModelSegmentation,
    FormAnnotation,
)
from eyened_orm.tag import SegmentationTagLink, FormAnnotationTagLink, TagType
from fastapi import APIRouter, Depends, HTTPException, Response

from sqlalchemy.orm import Session, selectinload

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_instances import ImageGET
from ..dtos.dtos_aux import ObjectTagPOST, ObjectTagPATCH, TagMeta

from .auth import CurrentUser, get_current_user, is_authenticated
from ..db import get_db
from ..utils.db_logging import get_db_logger


router = APIRouter()


def _get_image_instance_by_public_id(
    db: Session, public_id: str
) -> Optional[ImageInstance]:
    item = (
        db.query(ImageInstance)
        .options(
            selectinload(ImageInstance.ImageStorages).selectinload(
                ImageStorage.StorageBackend
            )
        )
        .filter(ImageInstance.PublicID == public_id)
        .first()
    )
    return item


@router.get("/instances/{instance_id}", response_model=ImageGET)
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
        selectinload(ImageInstance.Series)
        .selectinload(Series.Study)
        .selectinload(Study.Patient)
        .selectinload(Patient.Project),
        selectinload(ImageInstance.DeviceInstance).selectinload(
            DeviceInstance.DeviceModel
        ),
        selectinload(ImageInstance.Scan),
        selectinload(ImageInstance.ImageStorages).selectinload(
            ImageStorage.StorageBackend
        ),
        # instance tags
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
            ImageInstanceTagLink.Tag
        ),
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
            ImageInstanceTagLink.Creator
        ),
    ]
    if with_segmentations:
        opts += [
            selectinload(ImageInstance.Segmentations).selectinload(
                Segmentation.Feature
            ),
            selectinload(ImageInstance.Segmentations).selectinload(
                Segmentation.Creator
            ),
            selectinload(ImageInstance.Segmentations)
            .selectinload(Segmentation.SegmentationTagLinks)
            .selectinload(SegmentationTagLink.Tag),
            selectinload(ImageInstance.Segmentations)
            .selectinload(Segmentation.SegmentationTagLinks)
            .selectinload(SegmentationTagLink.Creator),
        ]
    if with_form_annotations:
        opts += [
            selectinload(ImageInstance.FormAnnotations)
            .selectinload(FormAnnotation.FormAnnotationTagLinks)
            .selectinload(FormAnnotationTagLink.Tag),
            selectinload(ImageInstance.FormAnnotations)
            .selectinload(FormAnnotation.FormAnnotationTagLinks)
            .selectinload(FormAnnotationTagLink.Creator),
        ]
    if with_model_segmentations:
        opts += [
            selectinload(ImageInstance.ModelSegmentations).selectinload(
                ModelSegmentation.Model
            ),
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


@router.get("/images/{image_id}", response_model=ImageGET)
async def get_public_image(
    image_id: str,
    with_segmentations: bool = False,
    with_form_annotations: bool = False,
    with_model_segmentations: bool = False,
    with_tag_metadata: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    opts = [
        # base graph
        selectinload(ImageInstance.Series)
        .selectinload(Series.Study)
        .selectinload(Study.Patient)
        .selectinload(Patient.Project),
        selectinload(ImageInstance.DeviceInstance).selectinload(
            DeviceInstance.DeviceModel
        ),
        selectinload(ImageInstance.Scan),
        selectinload(ImageInstance.ImageStorages).selectinload(
            ImageStorage.StorageBackend
        ),
        # instance tags
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
            ImageInstanceTagLink.Tag
        ),
        selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
            ImageInstanceTagLink.Creator
        ),
    ]
    if with_segmentations:
        opts += [
            selectinload(ImageInstance.Segmentations).selectinload(
                Segmentation.Feature
            ),
            selectinload(ImageInstance.Segmentations).selectinload(
                Segmentation.Creator
            ),
            selectinload(ImageInstance.Segmentations)
            .selectinload(Segmentation.SegmentationTagLinks)
            .selectinload(SegmentationTagLink.Tag),
            selectinload(ImageInstance.Segmentations)
            .selectinload(Segmentation.SegmentationTagLinks)
            .selectinload(SegmentationTagLink.Creator),
        ]
    if with_form_annotations:
        opts += [
            selectinload(ImageInstance.FormAnnotations)
            .selectinload(FormAnnotation.FormAnnotationTagLinks)
            .selectinload(FormAnnotationTagLink.Tag),
            selectinload(ImageInstance.FormAnnotations)
            .selectinload(FormAnnotation.FormAnnotationTagLinks)
            .selectinload(FormAnnotationTagLink.Creator),
        ]
    if with_model_segmentations:
        opts += [
            selectinload(ImageInstance.ModelSegmentations).selectinload(
                ModelSegmentation.Model
            ),
            # optional if Model.Feature relationship is added later:
            # selectinload(ImageInstance.ModelSegmentations).selectinload(ModelSegmentation.Model).selectinload(Model.Feature),
        ]

    item = (
        db.query(ImageInstance)
        .options(*opts)
        .filter(ImageInstance.PublicID == image_id)
        .first()
    )
    if not item and image_id.isdigit():
        item = db.get(ImageInstance, int(image_id), options=tuple(opts))
    if not item:
        raise HTTPException(404, "ImageInstance not found")

    return DTOConverter.image_instance_to_get(
        item,
        with_tag_metadata=with_tag_metadata,
        with_segmentations=with_segmentations,
        with_form_annotations=with_form_annotations,
        with_model_segmentations=with_model_segmentations,
    )


def build_storage_redirect_response(path: str) -> Response:
    response = Response()
    response.headers["X-Accel-Redirect"] = path
    return response


@router.get("/images/{image_id}/data")
async def get_public_image_data(
    image_id: str,
    index: Optional[int] = None,
    meta: bool = False,
    _: bool = Depends(is_authenticated),
    db: Session = Depends(get_db),
):
    item = _get_image_instance_by_public_id(db, image_id)
    if not item:
        raise HTTPException(404, "ImageInstance not found")
    if index is not None and index < 0:
        raise HTTPException(400, "index must be >= 0")

    storage = item.primary_storage
    if not storage:
        raise HTTPException(422, "Primary image storage not found")
    if not storage.StorageBackend or not storage.StorageBackend.Key:
        raise HTTPException(422, "Primary image storage has no storage backend")
    if not storage.ObjectKey:
        raise HTTPException(422, "Primary image storage has no ObjectKey")

    base_path = f"/{storage.StorageBackend.Key}/{storage.ObjectKey}"
    if storage.Format == "png_series":
        path, source_id = storage.ObjectKey.rsplit("/", 1)
        if meta:
            return build_storage_redirect_response(f"/{storage.StorageBackend.Key}/{path}/metadata.json")
        if index is None:
            raise HTTPException(
                422, "Index is required for png_series format if not fetching metadata"
            )
        return build_storage_redirect_response(f"/{storage.StorageBackend.Key}/{path}/{source_id}_{index}.png")
    elif storage.Format == "dicom":
        return build_storage_redirect_response(f"{base_path}")
    elif storage.Format == "binary":
        if meta:
            suffix = ".json"
        else:
            suffix = ".binary"
        return build_storage_redirect_response(f"{base_path}{suffix}")
    elif storage.Format == "image/png" or storage.Format == "image/jpeg":
        return build_storage_redirect_response(f"{base_path}")
    else:
        raise HTTPException(422, "Primary image storage has unknown format")


@router.get("/images/{image_id}/thumbnail")
async def get_public_image_thumbnail(
    image_id: str,
    size: int = 144,
    _: bool = Depends(is_authenticated),
    db: Session = Depends(get_db),
):
    item = _get_image_instance_by_public_id(db, image_id)
    if not item:
        raise HTTPException(404, "ImageInstance not found")

    return build_storage_redirect_response(
        f"/thumbnails/{item.ThumbnailPath}_{size}.jpg"
    )


@router.get("/instances/images/{dataset_identifier:path}")
async def get_file(
    dataset_identifier: str,
    _: bool = Depends(is_authenticated),
):
    # Set X-Accel-Redirect header to tell NGINX to serve the file
    response = Response()
    response.headers["X-Accel-Redirect"] = "/files/" + dataset_identifier
    return response


@router.get("/instances/thumbnails/{thumbnail_identifier:path}")
async def get_thumb(
    thumbnail_identifier: str,
    _: bool = Depends(is_authenticated),
):
    response = Response()
    response.headers["X-Accel-Redirect"] = "/thumbnails/" + thumbnail_identifier
    return response


@router.post("/instances/{instance_id}/tags", response_model=TagMeta)
async def tag_instance(
    instance_id: str,
    body: ObjectTagPOST,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to an ImageInstance by tag ID (idempotent)."""
    instance = _get_image_instance_by_public_id(db, instance_id)
    if not instance:
        raise HTTPException(404, "ImageInstance not found")
    tag = db.get(Tag, body.tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag.TagType != TagType.ImageInstance:
        raise HTTPException(400, "Tag type must be ImageInstance")

    link = db.get(
        ImageInstanceTagLink,
        {"TagID": tag.TagID, "ImageInstanceID": instance.ImageInstanceID},
    )
    if not link:
        link = ImageInstanceTagLink(
            TagID=tag.TagID,
            ImageInstanceID=instance.ImageInstanceID,
            CreatorID=current_user.id,
            Comment=body.comment,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        link.Tag = tag  # optional: avoid Tag lazy-load

        # Log tag link creation
        logger = get_db_logger()
        if logger:
            logger.log_insert(
                user=current_user.username,
                user_id=current_user.id,
                endpoint=f"POST /api/instances/{instance_id}/tags",
                entity="ImageInstanceTagLink",
                fields={
                    "tag_id": tag.TagID,
                    "image_instance_id": instance.ImageInstanceID,
                    "comment": body.comment,
                },
            )
    else:
        if body.comment is not None:
            old_comment = link.Comment
            link.Comment = body.comment
            db.commit()
            db.refresh(link)

            # Log tag link update
            logger = get_db_logger()
            if logger:
                logger.log_update(
                    user=current_user.username,
                    user_id=current_user.id,
                    endpoint=f"POST /api/instances/{instance_id}/tags",
                    entity="ImageInstanceTagLink",
                    fields={"tag_id": tag.TagID, "image_instance_id": instance_id},
                    changes={"comment": f"{old_comment} -> {body.comment}"},
                )

    return DTOConverter.link_to_tag_metadata(link)


@router.patch("/instances/{instance_id}/tags/{tag_id}", response_model=TagMeta)
async def patch_instance_tag(
    instance_id: str,
    tag_id: int,
    body: ObjectTagPATCH,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Update comment on an existing ImageInstance tag link."""
    instance = _get_image_instance_by_public_id(db, instance_id)
    if not instance:
        raise HTTPException(404, "ImageInstance not found")
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag.TagType != TagType.ImageInstance:
        raise HTTPException(400, "Tag type must be ImageInstance")

    link = db.get(
        ImageInstanceTagLink,
        {"TagID": tag_id, "ImageInstanceID": instance.ImageInstanceID},
    )
    if not link:
        raise HTTPException(404, "Link not found")

    if body.comment is not None:
        old_comment = link.Comment
        link.Comment = body.comment
        db.commit()
        db.refresh(link)

        # Log tag link update
        logger = get_db_logger()
        if logger:
            logger.log_update(
                user=current_user.username,
                user_id=current_user.id,
                endpoint=f"PATCH /api/instances/{instance_id}/tags/{tag_id}",
                entity="ImageInstanceTagLink",
                fields={
                    "tag_id": tag_id,
                    "image_instance_id": instance.ImageInstanceID,
                },
                changes={"comment": f"{old_comment} -> {body.comment}"},
            )

    link.Tag = tag
    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/instances/{instance_id}/tags/{tag_id}", status_code=204)
async def untag_instance(
    instance_id: str,
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from an ImageInstance (idempotent)."""
    instance = _get_image_instance_by_public_id(db, instance_id)
    if not instance:
        raise HTTPException(404, "ImageInstance not found")
    link = db.get(
        ImageInstanceTagLink,
        {"TagID": tag_id, "ImageInstanceID": instance.ImageInstanceID},
    )
    if link:
        # Save link data for logging before deletion
        deleted_data = {
            "tag_id": tag_id,
            "image_instance_id": instance.ImageInstanceID,
            "comment": link.Comment,
            "creator_id": link.CreatorID,
        }

        db.delete(link)
        db.commit()

        # Log tag link deletion
        logger = get_db_logger()
        if logger:
            logger.log_delete(
                user=current_user.username,
                user_id=current_user.id,
                endpoint=f"DELETE /api/instances/{instance_id}/tags/{tag_id}",
                entity="ImageInstanceTagLink",
                fields={"tag_id": tag_id, "image_instance_id": instance_id},
                deleted_data=deleted_data,
            )

    return Response(status_code=204)
