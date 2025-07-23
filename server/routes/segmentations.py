import gzip
import io
import json
from typing import Optional

import numpy as np
from eyened_orm import (
    Segmentation,
    ImageInstance,
    Segmentation,
    Datatype,
    DataRepresentation,
)
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
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()

dtypes = {
    Datatype.R8: np.uint8,
    Datatype.R8UI: np.uint8,
    Datatype.R16UI: np.uint16,
    Datatype.R32UI: np.uint32,
    Datatype.R32F: np.float32,
}



def load_params(metadata: str):
    required_params = ["ImageInstanceID", "FeatureID", "CreatorID", "DataType", "DataRepresentation"]

    params = json.loads(metadata)
    for param in required_params:
        if param not in params:
            raise HTTPException(status_code=400, detail=f"{param} is required")
    # replace string with enum
    params["DataType"] = Datatype[params["DataType"]]
    params["DataRepresentation"] = DataRepresentation[params["DataRepresentation"]]
    # remove ZarrArrayIndex from params (a new index needs to be assigned)
    if "ZarrArrayIndex" in params:
        del params["ZarrArrayIndex"]
    print("params", params)
    return params


async def load_array(np_array: Optional[UploadFile]) -> Optional[np.ndarray]:
    # Read and load numpy array
    if np_array is not None:
        data_content = await np_array.read()
        if np_array.filename.endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(data_content)) as f:
                data_content = f.read()
                print("uncompressed data_content", len(data_content))

        data_buffer = io.BytesIO(data_content)
        array = np.load(data_buffer)
        # check that the data is 3D
        if len(array.shape) != 3:
            raise HTTPException(
                status_code=400,
                detail=f"Segmentation is not 3D, got shape {array.shape}",
            )
        return array


def create_empty_array(segmentation: Segmentation, image: ImageInstance) -> np.ndarray:
    s_d, s_h, s_w = segmentation.shape
    im_d, im_h, im_w = image.shape
    shape = (s_d or im_d, s_h or im_h, s_w or im_w)
    segmentation.Depth, segmentation.Height, segmentation.Width = shape
    return np.zeros(shape, dtype=dtypes[segmentation.DataType])


#### CONSISTENCY CHECKS ####
"""
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
"""


# this endpoint uses multipart/form-data
# to create an annotation and upload its data at the same time
# it was implemented this way to ensure that the annotation data and metadata are consistent
# if the annotation data (np_array) is not provided, an empty (zeros) annotation is created
# once the annotation is created, its data can be updated using the PUT endpoint
# but only by data with the same shape as the original annotation
@router.post("/segmentations")
async def create_segmentation(
    np_array: UploadFile = File(default=None),
    metadata: str = Form(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    # create a new segmentation
    segmentation = Segmentation(**load_params(metadata))

    # creator can be different from the current_user and is passed in the params
    # segmentation.CreatorID = current_user.id

    image = ImageInstance.by_id(db, segmentation.ImageInstanceID)
    if image is None:
        raise HTTPException(
            status_code=400, detail="Segmentation has no associated image"
        )

    array = await load_array(np_array)
    if array is None:
        data = create_empty_array(segmentation, image)
    else:
        if segmentation.ScanIndices is None:
            # full volume
            data = array
            if segmentation.shape != array.shape:
                raise HTTPException(
                    status_code=400,
                    detail=f"Segmentation shape {segmentation.shape} does not match array shape {array.shape}",
                )
        else:
            # sparse volume
            if segmentation.SparseAxis is None:
                raise HTTPException(
                    status_code=400, detail=f"SparseAxis is not set for sparse volume"
                )

            if len(segmentation.ScanIndices) != array.shape[segmentation.SparseAxis]:
                raise HTTPException(
                    status_code=400,
                    detail=f"ScanIndices length {len(segmentation.ScanIndices)} does not match array sparse axis length {array.shape[segmentation.SparseAxis]}",
                )

            data = np.zeros(segmentation.shape, dtype=dtypes[segmentation.DataType])
            for i, scan_index in enumerate(segmentation.ScanIndices):
                data[scan_index] = array[i]

    for dim, attr in zip(data.shape, ["Depth", "Height", "Width"]):
        val = getattr(segmentation, attr)
        if val is None:
            # if the dimension is not set on the segmentation, set it to the array dimension
            setattr(segmentation, attr, dim)
        elif val != dim:
            # if the dimension is set on the segmentation, it must match the array dimension
            raise HTTPException(
                status_code=400,
                detail=f"Segmentation {attr} ({val}) does not match array {attr} ({dim})",
            )

    db.add(segmentation)
    db.flush()

    try:
        segmentation.write_data(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    db.commit()
    db.refresh(segmentation)
    return segmentation


@router.get("/segmentations/{segmentation_id}")
async def get_segmentation(
    segmentation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    item = Segmentation.by_id(db, segmentation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Segmentation not found")
    return item


@router.delete("/segmentations/{segmentation_id}", status_code=204)
async def delete_segmentation(
    segmentation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    segmentation = Segmentation.by_id(db, segmentation_id)
    if segmentation is None:
        raise HTTPException(status_code=404, detail="Segmentation not found")

    # db.delete(segmentation)
    segmentation.Inactive = True
    db.commit()
    return Response(status_code=204)


@router.put("/segmentations/{segmentation_id}/data")
async def update_segmentation_data(
    segmentation_id: int,
    request: Request,
    axis: Optional[int] = None,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    segmentation = Segmentation.by_id(db, segmentation_id)
    if segmentation is None:
        raise HTTPException(status_code=404, detail="Segmentation data not found")

    content_type = request.headers.get("Content-Type", "").lower()
    if content_type != "application/octet-stream":
        raise HTTPException(
            status_code=400, detail=f"Unsupported media type: {content_type}"
        )

    data = await request.body()
    np_image = np.load(io.BytesIO(data))

    try:
        segmentation.write_data(np_image, axis=axis, slice_index=scan_nr)
    except IndexError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    db.add(segmentation)
    db.commit()

    # return Response(status_code=204)

    # return the updated segmentation
    db.refresh(segmentation)
    return segmentation


@router.get("/segmentations/{segmentation_id}/data")
async def get_segmentation_data(
    segmentation_id: int,
    axis: Optional[int] = None,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    segmentation = Segmentation.by_id(db, segmentation_id)
    if segmentation is None:
        raise HTTPException(status_code=404, detail="Segmentation data not found")

    try:
        arr = segmentation.read_data(axis=axis, slice_index=scan_nr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    buf = io.BytesIO()
    np.save(buf, arr)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/octet-stream")
