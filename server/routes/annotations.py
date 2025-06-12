import gzip
import os

from eyened_orm import Annotation, AnnotationPlane, AnnotationData
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


@router.get("/annotation-data/{data_id}/file")
async def get_annotation_data_file(
    data_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    annotation_data = AnnotationData.by_composite_id(db, data_id)
    if annotation_data is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    if annotation_data.DatasetIdentifier is None:
        raise HTTPException(status_code=404, detail="Annotation data file not found")

    filename = annotation_data.path
    if not filename.exists():
        raise HTTPException(status_code=404, detail="Annotation data file not found")

    headers = {}
    if filename.suffix == ".gz":
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Encoding": "gzip",
        }

    return FileResponse(str(filename), headers=headers)



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
    elif content_type == "application/octet-stream":
        ext = "npy.gz"
        should_compress = content_encoding != "gzip"
    else:
        raise HTTPException(status_code=400, detail="Unsupported media type")

    if annotation_data.DatasetIdentifier is None:
        annotation_data.DatasetIdentifier = annotation_data.get_default_path(ext)
        db.add(annotation_data)
        db.commit()
        db.refresh(annotation_data)
    else:
        if not str(annotation_data.path).endswith(ext):
            raise HTTPException(
                status_code=400,
                detail=f"Media type mismatch: expected file ending with {ext}",
            )

    filename = annotation_data.path
    os.makedirs(filename.parent, exist_ok=True)

    data = await request.body()

    if content_type == "image/png":
        with open(filename, "wb") as f:
            f.write(data)

    else:  # npy
        if should_compress:
            with gzip.open(filename, "wb") as f:
                f.write(data)
        else:
            # Already gzipped — store as-is
            with open(filename, "wb") as f:
                f.write(data)

    return Response(status_code=204)


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
