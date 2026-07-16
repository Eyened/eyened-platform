import pytest

from eyened_orm.utils.factories import seed_search_dataset
from server.services.search import SearchService, get_search_service


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


@pytest.fixture()
def service():
    return get_search_service()


def _search(service, session, conditions=(), **kw):
    kw.setdefault("order_by", "Date Inserted")
    kw.setdefault("order", "ASC")
    return service.search_instances(session, conditions=list(conditions), **kw)


def test_get_search_service_returns_a_wired_service():
    """The factory wires a SearchService with its repository."""
    assert isinstance(get_search_service(), SearchService)


def test_search_instances_reports_has_more_without_leaking_the_lookahead_row(
    service, session, data
):
    """The limit+1 lookahead sets has_more but is trimmed from the results."""
    result = _search(service, session, limit=2, page=0)

    assert [i.PublicID for i in result.instances] == ["img-a1", "img-a2"]
    assert result.has_more is True


def test_search_instances_last_page_has_no_more(service, session, data):
    """The final page reports has_more False."""
    result = _search(service, session, limit=2, page=1)

    assert [i.PublicID for i in result.instances] == ["img-b1"]
    assert result.has_more is False


def test_search_instances_derives_studies_in_instance_order(service, session, data):
    """Studies are the instances' distinct studies, in first-appearance order."""
    result = _search(service, session)

    assert [s.StudyID for s in result.studies] == [
        data.studies["a"].StudyID,
        data.studies["b"].StudyID,
    ]


def test_search_instances_count_is_none_unless_requested(service, session, data):
    """count stays None unless include_count is set."""
    assert _search(service, session).count is None


def test_search_instances_count_ignores_pagination(service, session, data):
    """include_count counts the whole predicate, not the current page."""
    result = _search(service, session, limit=1, page=0, include_count=True)

    assert len(result.instances) == 1
    assert result.count == 3


def test_search_instances_with_no_matches_returns_empty_result(service, session, data):
    """A search matching nothing returns empty lists, not None."""
    result = _search(
        service,
        session,
        [{"type": "default", "variable": "Project Name", "operator": "==", "value": "Nope"}],
    )

    assert result.instances == []
    assert result.studies == []
    assert result.has_more is False


def test_search_studies_paginates_and_counts(service, session, data):
    """Study search applies the same limit+1/has_more and include_count policy."""
    result = service.search_studies(
        session, conditions=[], order_by="Study Date", order="ASC", limit=1, page=0,
        include_count=True,
    )

    assert [s.StudyID for s in result.studies] == [data.studies["a"].StudyID]
    assert result.has_more is True
    assert result.count == 2


def test_instance_signature_lists_the_vocabulary(service, session, data):
    """The instance signature covers the searchable fields plus seeded attributes."""
    names = {f.name for f in service.instance_signature(session)}

    assert "Project Name" in names
    assert "Quality" in names


def test_study_signature_lists_the_vocabulary(service, session, data):
    """The study signature covers the study searchable fields."""
    names = {f.name for f in service.study_signature(session)}

    assert "Study Tag Name" in names
