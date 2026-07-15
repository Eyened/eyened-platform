"""Model input resolution and AttributesModel I/O registration.

Attribute value selection
-------------------------
Use :func:`select_attribute_value` whenever one stored row must be chosen from
several candidates (inference input resolution, ORM shorthand properties, API
payloads).

**Returned row:** among candidates matching all supplied filters, the row whose
producing model has the **highest version** (``version_sort_key``). Returns
``None`` when no row qualifies.

**Filters** (combined with AND; omit a filter to ignore it):

- ``attribute_name`` — ``AttributeDefinition.AttributeName``
- ``producing_model_name`` — ``AttributesModel.ModelName``
- ``producing_model_id`` — ``AttributesModel.ModelID``
- ``min_version`` — producing-model version must be >= this threshold

**Availability** (``require_available=True``, default): rows with all value
columns NULL (failed inference) are excluded. Set ``require_available=False``
only when inspecting failure state (e.g. ``ImageInstance.roi`` warnings).

**Version ordering** (``version_sort_key``): PEP 440 semver strings rank before
opaque artifact ids; within each kind, higher version wins.

Inference pipelines resolve inputs via :func:`resolve_input_attribute_value`,
which applies the :class:`ModelInputSpec` filters for that dependency. ORM
shorthand properties and :meth:`~eyened_orm.attribute_value_lookup_mixin.AttributeValueLookupMixin.find_attribute_value`
call the same selector on ``ImageInstance.AttributeValues``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

from eyened_orm import AttributeDataType
from eyened_orm.inference.attribute_value_outcome import is_available_input
from eyened_orm.inference.model_versions import version_at_least, version_sort_key

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from eyened_orm import AttributeDefinition, AttributeValue, AttributesModel


@dataclass(frozen=True)
class ModelInputSpec:
    """Declares one model input dependency for inference pipelines.

    :func:`resolve_input_attribute_value` selects the highest-version available
    ``AttributeValue`` for ``(attribute_name, model_name)`` with producing-model
    version >= ``min_version``.
    """

    attribute_name: str
    model_name: str
    min_version: str = "0.0.0"
    input_name: str | None = None
    attribute_data_type: AttributeDataType | None = None

    @property
    def resolved_input_name(self) -> str:
        return self.input_name or self.attribute_name


CFI_ROI_INPUT = ModelInputSpec(
    attribute_name="CFI_ROI",
    model_name="CFI_ROI",
    min_version="0.0.0",
    attribute_data_type=AttributeDataType.JSON,
)

CFI_KEYPOINTS_INPUT = ModelInputSpec(
    attribute_name="CFI_Keypoints",
    model_name="CFI_Keypoints",
    min_version="0.0.0",
    attribute_data_type=AttributeDataType.JSON,
)

CFI_ODFD_INPUT = ModelInputSpec(
    attribute_name="CFI_ODFD",
    model_name="CFI_ODFD",
    min_version="0.0.0",
    attribute_data_type=AttributeDataType.Float,
)

ETDRS_INPUTS: tuple[ModelInputSpec, ...] = (CFI_KEYPOINTS_INPUT, CFI_ODFD_INPUT)


def _eligible_attribute_values(
    candidates: Iterable[AttributeValue],
    *,
    attribute_name: str | None = None,
    producing_model_name: str | None = None,
    producing_model_id: int | None = None,
    min_version: str | None = None,
    require_available: bool = True,
) -> list[AttributeValue]:
    eligible: list[AttributeValue] = []
    for av in candidates:
        producing_model = av.ProducingModel

        if producing_model_id is not None:
            if producing_model is None or producing_model.ModelID != producing_model_id:
                continue

        if producing_model_name is not None:
            if (
                producing_model is None
                or producing_model.ModelName != producing_model_name
            ):
                continue

        if attribute_name is not None:
            if av.AttributeDefinition.AttributeName != attribute_name:
                continue

        if require_available and not is_available_input(av):
            continue

        if min_version is not None and producing_model is not None:
            if not version_at_least(producing_model.Version, min_version):
                continue

        eligible.append(av)

    return eligible


def select_attribute_value(
    candidates: Iterable[AttributeValue],
    *,
    attribute_name: str | None = None,
    producing_model_name: str | None = None,
    producing_model_id: int | None = None,
    min_version: str | None = None,
    require_available: bool = True,
) -> AttributeValue | None:
    """Select one AttributeValue row by filter match and version precedence.

    See module docstring for the full selection contract. At least one of
    ``attribute_name``, ``producing_model_name``, or ``producing_model_id`` must
    be provided.
    """
    if (
        attribute_name is None
        and producing_model_name is None
        and producing_model_id is None
    ):
        return None

    eligible = _eligible_attribute_values(
        candidates,
        attribute_name=attribute_name,
        producing_model_name=producing_model_name,
        producing_model_id=producing_model_id,
        min_version=min_version,
        require_available=require_available,
    )
    if not eligible:
        return None

    return max(
        eligible,
        key=lambda av: version_sort_key(av.ProducingModel.Version),
    )


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
    """Resolve one pipeline input for an image.

    Loads all ``AttributeValue`` rows for ``image_id`` where the attribute name
    is ``spec.attribute_name`` and the producing model name is ``spec.model_name``,
    then returns the highest-version available row with producing-model version
    >= ``spec.min_version``. Returns ``None`` when no row qualifies (missing,
    failed, or below ``min_version``).
    """
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
    return select_attribute_value(
        candidates,
        attribute_name=spec.attribute_name,
        producing_model_name=spec.model_name,
        min_version=spec.min_version,
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


def attribute_value_data(av: AttributeValue) -> Any:
    """Read the stored value from column fields (no lazy-loaded relationships)."""
    if av.ValueJSON is not None:
        return av.ValueJSON
    if av.ValueFloat is not None:
        return av.ValueFloat
    if av.ValueInt is not None:
        return av.ValueInt
    if av.ValueText is not None:
        return av.ValueText
    return None
