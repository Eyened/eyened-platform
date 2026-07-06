from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from eyened_orm import Feature
from eyened_orm.segmentation import FeatureFeatureLink, Segmentation
from ..db import get_db
from ..utils.db_logging import get_db_logger
from .auth import CurrentUser, get_current_user
from ..dtos.dtos_main import FeaturePUT, FeaturePATCH, FeatureGET
from ..dtos.dto_converter import DTOConverter

router = APIRouter()

def set_subfeatures(db: Session, parent_id: int, sub_ids: list[int] | None) -> None:
    db.execute(delete(FeatureFeatureLink).where(FeatureFeatureLink.ParentFeatureID == parent_id))
    for idx, child_id in enumerate(sub_ids or []):
        db.add(FeatureFeatureLink(ParentFeatureID=parent_id, ChildFeatureID=child_id, FeatureIndex=idx))

@router.get("/features", response_model=list[FeatureGET])
async def list_features(
    with_counts: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return all features."""
    rows = db.scalars(select(Feature).order_by(Feature.FeatureName.asc())).all()
    if not with_counts:
        return [DTOConverter.feature_to_get(f) for f in rows]

    # Compute counts per FeatureID in one query
    counts_rows = db.execute(
        select(Segmentation.FeatureID, func.count()).group_by(Segmentation.FeatureID)
    ).all()
    counts = {fid: cnt for (fid, cnt) in counts_rows}

    return [DTOConverter.feature_to_get(f, counts.get(f.FeatureID, 0)) for f in rows]

@router.post("/features", response_model=FeatureGET)
async def create_feature(dto: FeaturePUT, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    feature = Feature(FeatureName=dto.name)
    db.add(feature); db.flush()
    set_subfeatures(db, feature.FeatureID, dto.subfeature_ids)
    db.commit(); db.refresh(feature)
    
    # Log feature creation
    logger = get_db_logger()
    if logger:
        logger.log_insert(
            user=current_user.username,
            user_id=current_user.id,
            endpoint="POST /api/features",
            entity="Feature",
            entity_id=feature.FeatureID,
            fields={
                "name": feature.FeatureName,
                "subfeature_ids": dto.subfeature_ids or [],
            },
        )
    
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
    changes = {}
    if dto.name is not None:
        changes["name"] = f"{feature.FeatureName} -> {dto.name}"
        feature.FeatureName = dto.name
    if dto.subfeature_ids is not None:
        # Get current subfeatures for logging
        from sqlalchemy import select
        current_subfeatures = db.execute(
            select(FeatureFeatureLink.ChildFeatureID)
            .where(FeatureFeatureLink.ParentFeatureID == feature_id)
            .order_by(FeatureFeatureLink.FeatureIndex)
        ).scalars().all()
        changes["subfeature_ids"] = f"{list(current_subfeatures)} -> {dto.subfeature_ids}"
        set_subfeatures(db, feature_id, dto.subfeature_ids)
    db.commit(); db.refresh(feature)
    
    # Log feature update
    logger = get_db_logger()
    if logger:
        logger.log_update(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"PATCH /api/features/{feature_id}",
            entity="Feature",
            entity_id=feature_id,
            changes=changes if changes else None,
        )
    
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

    # Save feature data for logging before deletion
    deleted_data = {
        "name": feature.FeatureName,
    }
    
    # Safe to delete; ORM cascade removes parent->child links, children remain intact
    db.delete(feature)
    db.commit()
    
    # Log feature deletion
    logger = get_db_logger()
    if logger:
        logger.log_delete(
            user=current_user.username,
            user_id=current_user.id,
            endpoint=f"DELETE /api/features/{feature_id}",
            entity="Feature",
            entity_id=feature_id,
            deleted_data=deleted_data,
        )
    
    return Response(status_code=204)
