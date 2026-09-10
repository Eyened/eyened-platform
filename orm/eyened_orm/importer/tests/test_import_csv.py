from __future__ import annotations

from datetime import date, datetime

import pytest

from eyened_orm.importer.import_csv import read_import_rows_csv


def test_write_import_rows_csv_round_trip(tmp_path):
    from eyened_orm.image_instance import Laterality, Modality
    from eyened_orm.importer.import_csv import write_import_rows_csv
    from eyened_orm.importer.importer_dtos import ImportRow

    rows = [
        ImportRow(
            project_name="proj-1",
            patient_identifier="pat-1",
            study_date=date(2026, 4, 15),
            series_instance_uid="1.2.3.series",
            modality=Modality.OCT,
            laterality=Laterality.L,
            width=512,
            height=496,
            image_storage_is_primary=True,
            object_key="vol.dcm",
        ),
        ImportRow(
            project_name="proj-1",
            patient_identifier="pat-2",
            object_key="op.dcm",
        ),
    ]
    path = write_import_rows_csv(rows, tmp_path / "out.csv")
    text = path.read_text(encoding="utf-8")
    assert "modality" in text.splitlines()[0]
    assert "birth_date" not in text.splitlines()[0]  # unused columns omitted

    loaded = read_import_rows_csv(path)
    assert len(loaded) == 2
    assert loaded[0].project_name == "proj-1"
    assert loaded[0].patient_identifier == "pat-1"
    assert loaded[0].study_date == date(2026, 4, 15)
    assert loaded[0].series_instance_uid == "1.2.3.series"
    assert loaded[0].modality == Modality.OCT
    assert loaded[0].laterality == Laterality.L
    assert loaded[0].width == 512
    assert loaded[0].height == 496
    assert loaded[0].image_storage_is_primary is True
    assert loaded[1].patient_identifier == "pat-2"
    assert loaded[1].modality is None


def test_write_import_rows_csv_exports_prepared_like_metadata(tmp_path):
    """Typical verify workflow: prepare_rows → write CSV → read back."""
    from eyened_orm.image_instance import Modality, ModalityType
    from eyened_orm.importer.import_csv import write_import_rows_csv
    from eyened_orm.importer.importer_dtos import ImportRow

    prepared = [
        ImportRow(
            project_name="p",
            storage_backend_key="sb",
            object_key="vol.dcm",
            image_storage_format="dicom",
            patient_identifier="P-EXPORT",
            study_date=date(2025, 4, 1),
            series_instance_uid="1.2.3.export.series",
            sop_instance_uid="1.2.3.export",
            dicom_modality=ModalityType.OPT,
            modality=Modality.OCT,
            width=128,
            height=64,
        )
    ]
    path = write_import_rows_csv(prepared, tmp_path / "inferred.csv")
    loaded = read_import_rows_csv(path)
    assert loaded[0].patient_identifier == "P-EXPORT"
    assert loaded[0].study_date == date(2025, 4, 1)
    assert loaded[0].series_instance_uid == "1.2.3.export.series"
    assert loaded[0].modality == Modality.OCT
    assert loaded[0].width == 128
    assert loaded[0].height == 64


def test_write_import_rows_csv_unknown_column_raises(tmp_path):
    from eyened_orm.importer.import_csv import write_import_rows_csv
    from eyened_orm.importer.importer_dtos import ImportRow

    with pytest.raises(ValueError, match="Unknown ImportRow column"):
        write_import_rows_csv(
            [ImportRow(project_name="p")],
            tmp_path / "bad.csv",
            columns=["project_name", "not_a_field"],
        )


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


def test_read_import_rows_csv_empty_cells_are_omitted(tmp_path):
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
    assert "study_date" not in rows[0].model_fields_set
    assert "patient_identifier" in rows[0].model_fields_set


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
