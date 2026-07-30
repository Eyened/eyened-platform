import pytest

from eyened_orm.utils.factories import seed_search_dataset


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


def _search(client, conditions, **kw):
    body = {"conditions": conditions, "order_by": "Date Inserted", "order": "ASC"}
    body.update(kw)
    resp = client.post("/instances/search", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _cond(variable, value, operator="=="):
    return {"type": "default", "variable": variable, "operator": operator, "value": value}


def test_unfiltered_search_returns_active_instances_only(client, data):
    """No conditions returns every active instance in Date Inserted order; inactive is excluded."""
    body = _search(client, [], include_count=True)

    assert body["result_ids"] == ["img-a1", "img-a2", "img-b1"]
    assert body["count"] == 3


def test_include_count_defaults_to_null(client, data):
    """count is omitted (None) unless include_count is requested."""
    body = _search(client, [])

    assert body.get("count") is None


@pytest.mark.parametrize(
    "variable,value,expected",
    [
        ("Project Name", "Alpha", ["img-a1", "img-a2"]),
        ("Patient Identifier", "PAT-B", ["img-b1"]),
        ("Segmentation Feature Name", "feat-x", ["img-a1"]),
        ("Segmentation Creator Name", "seg-creator", ["img-a1"]),
        ("Segmentation Tag Name", "seg-tag", ["img-a1"]),
        ("Form Schema Name", "schema-x", ["img-a1"]),
        ("Form Creator Name", "form-creator", ["img-a1"]),
        ("Form Tag Name", "form-tag", ["img-a1"]),
        ("Image Tag Name", "img-tag", ["img-a1"]),
    ],
)
def test_each_exists_branch_filters_to_the_expected_instances(
    client, data, variable, value, expected
):
    """Each searchable field routes through its EXISTS branch and matches the right rows."""
    assert _search(client, [_cond(variable, value)])["result_ids"] == expected


@pytest.mark.parametrize(
    "variable,value",
    [
        ("Project Name", "NoSuchProject"),
        ("Segmentation Feature Name", "no-such-feature"),
        ("Form Tag Name", "no-such-tag"),
        ("Image Tag Name", "no-such-tag"),
    ],
)
def test_each_exists_branch_has_an_empty_case(client, data, variable, value):
    """A non-matching value returns no rows rather than falling open."""
    body = _search(client, [_cond(variable, value)], include_count=True)

    assert body["result_ids"] == []
    assert body["has_more"] is False


def test_conditions_are_and_ed_together(client, data):
    """Multiple conditions AND globally (today's semantics): the result is their intersection.

    Verified against the code: `_build_instance_select` combines every group
    with `and_(*and_predicates)`.
    """
    # Alpha images are a1,a2; feat-x is on a1 only. AND narrows to a1 (OR would give a1,a2).
    narrowed = _search(
        client, [_cond("Project Name", "Alpha"), _cond("Segmentation Feature Name", "feat-x")]
    )
    assert narrowed["result_ids"] == ["img-a1"]

    # Contradictory conditions (Alpha project, but PAT-B lives in Beta) yield no rows.
    contradictory = _search(
        client, [_cond("Project Name", "Alpha"), _cond("Patient Identifier", "PAT-B")]
    )
    assert contradictory["result_ids"] == []


def test_in_operator_matches_any_listed_value(client, data):
    """A list value becomes an IN over the mapped column."""
    body = _search(client, [_cond("Patient Identifier", ["PAT-A", "PAT-B"], operator="IN")])

    assert body["result_ids"] == ["img-a1", "img-a2", "img-b1"]


def test_attribute_condition_filters_by_model_produced_value(client, data):
    """An attribute condition resolves the definition and filters on the typed value column."""
    body = _search(
        client,
        [{"type": "attribute", "model": "M1", "variable": "Quality", "operator": "==", "value": 5}],
    )

    assert body["result_ids"] == ["img-a1"]


def test_order_desc_reverses_results(client, data):
    """order=DESC reverses the sort while keeping the ImageInstanceID tiebreaker."""
    body = _search(client, [], order="DESC")

    assert body["result_ids"] == ["img-b1", "img-a2", "img-a1"]


def test_pagination_reports_has_more_and_walks_pages(client, data):
    """limit+1 lookahead drives has_more; page N returns the Nth window."""
    page0 = _search(client, [], limit=2, page=0)
    page1 = _search(client, [], limit=2, page=1)

    assert page0["result_ids"] == ["img-a1", "img-a2"]
    assert page0["has_more"] is True
    assert page1["result_ids"] == ["img-b1"]
    assert page1["has_more"] is False


def test_studies_are_derived_from_instances_in_instance_order(client, data):
    """The studies block is the instances' distinct studies, in first-appearance order."""
    body = _search(client, [])

    assert [s["id"] for s in body["studies"]] == [
        data.studies["a"].StudyID,
        data.studies["b"].StudyID,
    ]


def test_empty_result_returns_the_empty_envelope(client, data):
    """A search matching nothing returns empty lists and has_more False, not a 404."""
    body = _search(client, [_cond("Project Name", "NoSuchProject")], include_count=True)

    assert body["instances"] == []
    assert body["studies"] == []
    assert body["result_ids"] == []
    assert body["has_more"] is False


def test_unknown_static_field_is_rejected_by_pydantic(client, data):
    """An unknown static field 422s at request parsing -- the reason both asserts are dead code."""
    resp = client.post(
        "/instances/search",
        json={
            "conditions": [_cond("Patient Identifir", "PAT-A")],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 422


def test_unknown_order_by_is_rejected_by_pydantic(client, data):
    """order_by is Literal-typed, so an unknown sort field 422s rather than KeyError-ing."""
    resp = client.post(
        "/instances/search",
        json={"conditions": [], "order_by": "Nonsense", "order": "ASC"},
    )

    assert resp.status_code == 422


def test_unknown_attribute_field_is_rejected(client, data):
    """An unresolvable attribute 400s rather than silently returning every row.

    Behavior change (was: filter dropped, full result set returned).
    """
    resp = client.post(
        "/instances/search",
        json={
            "conditions": [
                {"type": "attribute", "model": None, "variable": "NoSuchAttr",
                 "operator": "==", "value": 1}
            ],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 400


def test_in_operator_with_a_scalar_value_is_rejected(client, data):
    """PRE-EXISTING BUG fixed: IN + scalar raised an uncaught ValueError (500); now a 400."""
    resp = client.post(
        "/instances/search",
        json={
            "conditions": [
                {"type": "default", "variable": "Patient Identifier",
                 "operator": "IN", "value": "PAT-A"}
            ],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 400
