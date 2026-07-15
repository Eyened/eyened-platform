"""Model input resolution and AttributesModel I/O registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from eyened_orm import AttributeDataType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from eyened_orm import AttributeDefinition, AttributeValue, AttributesModel


# Known version order per producing model (opaque strings, highest last).
VERSION_ORDER: dict[str, tuple[str, ...]] = {
    "CFI_ROI": ("1.0",),
    "CFI_Keypoints": ("july24",),
    "CFI_ODFD": ("odfd_march25",),
    "CFI_Quality": ("1.0",),
}


@dataclass(frozen=True)
class ModelInputSpec:
    attribute_name: str
    model_name: str
    min_version: str = "1.0"
    input_name: str | None = None
    attribute_data_type: AttributeDataType | None = None

    @property
    def resolved_input_name(self) -> str:
        return self.input_name or self.attribute_name


def _version_rank(model_name: str, version: str) -> int:
    order = VERSION_ORDER.get(model_name)
    if order is None:
        return 0
    try:
        return order.index(version)
    except ValueError:
        return -1


def version_at_least(model_name: str, version: str, min_version: str) -> bool:
    return _version_rank(model_name, version) >= _version_rank(model_name, min_version)


def register_model_output(
    session: Session,
    model: AttributesModel,
    attribute_definition: AttributeDefinition,
) -> None:
    """Declare which attribute this model produces (AttributesModelOutput)."""
    if attribute_definition not in model.OutputAttributes:
        model.OutputAttributes.add(attribute_definition)
        session.flush()


def register_model_inputs(
    session: Session,
    model: AttributesModel,
    specs: tuple[ModelInputSpec, ...],
) -> None:
    """Declare model input dependencies (ModelInput rows)."""
    from eyened_orm import AttributeDefinition, ModelInput

    for spec in specs:
        input_attr = AttributeDefinition.by_column(
            session, AttributeName=spec.attribute_name
        )
        if input_attr is None:
            if spec.attribute_data_type is None:
                raise ValueError(
                    f"Input attribute {spec.attribute_name!r} is not defined; "
                    "run the producing model first or set attribute_data_type on the spec"
                )
            input_attr = AttributeDefinition.get_or_create(
                session,
                match_by={
                    "AttributeName": spec.attribute_name,
                    "AttributeDataType": spec.attribute_data_type,
                },
            )
        ModelInput.get_or_create(
            session,
            match_by={
                "ModelID": model.ModelID,
                "InputAttributeID": input_attr.AttributeID,
            },
            update_values={"InputName": spec.resolved_input_name},
        )


def resolve_input_attribute_value(
    session: Session,
    *,
    image_id: int,
    spec: ModelInputSpec,
) -> AttributeValue | None:
    """Pick the best matching input AttributeValue for one image."""
    from sqlalchemy import select

    from eyened_orm import AttributeDefinition, AttributesModel, AttributeValue

    stmt = (
        select(AttributeValue)
        .join(AttributeDefinition)
        .join(AttributesModel, AttributeValue.ModelID == AttributesModel.ModelID)
        .where(
            AttributeValue.ImageInstanceID == image_id,
            AttributeDefinition.AttributeName == spec.attribute_name,
            AttributesModel.ModelName == spec.model_name,
        )
    )
    candidates = list(session.scalars(stmt).all())
    eligible = [
        av
        for av in candidates
        if av.ProducingModel is not None
        and version_at_least(
            spec.model_name, av.ProducingModel.Version, spec.min_version
        )
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda av: _version_rank(spec.model_name, av.ProducingModel.Version),
    )


def resolve_inputs_for_images(
    session: Session,
    image_ids: Iterable[int],
    specs: tuple[ModelInputSpec, ...],
) -> dict[int, dict[str, AttributeValue]]:
    """Resolve all declared inputs per image. Keys are input names."""
    resolved: dict[int, dict[str, AttributeValue]] = {}
    for image_id in image_ids:
        inputs: dict[str, AttributeValue] = {}
        for spec in specs:
            av = resolve_input_attribute_value(session, image_id=image_id, spec=spec)
            if av is not None:
                inputs[spec.resolved_input_name] = av
        if inputs:
            resolved[image_id] = inputs
    return resolved


def roi_value_from_inputs(inputs: dict[str, AttributeValue] | None) -> dict | None:
    """Extract CFI_ROI JSON from resolved input values."""
    if not inputs:
        return None
    roi_av = inputs.get("CFI_ROI")
    if roi_av is None:
        return None
    value = roi_av.value
    return value if isinstance(value, dict) else None
