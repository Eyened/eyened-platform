from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class _HasAttributeValues(Protocol):
    AttributeValues: list[Any]


class AttributeValueLookupMixin:
    def find_attribute_value(
        self: _HasAttributeValues,
        *,
        producing_model_name: str | None = None,
        producing_model_id: int | None = None,
        attribute_name: str | None = None,
    ) -> Any | None:
        """
        Get the first matching AttributeValue row (not just its stored value).

        Matching uses OR semantics across the provided filters.
        """
        for av in self.AttributeValues:
            producing_model = av.ProducingModel

            if (
                producing_model_name is not None
                and producing_model is not None
                and producing_model.ModelName == producing_model_name
            ):
                return av

            if (
                producing_model_id is not None
                and producing_model is not None
                and producing_model.ModelID == producing_model_id
            ):
                return av

            if (
                attribute_name is not None
                and av.AttributeDefinition.AttributeName == attribute_name
            ):
                return av

        return None

    def get_attribute_value(
        self: _HasAttributeValues,
        *,
        producing_model_name: str | None = None,
        producing_model_id: int | None = None,
        attribute_name: str | None = None,
    ) -> Optional[Any]:
        """
        Get the first matching attribute value.

        Matching uses OR semantics across the provided filters
        """
        av = self.find_attribute_value(
            producing_model_name=producing_model_name,
            producing_model_id=producing_model_id,
            attribute_name=attribute_name,
        )
        if av is None:
            return None
        return av.value
