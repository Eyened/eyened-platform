import pytest

from eyened_orm.utils.factories import seed_search_dataset


@pytest.fixture()
def data(session):
    return seed_search_dataset(session)


def _by_name(items):
    return {item["name"]: item for item in items}


def test_instance_signature_lists_every_searchable_field(client, data):
    """The instance signature advertises exactly the fields searchable_fields allows."""
    resp = client.get("/instances/search/signature")

    assert resp.status_code == 200
    assert set(_by_name(resp.json())) == {
        "Image DBID",
        "Laterality",
        "Modality",
        "ETDRS Field",
        "Color Fundus Quality",
        "Study Date",
        "Patient Identifier",
        "Patient Sex",
        "Patient Birthdate",
        "Project Name",
        "Device Model ID",
        "Segmentation Feature Name",
        "Segmentation Creator Name",
        "Segmentation Tag Name",
        "Form Schema Name",
        "Form Creator Name",
        "Form Tag Name",
        "Image Tag Name",
        "Quality",
    }


def test_instance_signature_exposes_nullable_and_multi(client, data):
    """nullable/multi are declared, serialized, and consumed by the client -- not dropped."""
    fields = _by_name(client.get("/instances/search/signature").json())

    assert fields["Patient Identifier"]["multi"] is True
    assert fields["Laterality"]["nullable"] is True


def test_instance_signature_enumerates_db_derived_values(client, data):
    """DB-derived fields carry the seeded values, sorted."""
    fields = _by_name(client.get("/instances/search/signature").json())

    assert fields["Project Name"]["values"] == ["Alpha", "Beta"]
    assert fields["Segmentation Feature Name"]["values"] == ["feat-x"]
    assert fields["Segmentation Tag Name"]["values"] == ["seg-tag"]
    assert fields["Form Tag Name"]["values"] == ["form-tag"]
    assert fields["Image Tag Name"]["values"] == ["img-tag"]


def test_instance_signature_describes_attributes(client, data):
    """Attribute definitions surface as type=attribute entries carrying their model."""
    quality = _by_name(client.get("/instances/search/signature").json())["Quality"]

    assert quality["type"] == "attribute"
    assert quality["values"] == "int"
    assert quality["model"] == "M1"


def test_study_signature_enumerates_db_derived_values(client, data):
    """The study signature carries the seeded project/schema/tag values."""
    fields = _by_name(client.get("/studies/search/signature").json())

    assert fields["Project Name"]["values"] == ["Alpha", "Beta"]
    assert fields["Form Schema Name"]["values"] == ["schema-x"]
    assert fields["Study Tag Name"]["values"] == ["study-tag"]


def test_study_signature_advertises_a_field_that_cannot_be_searched(client, data):
    """PRE-EXISTING BUG pinned as-is: the signature offers 'Study Instance UID',
    but study_searchable_fields omits it, so searching it 422s. Not fixed by this
    plan -- see Follow-up work; this test documents the bug until someone does."""
    fields = _by_name(client.get("/studies/search/signature").json())
    assert "Study Instance UID" in fields

    resp = client.post(
        "/studies/search",
        json={
            "conditions": [
                {"variable": "Study Instance UID", "operator": "==", "value": "x"}
            ],
            "order_by": "Study Date",
            "order": "ASC",
        },
    )

    assert resp.status_code == 422
