import os
from datetime import date
from pathlib import Path
from typing import List

from eyened_orm import Database
from eyened_orm.importer.importer import Importer
from eyened_orm.importer.importer_dtos import ImageImport, SeriesImport, StudyImport, PatientImport


def get_image_paths() -> List[Path]:
    base_dir = Path("/images")
    images_dir = base_dir / "hrfav/images"
    print(f"Searching for images in {images_dir}")
    image_paths = sorted(list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.JPG")))
    image_paths = [image_path.relative_to(base_dir) for image_path in image_paths]
    print(f"Found {len(image_paths)} images.")
    return image_paths


def get_image_import(image_path: Path) -> ImageImport:
    object_key = str(image_path)
    storage_backend_key = "test"
    return ImageImport(object_key=object_key, storage_backend_key=storage_backend_key)


def main():
    session = Database().create_session()
    importer = Importer(
        session=session,
        create_projects=True,
        create_patients=True,
        create_studies=True,
        create_series=True,
        generate_thumbnails=True,
    )

    image_paths = get_image_paths()
    patient_data = []
    batch_size = 10
    project_name = "FAU Fundus Dataset (for tests)"
    for i in range(0, len(image_paths), batch_size):
        batch_images = image_paths[i: i + batch_size]

        # Create image objects
        images = [get_image_import(img_path) for img_path in batch_images]

        # Create hierarchy objects
        series = SeriesImport(images=images)
        study = StudyImport(study_date=date.today(), series=[series])

        patient_item = PatientImport(
            project_name=project_name,
            patient_identifier=f"Patient_{i // batch_size + 1}",
            studies=[study],
        )

        patient_data.append(patient_item)

    print(f"Created data structure with {len(patient_data)} patients.")
    print(f"First patient has {len(patient_data[0].studies[0].series[0].images)} images.")

    import_apply = bool(int(os.getenv("IMPORT_APPLY", 0)))
    if not import_apply:
        print("IMPORT_APPLY environment variable not set (or set to 0). Only showing a summary of things that will be imported.")
    importer.import_many(patient_data, summary=(not import_apply))

if __name__ == "__main__":
    main()
