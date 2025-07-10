import io
from typing import Optional

import numpy as np
from eyened_orm import Annotation, ImageInstance
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from PIL import Image
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()


# class AnnotationDataCreate(BaseModel):
#     AnnotationID: int
#     ScanNr: int
#     AnnotationPlane: str  # should map to enum
#     ValueFloat: float | None = None
#     ValueInt: int | None = None


# @router.post("/annotation-data", response_model=AnnotationData)
# async def create_annotation_data(
#     data: AnnotationDataCreate,
#     request: Request,
#     db: Session = Depends(get_db),
#     current_user: CurrentUser = Depends(get_current_user),
# ):
#     try:
#         annotation = db.get(Annotation, data.AnnotationID)
#         if annotation is None:
#             raise HTTPException(status_code=404, detail="Annotation not found")

#         annotation_data = AnnotationData.create(
#             annotation, data.ScanNr, data.AnnotationPlane
#         )

#         if data.ValueFloat is not None:
#             annotation_data.ValueFloat = data.ValueFloat
#         if data.ValueInt is not None:
#             annotation_data.ValueInt = data.ValueInt

#         db.add(annotation_data)
#         db.commit()
#         db.refresh(annotation_data)
#         return annotation_data
#     except Exception as e:
#         raise HTTPException(
#             status_code=400, detail=f"Error creating annotation data: {e}"
#         )


# @router.get("/annotation-data/{data_id}", response_model=AnnotationData)
# async def get_annotation_data(
#     data_id: str,
#     db: Session = Depends(get_db),
#     current_user: CurrentUser = Depends(get_current_user),
# ):
#     annotation_data = AnnotationData.by_composite_id(db, data_id)
#     if annotation_data is None:
#         raise HTTPException(status_code=404, detail="Annotation data not found")
#     return annotation_data

# PatchModel = create_patch_model("AnnotationData_Patch", AnnotationDataBase)
# @router.patch("/annotation-data/{data_id}")
# async def update_annotation_data(
#     data_id: str,
#     params: PatchModel,
#     db: Session = Depends(get_db),
#     current_user: CurrentUser = Depends(get_current_user),
# ):
#     annotation_data = AnnotationData.by_composite_id(db, data_id)
#     if annotation_data is None:
#         raise HTTPException(status_code=404, detail="Annotation data not found")
#     print("[params]", params.model_dump(exclude_unset=True))

#     for key, value in params.model_dump(exclude_unset=True).items():
#         print("patching item", key, value)
#         setattr(annotation_data, key, value)

#     db.commit()
#     db.refresh(annotation_data)
#     return annotation_data


# @router.delete("/annotation-data/{data_id}", status_code=204)
# async def delete_annotation_data(
#     data_id: str,
#     db: Session = Depends(get_db),
#     current_user: CurrentUser = Depends(get_current_user),
# ):
#     annotation_data = AnnotationData.by_composite_id(db, data_id)
#     if annotation_data is None:
#         raise HTTPException(status_code=404, detail="Annotation data not found")

#     db.delete(annotation_data)
#     db.commit()
#     return Response(status_code=204)


@router.post("/annotations")
async def create_annotation(
    annotation: dict,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    if "PatientID" not in annotation:
        annotation["PatientID"] = ImageInstance.by_id(
            db, annotation["ImageInstanceID"]
        ).Series.Study.PatientID
    annotation["CreatorID"] = current_user.id
    # annotation['DateInserted'] = datetime.now()
    db_item = Annotation(**annotation)
    db.add(db_item)
    db.commit()
    return db_item


@router.get("/annotations/{annot_id}/data")
async def get_annotation_data_file(
    annot_id: int,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    # current_user: CurrentUser = Depends(get_current_user),
):
    annotation = Annotation.by_id(db, annot_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    arr = annotation.numpy

    if scan_nr is not None:
        arr = arr[:, :, scan_nr, ...]

    buf = io.BytesIO()
    np.save(buf, arr)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/octet-stream")


# @router.get("/annotation-data/{data_id}/file")
# async def get_annotation_data_file(
#     data_id: str,
#     db: Session = Depends(get_db),
#     current_user: CurrentUser = Depends(get_current_user),
# ):
#     annotation_data = AnnotationData.by_composite_id(db, data_id)
#     if annotation_data is None:
#         raise HTTPException(status_code=404, detail="Annotation data not found")

#     if annotation_data.DatasetIdentifier is None:
#         raise HTTPException(status_code=404, detail="Annotation data file not found")

#     filename = annotation_data.path
#     if not filename.exists():
#         raise HTTPException(status_code=404, detail="Annotation data file not found")

#     headers = {}
#     if filename.suffix == ".gz":
#         headers = {
#             "Content-Type": "application/octet-stream",
#             "Content-Encoding": "gzip",
#         }

#     return FileResponse(str(filename), headers=headers)


@router.put("/annotations/{annot_id}/data", status_code=204)
async def update_annotation_data_file(
    annot_id: int,
    request: Request,
    scan_nr: Optional[int] = None,
    db: Session = Depends(get_db),
    # current_user: CurrentUser = Depends(get_current_user),
):
    annotation = Annotation.by_id(annot_id)
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation data not found")

    content_type = request.headers.get("Content-Type", "").lower()

    if content_type not in ["image/png", "application/octet-stream"]:
        raise HTTPException(status_code=400, detail="Unsupported media type")

    data = await request.body()
    if content_type == "image/png":
        image = Image.open(io.BytesIO(data))
        np_image = np.array(image)

    else:  # npy
        np_image = np.load(io.BytesIO(data))
        # TODO: make it work with compressed data

    annotation.write_data(np_image)
    return Response(status_code=204)


# @router.put("/annotation-data/{data_id}/file", status_code=204)
# async def update_annotation_data_file(
#     data_id: str,
#     request: Request,
#     db: Session = Depends(get_db),
#     current_user: CurrentUser = Depends(get_current_user),
# ):
#     annotation_data = AnnotationData.by_composite_id(db, data_id)
#     if annotation_data is None:
#         raise HTTPException(status_code=404, detail="Annotation data not found")

#     content_type = request.headers.get("Content-Type", "").lower()
#     content_encoding = request.headers.get("Content-Encoding", "").lower()

#     if content_type == "image/png":
#         ext = "png"
#         should_compress = False
#     elif content_type == "application/octet-stream":
#         ext = "npy.gz"
#         should_compress = content_encoding != "gzip"
#     else:
#         raise HTTPException(status_code=400, detail="Unsupported media type")

#     if annotation_data.DatasetIdentifier is None:
#         annotation_data.DatasetIdentifier = annotation_data.get_default_path(ext)
#         db.add(annotation_data)
#         db.commit()
#         db.refresh(annotation_data)
#     else:
#         if not str(annotation_data.path).endswith(ext):
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Media type mismatch: expected file ending with {ext}",
#             )

#     filename = annotation_data.path
#     os.makedirs(filename.parent, exist_ok=True)

#     data = await request.body()

#     if content_type == "image/png":
#         with open(filename, "wb") as f:
#             f.write(data)

#     else:  # npy
#         if should_compress:
#             with gzip.open(filename, "wb") as f:
#                 f.write(data)
#         else:
#             # Already gzipped — store as-is
#             with open(filename, "wb") as f:
#                 f.write(data)

#     return Response(status_code=204)
