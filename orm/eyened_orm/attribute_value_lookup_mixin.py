from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class _HasAttributeValues(Protocol):
    AttributeValues: list[Any]


class AttributeValueLookupMixin:
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
        for av in self.AttributeValues:
            producing_model = av.ProducingModel

            if (
                producing_model_name is not None
                and producing_model is not None
                and producing_model.ModelName == producing_model_name
            ):
                return av.value

            if (
                producing_model_id is not None
                and producing_model is not None
                and producing_model.ModelID == producing_model_id
            ):
                return av.value

            if (
                attribute_name is not None
                and av.AttributeDefinition.AttributeName == attribute_name
            ):
                return av.value

        return None
