from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from eyened_orm import Feature
from eyened_orm.Segmentation import FeatureFeatureLink, Segmentation
from ..db import get_db
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_main import FeaturePUT, FeaturePATCH, FeatureGET
from ..dtos.dto_converter import DTOConverter

router = APIRouter()

def set_subfeatures(db: Session, parent_id: int, sub_ids: list[int] | None) -> None:
    db.execute(delete(FeatureFeatureLink).where(FeatureFeatureLink.ParentFeatureID == parent_id))
    for idx, child_id in enumerate(sub_ids or []):
        db.add(FeatureFeatureLink(ParentFeatureID=parent_id, ChildFeatureID=child_id, FeatureIndex=idx))

@router.post("/features", response_model=FeatureGET)
async def create_feature(dto: FeaturePUT, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    feature = Feature(FeatureName=dto.name)
    db.add(feature); db.flush()
    set_subfeatures(db, feature.FeatureID, dto.subfeature_ids)
    db.commit(); db.refresh(feature)
    return DTOConverter.feature_to_get(feature)

@router.get("/features/{feature_id}", response_model=FeatureGET)
async def get_feature(feature_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    feature = db.get(Feature, feature_id)
    if not feature:
        raise HTTPException(404, "Feature not found")
    return DTOConverter.feature_to_get(feature)

@router.patch("/features/{feature_id}", response_model=FeatureGET)
async def patch_feature(feature_id: int, dto: FeaturePATCH, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    feature = db.get(Feature, feature_id)
    if not feature:
        raise HTTPException(404, "Feature not found")
    if dto.name is not None:
        feature.FeatureName = dto.name
    if dto.subfeature_ids is not None:
        set_subfeatures(db, feature_id, dto.subfeature_ids)
    db.commit(); db.refresh(feature)
    return DTOConverter.feature_to_get(feature)

@router.delete("/features/{feature_id}", status_code=204)
async def delete_feature(feature_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    feature = db.get(Feature, feature_id)
    if not feature:
        raise HTTPException(404, "Feature not found")

    # Block if any segmentations reference this feature
    seg_count = db.execute(
        select(func.count()).select_from(Segmentation).where(Segmentation.FeatureID == feature_id)
    ).scalar_one()
    if seg_count > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "FEATURE_HAS_SEGMENTATIONS",
                "message": f"Cannot delete feature '{feature.FeatureName}' because it has {seg_count} linked segmentation(s).",
                "segmentation_count": seg_count,
            },
        )

    # Block if this feature is a child in any composite link
    parent_rows = db.execute(
        select(Feature.FeatureName)
        .join(FeatureFeatureLink, Feature.FeatureID == FeatureFeatureLink.ParentFeatureID)
        .where(FeatureFeatureLink.ChildFeatureID == feature_id)
    ).scalars().all()
    if parent_rows:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "FEATURE_IS_CHILD",
                "message": f"Cannot delete feature '{feature.FeatureName}' because it is a child of {len(parent_rows)} feature(s). Remove those links first.",
                "parents": parent_rows,
            },
        )

    # Safe to delete; ORM cascade removes parent->child links, children remain intact
    db.delete(feature)
    db.commit()
    return Response(status_code=204)
