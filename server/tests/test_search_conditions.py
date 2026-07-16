import pytest

from eyened_orm import Project
from eyened_orm.repositories.search import (
    AttributeConditionSpec,
    ResolvedCondition,
)
from server.services.search.conditions import (
    UnknownFieldError,
    translate_instance_conditions,
    translate_study_conditions,
)


def test_translate_resolves_a_static_label_to_its_orm_attribute():
    """A default condition's UI label becomes the mapped ORM attribute."""
    static, attrs = translate_instance_conditions(
        [{"type": "default", "variable": "Project Name", "operator": "==", "value": "Alpha"}]
    )

    assert static == [ResolvedCondition(Project.ProjectName, "==", "Alpha")]
    assert attrs == []


def test_translate_partitions_attribute_conditions():
    """Attribute conditions are split out and keep their model/feature addressing."""
    static, attrs = translate_instance_conditions(
        [
            {
                "type": "attribute",
                "model": "M1",
                "variable": "Quality",
                "operator": "==",
                "value": 5,
                "feature": None,
            }
        ]
    )

    assert static == []
    assert attrs == [
        AttributeConditionSpec(attribute="Quality", operator="==", value=5, model="M1", feature=None)
    ]


def test_translate_does_not_mutate_its_input():
    """Translation copies; the caller's condition dicts are left untouched."""
    raw = [{"type": "default", "variable": "Project Name", "operator": "==", "value": "Alpha"}]

    translate_instance_conditions(raw)

    assert raw[0]["variable"] == "Project Name"


def test_translate_study_conditions_resolves_labels():
    """Study conditions carry no discriminator and resolve against the study map."""
    assert translate_study_conditions(
        [{"variable": "Project Name", "operator": "==", "value": "Beta"}]
    ) == [ResolvedCondition(Project.ProjectName, "==", "Beta")]


def test_unknown_static_label_raises():
    """An unknown static label raises rather than silently dropping the filter."""
    with pytest.raises(UnknownFieldError):
        translate_instance_conditions(
            [{"type": "default", "variable": "Nope", "operator": "==", "value": 1}]
        )
