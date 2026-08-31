from fastapi import APIRouter, Depends, Response

from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_main import FeatureGET, FeaturePATCH, FeaturePUT
from ..services.feature_service import FeatureService, get_feature_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.get("/features", response_model=list[FeatureGET])
def list_features(
    with_counts: bool = False,
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return all features (optionally with a per-feature segmentation count)."""
    features, counts = service.list_features(with_counts)
    if not with_counts:
        return [DTOConverter.feature_to_get(f) for f in features]
    return [DTOConverter.feature_to_get(f, counts.get(f.FeatureID, 0)) for f in features]


@router.post("/features", response_model=FeatureGET)
def create_feature(
    dto: FeaturePUT,
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a feature and set its subfeature links."""
    feature = service.create_feature(
        dto.name,
        dto.subfeature_ids,
    )
    return DTOConverter.feature_to_get(feature)


@router.get("/features/{feature_id}", response_model=FeatureGET)
def get_feature(
    feature_id: int,
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return a single feature by id."""
    return DTOConverter.feature_to_get(service.get_feature(feature_id))


@router.patch("/features/{feature_id}", response_model=FeatureGET)
def patch_feature(
    feature_id: int,
    dto: FeaturePATCH,
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a feature's name and/or subfeature links."""
    feature = service.update_feature(
        feature_id,
        dto.name,
        dto.subfeature_ids,
    )
    return DTOConverter.feature_to_get(feature)


@router.delete("/features/{feature_id}", status_code=204)
def delete_feature(
    feature_id: int,
    service: FeatureService = Depends(get_feature_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a feature (409 if it has segmentations or is a child of another)."""
    service.delete_feature(
        feature_id,
    )
    return Response(status_code=204)
