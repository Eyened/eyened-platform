from typing import Dict, List

from eyened_orm import Feature
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from .auth import CurrentUser, get_current_user

router = APIRouter()


class FeatureResponse(BaseModel):
    FeatureID: int
    FeatureName: str


class FeatureCreate(BaseModel):
    FeatureName: str


@router.post("/features", response_model=FeatureResponse)
async def create_feature(
    params: FeatureCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    new_feature = Feature()
    new_feature.FeatureName = params.FeatureName
    db.add(new_feature)
    db.commit()
    return new_feature


@router.get("/features", response_model=List[FeatureResponse])
async def get_features(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return db.scalars(select(Feature)).all()


@router.get("/features/{feature_id}", response_model=FeatureResponse)
async def get_feature(
    feature_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.delete("/features/{feature_id}")
async def delete_feature(
    feature_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    feature = db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    db.delete(feature)
    db.commit()
    return Response(status_code=204)
