import pytest

from eyened_orm import ImageInstance, Patient, Project, Study
from eyened_orm.repositories.search import (
    AttributeConditionSpec,
    ResolvedCondition,
    SearchRepository,
)
from eyened_orm.utils.factories import seed_search_dataset


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


@pytest.fixture()
def repo():
    return SearchRepository()


def _ids(rows):
    return [r.PublicID for r in rows]


def _instances(repo, session, conditions=(), attr_conditions=(), limit=100, offset=0):
    return repo.search_instances(
        session,
        conditions=list(conditions),
        attr_conditions=list(attr_conditions),
        order_by=ImageInstance.DateInserted,
        order="ASC",
        limit=limit,
        offset=offset,
    )


def test_search_instances_excludes_inactive(repo, session, data):
    """The base instance select filters out inactive instances."""
    assert _ids(_instances(repo, session)) == ["img-a1", "img-a2", "img-b1"]


def test_count_instances_matches_the_search(repo, session, data):
    """count_instances counts the same predicate the search applies."""
    assert repo.count_instances(session, conditions=[], attr_conditions=[]) == 3


def test_search_instances_applies_a_base_condition(repo, session, data):
    """A condition on a base entity lands in the WHERE clause."""
    cond = ResolvedCondition(variable=Project.ProjectName, operator="==", value="Alpha")

    assert _ids(_instances(repo, session, [cond])) == ["img-a1", "img-a2"]


def test_search_instances_paginates(repo, session, data):
    """limit/offset window the ordered result."""
    assert _ids(_instances(repo, session, limit=2, offset=0)) == ["img-a1", "img-a2"]
    assert _ids(_instances(repo, session, limit=2, offset=2)) == ["img-b1"]


@pytest.mark.parametrize(
    "attr_name,value,expected",
    [("FeatureName", "feat-x", ["img-a1"]), ("FeatureName", "nope", [])],
)
def test_segmentation_exists_branch_positive_and_empty(
    repo, session, data, attr_name, value, expected
):
    """The segmentation EXISTS semijoin matches only annotated instances."""
    from eyened_orm import Feature

    cond = ResolvedCondition(
        variable=getattr(Feature, attr_name), operator="==", value=value
    )

    assert _ids(_instances(repo, session, [cond])) == expected


@pytest.mark.parametrize("value,expected", [("schema-x", ["img-a1"]), ("nope", [])])
def test_forms_exists_branch_positive_and_empty(repo, session, data, value, expected):
    """The forms EXISTS semijoin correlates image-level form annotations."""
    from eyened_orm import FormSchema

    cond = ResolvedCondition(variable=FormSchema.SchemaName, operator="==", value=value)

    assert _ids(_instances(repo, session, [cond])) == expected


@pytest.mark.parametrize("value,expected", [("img-tag", ["img-a1"]), ("nope", [])])
def test_image_tag_exists_branch_positive_and_empty(repo, session, data, value, expected):
    """The image-tag EXISTS semijoin matches only tagged instances."""
    from eyened_orm.repositories.search import InstTag

    cond = ResolvedCondition(variable=InstTag.TagName, operator="==", value=value)

    assert _ids(_instances(repo, session, [cond])) == expected


@pytest.mark.parametrize("value,expected", [(5, ["img-a1"]), (99, [])])
def test_attribute_exists_branch_positive_and_empty(repo, session, data, value, expected):
    """The attribute EXISTS resolves the definition and filters the typed value column."""
    spec = AttributeConditionSpec(attribute="Quality", operator="==", value=value, model="M1")

    assert _ids(_instances(repo, session, attr_conditions=[spec])) == expected


def test_unresolvable_attribute_is_skipped(repo, session, data):
    """The repository still drops an unresolved definition; the *service* rejects it
    with a 400 before the repository is ever asked (see SearchService.search_instances)."""
    spec = AttributeConditionSpec(attribute="NoSuchAttr", operator="==", value=1)

    assert _ids(_instances(repo, session, attr_conditions=[spec])) == [
        "img-a1",
        "img-a2",
        "img-b1",
    ]


def test_search_studies_and_count(repo, session, data):
    """Study search returns ordered studies and counts the same predicate."""
    rows = repo.search_studies(
        session, conditions=[], order_by=Study.StudyDate, order="ASC", limit=100, offset=0
    )

    assert [s.StudyID for s in rows] == [data.studies["a"].StudyID, data.studies["b"].StudyID]
    assert repo.count_studies(session, conditions=[]) == 2


def test_search_studies_applies_a_base_condition(repo, session, data):
    """A study condition on a joined base entity lands in the WHERE clause."""
    cond = ResolvedCondition(variable=Patient.PatientIdentifier, operator="==", value="PAT-B")
    rows = repo.search_studies(
        session, conditions=[cond], order_by=Study.StudyDate, order="ASC", limit=100, offset=0
    )

    assert [s.StudyID for s in rows] == [data.studies["b"].StudyID]


def test_instances_for_studies_returns_active_instances(repo, session, data):
    """instances_for_studies returns the studies' active instances."""
    rows = repo.instances_for_studies(session, [data.studies["a"].StudyID])

    assert sorted(_ids(rows)) == ["img-a1", "img-a2"]


def test_instances_for_studies_with_no_ids_returns_empty(repo, session, data):
    """An empty study-id list returns no rows rather than every instance."""
    assert repo.instances_for_studies(session, []) == []


def test_attribute_resolves_when_a_model_name_has_several_versions(repo, session, data):
    """Model allows (ModelName, Version) duplicates, so the def join fans out; resolution must not blow up."""
    from eyened_orm.attributes import AttributeDefinition
    from eyened_orm.repositories.search import AttributeConditionSpec
    from eyened_orm.utils.factories import make_attribute_value, make_attributes_model
    from sqlalchemy import select

    quality = session.scalar(
        select(AttributeDefinition).where(AttributeDefinition.AttributeName == "Quality")
    )
    m1_v2 = make_attributes_model(session, "M1", outputs=[quality], version="2")
    make_attribute_value(session, quality, image=data.images["a2"], model=m1_v2, value=5)
    session.flush()

    spec = AttributeConditionSpec(attribute="Quality", operator="==", value=5, model="M1")
    resolved = repo.resolve_attribute_definitions(session, [spec])

    assert resolved[("M1", "Quality", None)].AttributeName == "Quality"
