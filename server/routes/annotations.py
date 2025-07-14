import io
import json
from typing import Optional

import numpy as np
from eyened_orm import Annotation, ImageInstance
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()

# this endpoint uses multipart/form-data
# to create an annotation and upload its data at the same time
# it was implemented this way to ensure that the annotation data and metadata are consistent
# if the annotation data (np_array) is not provided, an empty (zeros) annotation is created
# once the annotation is created, its data can be updated using the PUT endpoint
# but only by data with the same shape as the original annotation
@router.post("/segmentations")
async def create_annotation(
    np_array: UploadFile = File(default=None),
    metadata: str = Form(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = Annotation(**json.loads(metadata))    
    annotation.CreatorID = current_user.id
    
    image = ImageInstance.by_id(db, annotation.ImageInstanceID)
    if image is None:
        raise HTTPException(status_code=404, detail="Image instance not found")
    
    # Read and load numpy array
    if np_array:
        data_content = await np_array.read()
        data_buffer = io.BytesIO(data_content)
        np_array = np.load(data_buffer)

        # check that the data is 3D
        if len(np_array.shape) != 3:
            raise HTTPException(status_code=400, detail=f"Annotation data is not 3D, got shape {np_array.shape}")
        
        if annotation.Width is None:
            annotation.Width = np_array.shape[0]
        if annotation.Height is None:
            annotation.Height = np_array.shape[1]
        if annotation.Depth is None:
            annotation.Depth = np_array.shape[2]

    else:
        # create an empty annotation
        if annotation.Width is None and annotation.Height is None and annotation.Depth is None:
            annotation.Height, annotation.Width, annotation.Depth = image.shape
        np_array = np.zeros(annotation.shape, dtype=np.uint8)

    db.add(annotation)
    db.flush()

    #### CONSISTENCY CHECKS ####
    if image.is_2d and annotation.is_2d:
        # one one-dimension should match
        if image.l1_axis != annotation.l1_axis:
            raise HTTPException(status_code=400, detail=f"Image length 1 axis {image.length_1_axis} does not match annotation length 1 axis {annotation.l1_axis}")
        
        if image.shape != annotation.shape and annotation.ImageProjectionMatrix is None:
            raise HTTPException(status_code=400, detail=f"Image shape {image.shape} does not match annotation shape {annotation.shape} and ImageProjectionMatrix is not provided")
        
        annotation.ScanIndices = None
        annotation.SparseAxis = None
        
    elif image.is_3d and annotation.is_2d:
        if annotation.ScanIndices is None or not isinstance(annotation.ScanIndices, int):
            raise HTTPException(status_code=400, detail=f"ScanIndices must be an int for 2D annotations on 3D images")
        
        # scan index must be within the image shape
        if annotation.ScanIndices >= image.shape[annotation.l1_axis]:
            raise HTTPException(status_code=400, detail=f"ScanIndices {annotation.ScanIndices} is out of bounds for image shape {image.shape} along dimension {annotation.l1_axis}")
        
        # check if image and annotation match along dimensions other than the length 1 axis
        if not annotation.shape_matches_image_shape and annotation.ImageProjectionMatrix is None:
            raise HTTPException(status_code=400, detail=f"Annotation shape {annotation.shape} does not match image shape {image.shape} and ImageProjectionMatrix is not provided")
        annotation.SparseAxis = None
        
    elif image.is_3d and annotation.is_3d:
        if image.shape != annotation.shape:
            raise HTTPException(status_code=400, detail=f"3D annotation shape {annotation.shape} does not match image shape {image.shape}")
        
        # SparseAxis and ScanIndices can either be both present or both absent
        if annotation.SparseAxis is not None and annotation.ScanIndices is None:
            raise HTTPException(status_code=400, detail=f"SparseAxis is provided but ScanIndices is not")
        if annotation.SparseAxis is None and annotation.ScanIndices is not None:
            raise HTTPException(status_code=400, detail=f"ScanIndices is provided but SparseAxis is not")
        
        if annotation.ScanIndices is not None:
            if not isinstance(annotation.ScanIndices, list):
                raise HTTPException(status_code=400, detail=f"ScanIndices must be a list for sparse annotations")
            
            # scan indices must be unique and within the image bounds
            for i in annotation.ScanIndices:
                if i >= image.shape[annotation.SparseAxis]:
                    raise HTTPException(status_code=400, detail=f"Scan index {i} is out of bounds for image shape {image.shape} along dimension {annotation.SparseAxis}")
            
    else:
        raise HTTPException(status_code=400, detail=f"Image and annotation shapes are not compatible")

    try:
        annotation.write_data(np_array)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    db.commit()
    db.refresh(annotation)
    return annotation


@router.get("/segmentations/{segmentation_id}")
async def get_annotation(
    segmentation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    item = Annotation.by_id(db, segmentation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return item

@router.put("/segmentations/{segmentation_id}/data", status_code=204)
async def update_annotation_data_file(
    segmentation_id: int,
    request: Request,
    axis: Optional[int] = None,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = Annotation.by_id(db, segmentation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    content_type = request.headers.get("Content-Type", "").lower()

    if content_type not in ["image/png", "application/octet-stream"]:
        raise HTTPException(status_code=400, detail="Unsupported media type")

    data = await request.body()
    np_image = np.load(io.BytesIO(data))

    try:
        annotation.write_data(np_image, axis=axis, slice_index=scan_nr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    
    db.add(annotation)
    db.commit()

    return Response(status_code=204)


@router.get("/segmentations/{segmentation_id}/data")
async def get_annotation_data_file(
    segmentation_id: int,
    axis: Optional[int] = None,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation = Annotation.by_id(db, segmentation_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    arr = annotation.read_data(axis=axis, slice_index=scan_nr)

    buf = io.BytesIO()
    np.save(buf, arr)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/octet-stream")
