import pytest

from eyened_orm.repositories.search import SearchRepository
from eyened_orm.utils.factories import seed_search_dataset
from server.services.search import SearchService


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


@pytest.fixture()
def service(session):
    return SearchService(SearchRepository(session))


def _search(service, conditions=(), **kw):
    kw.setdefault("order_by", "Date Inserted")
    kw.setdefault("order", "ASC")
    return service.search_instances(conditions=list(conditions), **kw)


def test_search_instances_reports_has_more_without_leaking_the_lookahead_row(
    service, session, data
):
    """The limit+1 lookahead sets has_more but is trimmed from the results."""
    result = _search(service, limit=2, page=0)

    assert [i.PublicID for i in result.instances] == ["img-a1", "img-a2"]
    assert result.has_more is True


def test_search_instances_last_page_has_no_more(service, session, data):
    """The final page reports has_more False."""
    result = _search(service, limit=2, page=1)

    assert [i.PublicID for i in result.instances] == ["img-b1"]
    assert result.has_more is False


def test_search_instances_derives_studies_in_instance_order(service, session, data):
    """Studies are the instances' distinct studies, in first-appearance order."""
    result = _search(service)

    assert [s.StudyID for s in result.studies] == [
        data.studies["a"].StudyID,
        data.studies["b"].StudyID,
    ]


def test_search_instances_count_is_none_unless_requested(service, session, data):
    """count stays None unless include_count is set."""
    assert _search(service).count is None


def test_search_instances_count_ignores_pagination(service, session, data):
    """include_count counts the whole predicate, not the current page."""
    result = _search(service, limit=1, page=0, include_count=True)

    assert len(result.instances) == 1
    assert result.count == 3


def test_search_instances_with_no_matches_returns_empty_result(service, session, data):
    """A search matching nothing returns empty lists, not None."""
    result = _search(
        service,
        [{"type": "default", "variable": "Project Name", "operator": "==", "value": "Nope"}],
    )

    assert result.instances == []
    assert result.studies == []
    assert result.has_more is False


def test_search_studies_paginates_and_counts(service, session, data):
    """Study search applies the same limit+1/has_more and include_count policy."""
    result = service.search_studies(
        conditions=[], order_by="Study Date", order="ASC", limit=1, page=0,
        include_count=True,
    )

    assert [s.StudyID for s in result.studies] == [data.studies["a"].StudyID]
    assert result.has_more is True
    assert result.count == 2


def test_instance_signature_lists_the_vocabulary(service, session, data):
    """The instance signature covers the searchable fields plus seeded attributes."""
    names = {f.name for f in service.instance_signature()}

    assert "Project Name" in names
    assert "Quality" in names


def test_study_signature_lists_the_vocabulary(service, session, data):
    """The study signature covers the study searchable fields."""
    names = {f.name for f in service.study_signature()}

    assert "Study Tag Name" in names


def test_unresolvable_attribute_raises_bad_request(service, session, data):
    """An attribute that resolves to nothing is a 400, not a silently-dropped filter."""
    from server.services.exceptions import BadRequestError

    with pytest.raises(BadRequestError):
        _search(
            service,
            [{"type": "attribute", "model": None, "variable": "NoSuchAttr",
              "operator": "==", "value": 1}],
        )


def test_attribute_definitions_are_resolved_once_per_search(service, session, data):
    """The resolution N+1 runs once, not once per select build (validate + search + count)."""
    from sqlalchemy import event

    stmts: list[str] = []

    def _rec(conn, cursor, statement, params, context, executemany):
        stmts.append(" ".join(statement.split()))

    bind = session.get_bind()
    event.listen(bind, "before_cursor_execute", _rec)
    try:
        _search(
            service,
            [{"type": "attribute", "model": "M1", "variable": "Quality",
              "operator": "==", "value": 5}],
            include_count=True,
        )
    finally:
        event.remove(bind, "before_cursor_execute", _rec)

    # Matched on the resolution join rather than the SELECT prefix: the prefix
    # carries a DISTINCT that is incidental to what this test pins, and matching it
    # would make the count silently drop to 0 if it changed. This join shape is the
    # resolution query and nothing else -- the selectinload of AttributeDefinition
    # aliases its columns and does not join AttributesModelOutput.
    resolutions = [
        s
        for s in stmts
        if 'FROM "AttributeDefinition" JOIN "AttributesModelOutput"' in s
    ]
    assert len(resolutions) == 1
