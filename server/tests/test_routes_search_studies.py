import pytest

from eyened_orm.utils.factories import seed_search_dataset


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


def _search(client, conditions, **kw):
    body = {"conditions": conditions, "order_by": "Study Date", "order": "ASC"}
    body.update(kw)
    resp = client.post("/studies/search", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _cond(variable, value, operator="=="):
    return {"variable": variable, "operator": operator, "value": value}


def test_unfiltered_study_search_returns_all_studies(client, data):
    """No conditions returns every study in Study Date order."""
    body = _search(client, [], include_count=True)

    assert body["result_ids"] == [data.studies["a"].StudyID, data.studies["b"].StudyID]
    assert body["count"] == 2


@pytest.mark.parametrize(
    "variable,value,expected_key",
    [
        ("Project Name", "Beta", "b"),
        ("Patient Identifier", "PAT-A", "a"),
        ("Study Description", "study-a", "a"),
        ("Study Round", 2, "b"),
        ("Study Tag Name", "study-tag", "b"),
        ("Form Schema Name", "schema-x", "b"),
        ("Form Creator Name", "form-creator", "b"),
    ],
)
def test_each_study_branch_filters_to_the_expected_study(
    client, data, variable, value, expected_key
):
    """Each study-searchable field routes through its branch and matches the right study.

    Only the study-level form annotation (on study-b) satisfies the forms EXISTS,
    which correlates on StudyID; img-a1's form annotation is image-level.
    """
    body = _search(client, [_cond(variable, value)])

    assert body["result_ids"] == [data.studies[expected_key].StudyID]


def test_study_search_returns_instances_for_matched_studies(client, data):
    """The instances block carries every active instance of the matched studies."""
    body = _search(client, [_cond("Project Name", "Alpha")])

    assert sorted(i["id"] for i in body["instances"]) == ["img-a1", "img-a2"]


def test_study_search_pagination_reports_has_more(client, data):
    """limit+1 lookahead drives has_more on the study surface too."""
    page0 = _search(client, [], limit=1, page=0)
    page1 = _search(client, [], limit=1, page=1)

    assert page0["result_ids"] == [data.studies["a"].StudyID]
    assert page0["has_more"] is True
    assert page1["result_ids"] == [data.studies["b"].StudyID]
    assert page1["has_more"] is False


def test_study_search_empty_result_returns_the_empty_envelope(client, data):
    """A study search matching nothing returns empty lists, not a 404."""
    body = _search(client, [_cond("Project Name", "NoSuchProject")], include_count=True)

    assert body["studies"] == []
    assert body["instances"] == []
    assert body["result_ids"] == []
    assert body["has_more"] is False


def test_study_search_unknown_field_is_rejected_by_pydantic(client, data):
    """study_searchable_fields is a Literal, so an unknown field 422s at parsing."""
    resp = client.post(
        "/studies/search",
        json={
            "conditions": [_cond("Nonsense", "x")],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 422
