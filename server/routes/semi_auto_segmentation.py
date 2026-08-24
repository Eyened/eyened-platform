from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import CurrentUser, get_current_user
from ..utils.semi_auto_medsam import JOB_REGISTRY


router = APIRouter()


class ClickPoint(BaseModel):
    x: float
    y: float


class SemiAutoSegmentationRequest(BaseModel):
    image_id: str = Field(..., description="Public image ID (or numeric ID)")
    feature_id: int = Field(..., description="Feature ID for the generated segmentation")
    mode: Literal["area", "layer"] = Field(
        default="area",
        description="Segmentation mode: area uses sparse prompts, layer traces a full layer",
    )
    slice_index: int | None = Field(
        default=None,
        ge=0,
        description="Optional depth index for 3D OCT volumes",
    )
    positive_points: list[ClickPoint] = Field(
        ..., min_length=1, description="Foreground clicks in image pixel coordinates"
    )
    negative_points: list[ClickPoint] = Field(
        default_factory=list, description="Background clicks in image pixel coordinates"
    )

    # Post-processing settings
    smoothing_strength: Literal["light", "medium", "strong"] = "medium"
    negative_guard_radius: int = Field(default=6, ge=1, le=64)
    positive_boost_strength: Literal["light", "medium", "strong"] = "strong"
    positive_anchor_radius: int = Field(default=4, ge=1, le=64)
    subtask_id: int | None = None


class SemiAutoSegmentationStartResponse(BaseModel):
    job_id: str
    status: str
    message: str


class SemiAutoSegmentationStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    result: dict | None = None
    error: str | None = None
    created_at: str
    updated_at: str


@router.post(
    "/segmentations/semi-auto",
    response_model=SemiAutoSegmentationStartResponse,
)
async def start_semi_auto_segmentation(
    body: SemiAutoSegmentationRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    payload = body.model_dump()
    payload["creator_id"] = int(current_user.id)

    job_id = JOB_REGISTRY.create(payload)
    JOB_REGISTRY.start(job_id)

    return SemiAutoSegmentationStartResponse(
        job_id=job_id,
        status="queued",
        message="Semi-auto segmentation job queued",
    )


@router.get(
    "/segmentations/semi-auto/status/{job_id}",
    response_model=SemiAutoSegmentationStatusResponse,
)
async def get_semi_auto_segmentation_status(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    status = JOB_REGISTRY.get(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return SemiAutoSegmentationStatusResponse(**status)
