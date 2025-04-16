"""index renaming

Revision ID: e5d9bb4214cb
Revises: 7aff6bc32315
Create Date: 2024-09-18 19:15:16.605353

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e5d9bb4214cb"
down_revision = "7aff6bc32315"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # All create_index operations
    op.create_index(
        op.f("AnnotationTypeID"), "Annotation", ["AnnotationTypeID"], unique=False
    )
    op.create_index(op.f("CreatorID"), "Annotation", ["CreatorID"], unique=False)
    op.create_index(op.f("FeatureID"), "Annotation", ["FeatureID"], unique=False)
    op.create_index(
        op.f("ImageInstanceID"), "Annotation", ["ImageInstanceID"], unique=False
    )
    op.create_index(op.f("PatientID"), "Annotation", ["PatientID"], unique=False)
    op.create_index(op.f("SeriesID"), "Annotation", ["SeriesID"], unique=False)
    op.create_index(op.f("StudyID"), "Annotation", ["StudyID"], unique=False)
    op.create_index(
        op.f("AnnotationID"), "AnnotationData", ["AnnotationID"], unique=False
    )
    op.create_index(
        op.f("AnnotationID"), "AnnotationTag", ["AnnotationID"], unique=False
    )
    op.create_index(op.f("TagID"), "AnnotationTag", ["TagID"], unique=False)
    op.create_index(op.f("CreatorID"), "FormAnnotation", ["CreatorID"], unique=False)
    op.create_index(
        op.f("FormSchemaID"), "FormAnnotation", ["FormSchemaID"], unique=False
    )
    op.create_index(
        op.f("ImageInstanceID"), "FormAnnotation", ["ImageInstanceID"], unique=False
    )
    op.create_index(op.f("PatientID"), "FormAnnotation", ["PatientID"], unique=False)
    op.create_index(op.f("StudyID"), "FormAnnotation", ["StudyID"], unique=False)
    op.create_index(op.f("SubTaskID"), "FormAnnotation", ["SubTaskID"], unique=False)
    op.create_index(op.f("DeviceID"), "ImageInstance", ["DeviceID"], unique=False)
    op.create_index(op.f("ModalityID"), "ImageInstance", ["ModalityID"], unique=False)
    op.create_index(op.f("ScanID"), "ImageInstance", ["ScanID"], unique=False)
    op.create_index(op.f("SeriesID"), "ImageInstance", ["SeriesID"], unique=False)
    op.create_index(
        op.f("SourceInfoID"), "ImageInstance", ["SourceInfoID"], unique=False
    )
    op.create_index(
        op.f("ImageInstanceID"), "ImageInstanceTag", ["ImageInstanceID"], unique=False
    )
    op.create_index(op.f("TagID"), "ImageInstanceTag", ["TagID"], unique=False)
    op.create_index(op.f("ProjectID"), "Patient", ["ProjectID"], unique=False)
    op.create_index(op.f("StudyID"), "Series", ["StudyID"], unique=False)
    op.create_index(op.f("PatientID"), "Study", ["PatientID"], unique=False)
    op.create_index(op.f("StudyID"), "StudyTag", ["StudyID"], unique=False)
    op.create_index(op.f("TagID"), "StudyTag", ["TagID"], unique=False)

    # Rest of the operations
    op.drop_index("fk_Annotation_AnnotationType1_idx", table_name="Annotation")
    op.drop_index("fk_Annotation_Features1_idx", table_name="Annotation")
    op.drop_index("fk_Annotation_Grader1_idx", table_name="Annotation")
    op.drop_index("fk_Annotation_ImageInstance1_idx", table_name="Annotation")
    op.drop_index("fk_Annotation_Patient1_idx", table_name="Annotation")
    op.drop_index("fk_Annotation_Series1_idx", table_name="Annotation")
    op.drop_index("fk_Annotation_Study1_idx", table_name="Annotation")
    op.drop_index("DatasetIdentifier_UNIQUE", table_name="AnnotationData")
    op.drop_index("fk_AnnotationData_Annotation1_idx", table_name="AnnotationData")
    op.create_unique_constraint(
        op.f("AnnotationData_DatasetIdentifier_UNIQUE"),
        "AnnotationData",
        ["DatasetIdentifier"],
    )
    op.drop_constraint(
        "fk_AnnotationData_Annotation1", "AnnotationData", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_AnnotationData_Annotation1"),
        "AnnotationData",
        "Annotation",
        ["AnnotationID"],
        ["AnnotationID"],
    )
    op.drop_index("fk_AnnotationTag_Annotation1_idx", table_name="AnnotationTag")
    op.drop_index("fk_AnnotationTag_Tag1_idx", table_name="AnnotationTag")
    op.drop_constraint("fk_AnnotationTag_Tag1", "AnnotationTag", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_AnnotationTag_Tag1"), "AnnotationTag", "Tag", ["TagID"], ["TagID"]
    )
    op.drop_index("CreatorName_UNIQUE", table_name="Creator")
    op.create_unique_constraint(
        op.f("Creator_CreatorName_UNIQUE"), "Creator", ["CreatorName"]
    )
    op.drop_index("FeatureName_UNIQUE", table_name="Feature")
    op.create_unique_constraint(
        op.f("Feature_FeatureName_UNIQUE"), "Feature", ["FeatureName"]
    )
    op.drop_index("fk_FormAnnotation_Creator1_idx", table_name="FormAnnotation")
    op.drop_index("fk_FormAnnotation_FormSchema1_idx", table_name="FormAnnotation")
    op.drop_index("fk_FormAnnotation_ImageInstance1_idx", table_name="FormAnnotation")
    op.drop_index("fk_FormAnnotation_Patient1_idx", table_name="FormAnnotation")
    op.drop_index("fk_FormAnnotation_Study1_idx", table_name="FormAnnotation")
    op.drop_index("fk_FormAnnotation_SubTask1_idx", table_name="FormAnnotation")
    op.drop_index("SchemaName_UNIQUE", table_name="FormSchema")
    op.create_unique_constraint(
        op.f("FormSchema_SchemaName_UNIQUE"), "FormSchema", ["SchemaName"]
    )
    op.drop_index("SOPInstanceUid_UNIQUE", table_name="ImageInstance")
    op.create_unique_constraint(
        op.f("ImageInstance_SOPInstanceUid_UNIQUE"), "ImageInstance", ["SOPInstanceUid"]
    )
    op.drop_index("fk_ImageInstance_Devices1_idx", table_name="ImageInstance")
    op.drop_index("fk_ImageInstance_Modality1_idx", table_name="ImageInstance")
    op.drop_index("fk_ImageInstance_Scan1_idx", table_name="ImageInstance")
    op.drop_index("fk_ImageInstance_Series1_idx", table_name="ImageInstance")
    op.drop_index("fk_ImageInstance_Sources1_idx1", table_name="ImageInstance")
    op.drop_index(
        "fk_ImageInstanceTag_ImageInstance1_idx", table_name="ImageInstanceTag"
    )
    op.drop_index("fk_ImageInstanceTag_Tag1_idx", table_name="ImageInstanceTag")
    op.drop_constraint(
        "fk_ImageInstanceTag_Tag1", "ImageInstanceTag", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_ImageInstanceTag_Tag1"),
        "ImageInstanceTag",
        "Tag",
        ["TagID"],
        ["TagID"],
    )
    op.drop_index("ModalityTag_UNIQUE", table_name="Modality")
    op.create_unique_constraint(
        op.f("Modality_ModalityTag_UNIQUE"), "Modality", ["ModalityTag"]
    )
    op.drop_index("fk_Patient_Project1_idx", table_name="Patient")
    op.drop_index("ProjectName_UNIQUE", table_name="Project")
    op.create_unique_constraint(
        op.f("Project_ProjectName_UNIQUE"), "Project", ["ProjectName"]
    )
    op.drop_index("ScanMode_UNIQUE", table_name="Scan")
    op.create_unique_constraint(op.f("Scan_ScanMode_UNIQUE"), "Scan", ["ScanMode"])
    op.drop_index("SeriesInstanceUid_UNIQUE", table_name="Series")
    op.drop_index("fk_Series_Study1_idx", table_name="Series")
    op.create_unique_constraint(
        op.f("Series_SeriesInstanceUid_UNIQUE"), "Series", ["SeriesInstanceUid"]
    )
    op.drop_index("SourceName_UNIQUE", table_name="SourceInfo")
    op.drop_index("SourcePath_UNIQUE", table_name="SourceInfo")
    op.drop_index("ThumbnailPath_UNIQUE", table_name="SourceInfo")
    op.create_unique_constraint(
        op.f("SourceInfo_SourceName_UNIQUE"), "SourceInfo", ["SourceName"]
    )
    op.create_unique_constraint(
        op.f("SourceInfo_SourcePath_UNIQUE"), "SourceInfo", ["SourcePath"]
    )
    op.create_unique_constraint(
        op.f("SourceInfo_ThumbnailPath_UNIQUE"), "SourceInfo", ["ThumbnailPath"]
    )
    op.drop_index("StudyInstanceUid_UNIQUE", table_name="Study")
    op.drop_index("fk_Study_Patient1_idx", table_name="Study")
    op.create_unique_constraint(
        op.f("Study_StudyInstanceUid_UNIQUE"), "Study", ["StudyInstanceUid"]
    )
    op.drop_index("fk_StudyTag_Study1_idx", table_name="StudyTag")
    op.drop_index("fk_StudyTag_Tag1_idx", table_name="StudyTag")

    op.drop_index("TagName_UNIQUE", table_name="Tag")
    op.create_unique_constraint(op.f("Tag_TagName_UNIQUE"), "Tag", ["TagName"])
    op.drop_index("TaskName_UNIQUE", table_name="Task")
    op.drop_index("TaskDefinitionName_UNIQUE", table_name="TaskDefinition")
    op.drop_index("TaskStateName_UNIQUE", table_name="TaskState")

    op.create_index(
    op.f("ImageInstanceID"), "SubTaskImageLink", ["ImageInstanceID"], unique=False
    )
    op.create_index(op.f("SubTaskID"), "SubTaskImageLink", ["SubTaskID"], unique=False)
    op.drop_index(
        "fk_SubTaskImageLink_ImageInstance1_idx", table_name="SubTaskImageLink"
    )
    op.drop_index("fk_SubTaskImageLink_SubTask1_idx", table_name="SubTaskImageLink")
