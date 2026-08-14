import pytest

from eyened_orm import ImageInstance, Patient, Project, Study
from eyened_orm.repositories.search import (
    AttributeConditionSpec,
    ResolvedCondition,
    SearchRepository,
)
from eyened_orm.utils.factories import (
    admin_scope,
    seed_search_dataset,
)


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


@pytest.fixture()
def repo(session):
    return SearchRepository(session, scope=admin_scope())


def _ids(rows):
    return [r.PublicID for r in rows]


def _instances(repo, conditions=(), attr_conditions=(), limit=100, offset=0):
    specs = list(attr_conditions)
    attr_defs = repo.resolve_attribute_definitions(specs) if specs else {}
    return repo.search_instances(
        conditions=list(conditions),
        attr_conditions=specs,
        attr_defs=attr_defs,
        order_by=ImageInstance.DateInserted,
        order="ASC",
        limit=limit,
        offset=offset,
    )


def test_search_instances_excludes_inactive(repo, session, data):
    """The base instance select filters out inactive instances."""
    assert _ids(_instances(repo)) == ["img-a1", "img-a2", "img-b1"]


def test_count_instances_matches_the_search(repo, session, data):
    """count_instances counts the same predicate the search applies."""
    assert repo.count_instances(conditions=[], attr_conditions=[], attr_defs={}) == 3


def test_search_instances_applies_a_base_condition(repo, session, data):
    """A condition on a base entity lands in the WHERE clause."""
    cond = ResolvedCondition(variable=Project.ProjectName, operator="==", value="Alpha")

    assert _ids(_instances(repo, [cond])) == ["img-a1", "img-a2"]


def test_search_instances_paginates(repo, session, data):
    """limit/offset window the ordered result."""
    assert _ids(_instances(repo, limit=2, offset=0)) == ["img-a1", "img-a2"]
    assert _ids(_instances(repo, limit=2, offset=2)) == ["img-b1"]


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

    assert _ids(_instances(repo, [cond])) == expected


@pytest.mark.parametrize("value,expected", [("schema-x", ["img-a1"]), ("nope", [])])
def test_forms_exists_branch_positive_and_empty(repo, session, data, value, expected):
    """The forms EXISTS semijoin correlates image-level form annotations."""
    from eyened_orm import FormSchema

    cond = ResolvedCondition(variable=FormSchema.SchemaName, operator="==", value=value)

    assert _ids(_instances(repo, [cond])) == expected


@pytest.mark.parametrize("value,expected", [("img-tag", ["img-a1"]), ("nope", [])])
def test_image_tag_exists_branch_positive_and_empty(repo, session, data, value, expected):
    """The image-tag EXISTS semijoin matches only tagged instances."""
    from eyened_orm.repositories.search import InstTag

    cond = ResolvedCondition(variable=InstTag.TagName, operator="==", value=value)

    assert _ids(_instances(repo, [cond])) == expected


@pytest.mark.parametrize("value,expected", [(5, ["img-a1"]), (99, [])])
def test_attribute_exists_branch_positive_and_empty(repo, session, data, value, expected):
    """The attribute EXISTS resolves the definition and filters the typed value column."""
    spec = AttributeConditionSpec(attribute="Quality", operator="==", value=value, model="M1")

    assert _ids(_instances(repo, attr_conditions=[spec])) == expected


def test_unresolvable_attribute_is_skipped(repo, session, data):
    """The repository still drops an unresolved definition; the *service* rejects it
    with a 400 before the repository is ever asked (see SearchService.search_instances)."""
    spec = AttributeConditionSpec(attribute="NoSuchAttr", operator="==", value=1)

    assert _ids(_instances(repo, attr_conditions=[spec])) == [
        "img-a1",
        "img-a2",
        "img-b1",
    ]


def test_search_studies_and_count(repo, session, data):
    """Study search returns ordered studies and counts the same predicate."""
    rows = repo.search_studies(
        conditions=[], order_by=Study.StudyDate, order="ASC", limit=100, offset=0
    )

    assert [s.StudyID for s in rows] == [data.studies["a"].StudyID, data.studies["b"].StudyID]
    assert repo.count_studies(conditions=[]) == 2


def test_search_studies_applies_a_base_condition(repo, session, data):
    """A study condition on a joined base entity lands in the WHERE clause."""
    cond = ResolvedCondition(variable=Patient.PatientIdentifier, operator="==", value="PAT-B")
    rows = repo.search_studies(
        conditions=[cond], order_by=Study.StudyDate, order="ASC", limit=100, offset=0
    )

    assert [s.StudyID for s in rows] == [data.studies["b"].StudyID]


def test_instances_for_studies_returns_active_instances(repo, session, data):
    """instances_for_studies returns the studies' active instances."""
    rows = repo.instances_for_studies([data.studies["a"].StudyID])

    assert sorted(_ids(rows)) == ["img-a1", "img-a2"]


def test_instances_for_studies_with_no_ids_returns_empty(repo, session, data):
    """An empty study-id list returns no rows rather than every instance."""
    assert repo.instances_for_studies([]) == []


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
    resolved = repo.resolve_attribute_definitions([spec])

    assert resolved[("M1", "Quality", None)].AttributeName == "Quality"


def test_studies_by_ids_loads_the_requested_studies(repo, session, data):
    """studies_by_ids returns exactly the requested studies, active instances loaded."""
    # Read the id first, then commit, so the session state matches a real request's.
    # Study.Series and Series.ImageInstances are both lazy="selectin", so *touching a
    # Study after the commit expires it* refetches those collections unfiltered -- and
    # a filtered selectinload populates an empty collection, it never prunes a loaded
    # one, so the inactive image would survive the filter and this test would pin the
    # opposite of the truth. The service path is unaffected: it never re-reads a Study
    # that way, and its studies payload is active-only (verified end to end).
    study_id = data.studies["a"].StudyID
    session.commit()

    rows = repo.studies_by_ids([study_id])

    assert [s.StudyID for s in rows] == [study_id]
    assert sorted(i.PublicID for s in rows for ser in s.Series for i in ser.ImageInstances) == [
        "img-a1",
        "img-a2",
    ]


def test_studies_by_ids_with_no_ids_returns_empty(repo, session, data):
    """An empty id list returns no rows rather than every study."""
    assert repo.studies_by_ids([]) == []


def test_tag_names_lists_linked_tags_sorted(repo, session, data):
    """tag_names returns the distinct tag names reachable through a link table."""
    from eyened_orm import ImageInstanceTagLink

    assert repo.tag_names(ImageInstanceTagLink) == ["img-tag"]


def test_active_form_creator_names_excludes_inactive_annotations(repo, session, data):
    """Only creators with a live form annotation are listed."""
    assert repo.active_form_creator_names() == ["form-creator"]


def test_attribute_signature_rows_carry_name_dtype_and_model(repo, session, data):
    """Attribute rows describe (name, dtype, producing model) and skip JSON attributes."""
    from eyened_orm.attributes import AttributeDataType

    assert repo.attribute_signature_rows() == [
        ("Quality", AttributeDataType.Int, "M1")
    ]
