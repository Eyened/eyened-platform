from __future__ import annotations

from datetime import date, datetime

import pytest

from eyened_orm.importer.import_csv import read_import_rows_csv


def test_read_import_rows_csv_parses_common_types(tmp_path):
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(
        "\n".join(
            [
                "project_name,patient_identifier,study_date,image_storage_is_primary,series_number,acquisition_date_time,object_key",
                "proj-1,pat-1,2026-04-15,true,7,2026-04-15T12:34:56,img-1.png",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = read_import_rows_csv(csv_path)
    assert len(rows) == 1
    r = rows[0]
    assert r.project_name == "proj-1"
    assert r.patient_identifier == "pat-1"
    assert r.study_date == date(2026, 4, 15)
    assert r.image_storage_is_primary is True
    assert r.series_number == 7
    assert r.acquisition_date_time == datetime(2026, 4, 15, 12, 34, 56)
    assert r.object_key == "img-1.png"


def test_read_import_rows_csv_empty_cells_become_none(tmp_path):
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(
        "\n".join(
            [
                "project_name,patient_identifier,study_date",
                "proj-1,pat-1,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = read_import_rows_csv(csv_path)
    assert rows[0].study_date is None


def test_read_import_rows_csv_strict_columns_raises(tmp_path):
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(
        "\n".join(
            [
                "project_name,unknown_col",
                "proj-1,x",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown column"):
        read_import_rows_csv(csv_path, strict_columns=True)

