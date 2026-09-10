from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class _HasAttributeValues(Protocol):
    AttributeValues: list[Any]


class AttributeValueLookupMixin:
    """Version-aware attribute lookup shared by ORM objects and the API layer."""

    def find_attribute_value(
        self: _HasAttributeValues,
        *,
        producing_model_name: str | None = None,
        producing_model_id: int | None = None,
        attribute_name: str | None = None,
        min_version: str | None = None,
    ) -> Any | None:
        """Return the selected ``AttributeValue`` row for this object.

        Delegates to :func:`~eyened_orm.inference.model_inputs.select_attribute_value`
        on ``self.AttributeValues``.

        ``min_version``, when set, must equal an ``AttributesModel.Version`` value
        exactly (same string as stored in the database). Selection uses ``ModelID``
        ordering, not string comparison on ``Version``. Failed rows (null value
        columns) are excluded.
        """
        from eyened_orm.inference.model_inputs import select_attribute_value

        return select_attribute_value(
            self.AttributeValues,
            attribute_name=attribute_name,
            producing_model_name=producing_model_name,
            producing_model_id=producing_model_id,
            min_version=min_version,
        )

    def get_attribute_value(
        self: _HasAttributeValues,
        *,
        producing_model_name: str | None = None,
        producing_model_id: int | None = None,
        attribute_name: str | None = None,
        min_version: str | None = None,
    ) -> Optional[Any]:
        """Return the stored value from the selected ``AttributeValue`` row."""
        av = self.find_attribute_value(
            producing_model_name=producing_model_name,
            producing_model_id=producing_model_id,
            attribute_name=attribute_name,
            min_version=min_version,
        )
        if av is None:
            return None
        return av.value
