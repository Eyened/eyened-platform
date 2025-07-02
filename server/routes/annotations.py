import gzip
import os
import numpy as np
from PIL import Image
import io
import gzip
from fastapi import Response
from pathlib import Path

from eyened_orm import Annotation, AnnotationPlane, AnnotationData, AnnotationDataBase
from eyened_orm.base import create_patch_model
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()


class AnnotationDataCreate(BaseModel):
    AnnotationID: int
    ScanNr: int
    AnnotationPlane: str  # should map to enum
    ValueFloat: float | None = None
    ValueInt: int | None = None


@router.post("/annotation-data", response_model=AnnotationData)
async def create_annotation_data(
    data: AnnotationDataCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        annotation = db.get(Annotation, data.AnnotationID)
        if annotation is None:
            raise HTTPException(status_code=404, detail="Annotation not found")

        annotation_data = AnnotationData.create(
            annotation, data.ScanNr, data.AnnotationPlane
        )

        if data.ValueFloat is not None:
            annotation_data.ValueFloat = data.ValueFloat
        if data.ValueInt is not None:
            annotation_data.ValueInt = data.ValueInt

        db.add(annotation_data)
        db.commit()
        db.refresh(annotation_data)
        return annotation_data
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error creating annotation data: {e}"
        )


@router.get("/annotation-data/{data_id}", response_model=AnnotationData)
async def get_annotation_data(
    data_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.by_composite_id(db, data_id)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")
    return annotation_data


def get_path(annotation_data: AnnotationData):
    subfolder = f"{annotation_data.AnnotationID:04d}"[-4:]
    filename = f"{annotation_data.AnnotationID}_{annotation_data.ScanNr}.npy.gz"
    return annotation_data.config.annotations_path / "viewer" / subfolder / filename


def convert_png_to_npy(annotation_data: AnnotationData):
    array = np.array(Image.open(annotation_data.path))
    result = np.zeros(array.shape[:2], dtype=np.uint8)
    if annotation_data.Annotation.AnnotationTypeID in [2, 3, 5]:
        # 2D R/G mask
        r = array[:, :, 0]
        g = array[:, :, 1]
        result[r > 0] |= 1 << 0  # mask in first bit
        result[g > 0] |= 1 << 1  # questionable in second bit

    elif annotation_data.Annotation.AnnotationTypeID in [13, 17, 24]:
        # 2D binary mask
        if len(array.shape) == 3:
            result = array[:, :, 0]
        else:
            result = array
    elif annotation_data.Annotation.AnnotationTypeID in [14, 23, 25]:
        # 2D probability
        if len(array.shape) == 3:
            result = array[:, :, 0]
        else:
            result = array
    else:
        print(
            "warning: unsupported annotation type",
            annotation_data.Annotation.AnnotationTypeID,
        )
        raise HTTPException(status_code=400, detail="Unsupported annotation type")

    return result


@router.get("/annotation-data/{data_id}/file")
async def get_annotation_data_file(
    data_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.by_composite_id(db, data_id)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    path = get_path(annotation_data)
    print("path", path)
    if os.path.exists(path):
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Encoding": "gzip",
        }
        print("returning file")
        return FileResponse(str(path), headers=headers)

    # look for old file
    # TODO: convert file to new format

    if annotation_data.DatasetIdentifier is None:
        raise HTTPException(status_code=404, detail="Annotation data file not found")

    filename = annotation_data.path
    if not filename.exists():
        raise HTTPException(status_code=404, detail="Annotation data file not found")

    if filename.suffix == ".png":
        array = convert_png_to_npy(annotation_data)
        return send_npy_gzipped(array)

    headers = {}
    if filename.suffix == ".gz":
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Encoding": "gzip",
        }

    return FileResponse(str(filename), headers=headers)


def send_npy_gzipped(array: np.ndarray, filename="array.npy.gz"):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        np.save(gz, array)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Encoding": "gzip",
        },
    )


@router.put("/annotation-data/{data_id}/file", status_code=204)
async def update_annotation_data_file(
    data_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.by_composite_id(db, data_id)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    content_type = request.headers.get("Content-Type", "").lower()
    content_encoding = request.headers.get("Content-Encoding", "").lower()

    if content_type == "image/png":
        ext = "png"
        should_compress = False
        print("warning: png deprecated")
    elif content_type == "application/octet-stream":
        ext = "npy.gz"
        should_compress = content_encoding != "gzip"
    else:
        raise HTTPException(status_code=400, detail="Unsupported media type")

    # if annotation_data.DatasetIdentifier is None:
    #     annotation_data.DatasetIdentifier = annotation_data.get_default_path(ext)
    #     db.add(annotation_data)
    #     db.commit()
    #     db.refresh(annotation_data)
    # else:
    #     if not str(annotation_data.path).endswith(ext):
    #         raise HTTPException(
    #             status_code=400,
    #             detail=f"Media type mismatch: expected file ending with {ext}",
    #         )

    # old: filename = annotation_data.path
    filename = get_path(annotation_data)
    os.makedirs(filename.parent, exist_ok=True)

    data = await request.body()

    if content_type == "image/png":
        print("warning: png deprecated")
        with open(filename, "wb") as f:
            f.write(data)

    else:  # npy
        print("saving to", filename)
        if should_compress:
            with gzip.open(filename, "wb") as f:
                f.write(data)
        else:
            # Already gzipped — store as-is
            with open(filename, "wb") as f:
                f.write(data)

    return Response(status_code=204)


PatchModel = create_patch_model(f"AnnotationData_Patch", AnnotationDataBase)


@router.patch("/annotation-data/{data_id}")
async def update_annotation_data(
    data_id: str,
    params: PatchModel,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.by_composite_id(db, data_id)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")
    print("[params]", params.model_dump(exclude_unset=True))

    for key, value in params.model_dump(exclude_unset=True).items():
        print("patching item", key, value)
        setattr(annotation_data, key, value)

    db.commit()
    db.refresh(annotation_data)
    return annotation_data


@router.delete("/annotation-data/{data_id}", status_code=204)
async def delete_annotation_data(
    data_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.by_composite_id(db, data_id)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    db.delete(annotation_data)
    db.commit()
    return Response(status_code=204)
