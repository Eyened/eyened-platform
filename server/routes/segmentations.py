import gzip
import io
from typing import Annotated, Optional

import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import ObjectTagPOST, TagMeta
from ..dtos.dtos_main import SegmentationGET, SegmentationPATCH, SegmentationPOST
from ..services.acting_user import ActingUser
from ..services.segmentation_service import (
    ModelSegmentationService,
    SegmentationService,
    get_model_segmentation_service,
    get_segmentation_service,
)
from .auth import CurrentUser, get_current_user

router = APIRouter()


async def load_array(np_array: Optional[UploadFile]) -> Optional[np.ndarray]:
    """Read an uploaded (optionally gzipped) .npy into a 3D array, or None."""
    if np_array is None:
        return None
    data_content = await np_array.read()
    if np_array.filename.endswith(".gz"):
        with gzip.GzipFile(fileobj=io.BytesIO(data_content)) as f:
            data_content = f.read()
    array = np.load(io.BytesIO(data_content))
    if len(array.shape) != 3:
        raise HTTPException(
            status_code=400,
            detail=f"Segmentation is not 3D, got shape {array.shape}",
        )
    return array


def _segmentation_data_response(arr: Optional[np.ndarray], filename: str) -> Response:
    if arr is None:
        return Response(status_code=204)
    np_buf = io.BytesIO()
    np.save(np_buf, arr)
    gz = gzip.compress(np_buf.getvalue())
    headers = {
        "Content-Encoding": "gzip",
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(len(gz)),
    }
    return Response(content=gz, media_type="application/octet-stream", headers=headers)


@router.post("/segmentations", response_model=SegmentationGET)
async def create_segmentation(
    metadata: Annotated[str, Form()],
    np_array: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    service: SegmentationService = Depends(get_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    dto = SegmentationPOST.model_validate_json(metadata)
    array = await load_array(np_array)
    segmentation = service.create(
        db,
        image_id=dto.image_id,
        feature_id=dto.feature_id,
        subtask_id=dto.subtask_id,
        data_type=dto.data_type,
        data_representation=dto.data_representation,
        depth=dto.depth,
        height=dto.height,
        width=dto.width,
        sparse_axis=dto.sparse_axis,
        image_projection_matrix=dto.image_projection_matrix,
        scan_indices=dto.scan_indices,
        threshold=dto.threshold,
        reference_segmentation_id=dto.reference_segmentation_id,
        array=array,
        actor=ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.segmentation_to_get(segmentation)


@router.get("/segmentations/{segmentation_id}", response_model=SegmentationGET)
async def get_segmentation(
    segmentation_id: int,
    db: Session = Depends(get_db),
    service: SegmentationService = Depends(get_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    item = service.get_segmentation(db, segmentation_id)
    return DTOConverter.segmentation_to_get(item)


@router.delete("/segmentations/{segmentation_id}", status_code=204)
async def delete_segmentation(
    segmentation_id: int,
    db: Session = Depends(get_db),
    service: SegmentationService = Depends(get_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    service.soft_delete(
        db,
        segmentation_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.put("/segmentations/{segmentation_id}/data")
async def update_segmentation_data(
    segmentation_id: int,
    request: Request,
    axis: Optional[int] = None,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    service: SegmentationService = Depends(get_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    content_type = request.headers.get("Content-Type", "").lower()
    if content_type != "application/octet-stream":
        raise HTTPException(
            status_code=400, detail=f"Unsupported media type: {content_type}"
        )
    np_image = np.load(io.BytesIO(await request.body()))
    return service.write_data(
        db,
        segmentation_id,
        np_image,
        axis=axis,
        scan_nr=scan_nr,
        actor=ActingUser(id=current_user.id, username=current_user.username),
    )


@router.get("/segmentations/{segmentation_id}/data")
async def get_segmentation_data(
    segmentation_id: int,
    axis: Optional[int] = None,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    service: SegmentationService = Depends(get_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    arr = service.read_data(db, segmentation_id, axis=axis, scan_nr=scan_nr)
    return _segmentation_data_response(arr, "segmentation.npy.gz")


@router.patch("/segmentations/{segmentation_id}", response_model=SegmentationGET)
async def patch_segmentation(
    segmentation_id: int,
    dto: SegmentationPATCH,
    db: Session = Depends(get_db),
    service: SegmentationService = Depends(get_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    segmentation = service.patch(
        db,
        segmentation_id,
        reference_segmentation_id=dto.reference_segmentation_id,
        feature_id=dto.feature_id,
        threshold=dto.threshold,
        actor=ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.segmentation_to_get(segmentation)


@router.post("/segmentations/{segmentation_id}/tags", response_model=TagMeta)
async def tag_segmentation(
    segmentation_id: int,
    body: ObjectTagPOST,
    db: Session = Depends(get_db),
    service: SegmentationService = Depends(get_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to a Segmentation by tag ID (idempotent)."""
    link = service.tag(
        db,
        segmentation_id,
        body.tag_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/segmentations/{segmentation_id}/tags/{tag_id}", status_code=204)
async def untag_segmentation(
    segmentation_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    service: SegmentationService = Depends(get_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from a Segmentation (idempotent)."""
    service.untag(
        db,
        segmentation_id,
        tag_id,
        ActingUser(id=current_user.id, username=current_user.username),
    )
    return Response(status_code=204)


@router.get("/model-segmentations/{model_segmentation_id}/data")
async def get_model_segmentation_data(
    model_segmentation_id: int,
    axis: Optional[int] = None,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    service: ModelSegmentationService = Depends(get_model_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    arr = service.read_data(db, model_segmentation_id, axis=axis, scan_nr=scan_nr)
    return _segmentation_data_response(arr, "model_segmentation.npy.gz")


@router.put("/model-segmentations/{model_segmentation_id}/data")
async def update_model_segmentation_data(
    model_segmentation_id: int,
    request: Request,
    axis: Optional[int] = None,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    service: ModelSegmentationService = Depends(get_model_segmentation_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    content_type = request.headers.get("Content-Type", "").lower()
    if content_type != "application/octet-stream":
        raise HTTPException(
            status_code=400, detail=f"Unsupported media type: {content_type}"
        )
    np_image = np.load(io.BytesIO(await request.body()))
    return service.write_data(
        db, model_segmentation_id, np_image, axis=axis, scan_nr=scan_nr
    )
