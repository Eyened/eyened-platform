from typing import Dict

from eyened_orm import Feature
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()


class FeatureCreate(BaseModel):
    FeatureName: str


@router.post("/features/new", response_model=Dict)
async def create_feature(
    params: FeatureCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    new_feature = Feature()
    new_feature.FeatureName = params.FeatureName
    db.add(new_feature)
    db.commit()
    return new_feature.to_dict()


@router.delete("/features/{feature_id}")
async def delete_feature(
    feature_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    feature = db.query(Feature).filter(Feature.FeatureID == feature_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    db.delete(feature)
    db.commit()
    return Response(status_code=204)


@router.get("/features")
async def get_features(
    current_user: CurrentUser = Depends(get_current_user)
):
    pass
