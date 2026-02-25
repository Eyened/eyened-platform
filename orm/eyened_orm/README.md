# Eyened ORM Architecture

## Usage

The ORM allows you to interact with the Eyened database for operations such as:
- Updating fields not updateable in the viewer
- Importing and exporting data
- Bulk updates to metadata or corrections

:::note
The Eyened API may provide a more convenient way to interact with the database. Use of the ORM is considered advanced as it provides broader functionality and more direct interaction with database objects.
:::

### Setup

To install the ORM locally as a Python package:

```bash
git clone https://github.com/Eyened/eyened-platform.git 
cd eyened-platform/orm
pip install -e .
```

### Connecting to the database

The easiest way to connect the ORM to a database from Python code is to use the `Database` class with a configuration:

```python
from eyened_orm import Database

# Initialize database
database = Database()

with database.get_session() as session:
    # Use session for database operations
    pass
```

:::tip
See [ORM Configuration](/eyened-platform/orm/configuration) for more information on how to create environments or manually set up configuration files for the ORM.
:::

### Working with database objects

Once connected, you can import and use database objects from the ORM:

```python
# Import database model classes
from eyened_orm import Project, Patient, Study, Series, ImageInstance

# Find a project by name
project = Project.by_name(session, 'My Project Name')

# Access related objects
for patient in project.Patients:
    print(f"Patient ID: {patient.PatientID}, Identifier: {patient.PatientIdentifier}")
    
    for study in patient.Studies:
        print(f"  Study date: {study.StudyDate}")
        
        for series in study.Series:
            print(f"    Series ID: {series.SeriesID}")
            
            for image in series.ImageInstances:
                print(f"      Image path: {image.path}")

# Query objects directly
patients = session.query(Patient).filter(Patient.PatientIdentifier.like("Patient_%")).all()

# You can also use Python-style attribute names
for patient in project.Patients:
    print(f"Patient ID: {patient.patient_id}, Identifier: {patient.patient_identifier}")
    
    for study in patient.Studies:
        print(f"  Study date: {study.study_date}")
```

:::tip
The properties on each ORM object are the same as the database column names (in capitalized camel case), but they're also exposed in Python style (snake_case). For example, you can access `patient_id` instead of `PatientID`, `patient_identifier` instead of `PatientIdentifier`, and `study_date` instead of `StudyDate`.
:::

For more information on using the ORM, see the [SQLAlchemy documentation](https://docs.sqlalchemy.org/en/20/).

## Architecture Overview

The Eyened ORM provides a comprehensive object-relational mapping for the Eyened database, which stores ophthalmic imaging data and associated annotations, segmentations, and metadata.

The architecture is centered around a core hierarchy that organizes imaging data:

**Project → Patient → Study → Series → ImageInstance**

This hierarchy represents the natural organization of medical imaging data:
- **Projects** group related patients and studies
- **Patients** represent individual subjects
- **Studies** represent patient visits (typically one per day)
- **Series** group images taken together during a study
- **ImageInstances** are individual images

Around this core hierarchy, the ORM provides:

- **Annotation System**: Manual annotations with metadata and data storage
- **Segmentation System**: Pixel-level segmentations for image analysis
- **Form System**: Structured form-based annotations
- **Tag System**: Flexible tagging of entities for organization
- **Task System**: Workflow management for annotation tasks
- **Attribute System**: Computed attributes and model outputs
- **Model System**: Support for AI/ML model outputs and segmentation

All of these systems integrate with the core hierarchy, allowing annotations, segmentations, and metadata to be attached at appropriate levels (Patient, Study, Series, or ImageInstance).

## Main ORM Relationships

The following hierarchical tree shows the complete structure of the ORM, including the core hierarchy and all related entities:

```
Project
├── Contact (optional, 1→N)
└── Patient (1→N, CASCADE)
    ├── Study (1→N, CASCADE)
    │   ├── Series (1→N, CASCADE)
    │   │   └── ImageInstance (1→N, CASCADE)
    │   │       ├── Annotation (N→1, via Creator, Feature, AnnotationType)
    │   │       │   └── AnnotationData (1→N, stores actual data)
    │   │       ├── Segmentation (N→1, via Creator, Feature)
    │   │       ├── ModelSegmentation (N→1, via Model)
    │   │       ├── FormAnnotation (N→1, via Creator, FormSchema)
    │   │       ├── AttributeValue (N→1, via AttributeDefinition, Model)
    │   │       ├── ImageInstanceTagLink (N→M, via Tag)
    │   │       ├── DeviceInstance (N→1)
    │   │       │   └── DeviceModel (N→1)
    │   │       ├── SourceInfo (N→1)
    │   │       ├── ModalityTable (N→1)
    │   │       ├── Scan (N→1, optional)
    │   │       └── SubTaskImageLink (N→M, links to SubTask)
    │   ├── FormAnnotation (N→1, via Creator, FormSchema)
    │   └── StudyTagLink (N→M, via Tag)
    ├── FormAnnotation (N→1, via Creator, FormSchema)
    └── Annotation (N→1, via Creator, Feature, AnnotationType)

Segmentation relates to:
├── Feature (N→1)
│   └── FeatureFeatureLink (parent-child hierarchy, N→M)
└── SubTask (N→1, optional)

ModelSegmentation relates to:
└── Model (N→1)
    ├── SegmentationModel (polymorphic, has Feature)
    └── AttributesModel (polymorphic)

Task System (independent workflow):
Task
├── TaskDefinition (N→1)
└── SubTask (1→N)
    ├── SubTaskImageLink (N→M, links to ImageInstance)
    ├── FormAnnotation (1→N)
    └── Segmentation (1→N)

Tag System (can tag multiple entity types):
Tag
├── StudyTagLink (N→M, via Study)
├── ImageInstanceTagLink (N→M, via ImageInstance)
├── AnnotationTagLink (N→M, via Annotation)
├── SegmentationTagLink (N→M, via Segmentation)
├── FormAnnotationTagLink (N→M, via FormAnnotation)
└── CreatorTagLink (N→M, via Creator, for starred tags)

Attribute System:
AttributeDefinition
├── AttributeValue (1→N)
│   ├── ImageInstance (N→1, optional)
│   ├── Segmentation (N→1, optional)
│   └── ModelSegmentation (N→1, optional)
└── AttributesModel (N→M, via AttributesModelOutput)

Creator (links to many entities):
Creator
├── Annotation (1→N)
├── FormAnnotation (1→N)
├── Segmentation (1→N)
├── Tag (1→N)
├── Task (1→N)
└── SubTask (1→N)
```

### Legend

- `├──` and `└──` indicate direct parent-child relationships in the tree structure
- `(1→N)` indicates one-to-many relationship (one parent, many children)
- `(N→M)` indicates many-to-many relationship (via link table)
- `(optional)` indicates nullable foreign key (relationship is optional)
- `(CASCADE)` indicates CASCADE delete behavior (deleting parent deletes children)
- `via X` indicates relationship goes through another entity or link table
- Indentation shows hierarchical structure

## Core Hierarchy

The central hierarchy of the ORM follows the DICOM-inspired structure common in medical imaging:

### Project → Patient → Study → Series → ImageInstance

#### Project ([project.py](project.py))

**Purpose**: Top-level container that groups patients and holds project metadata.

**Classes**:
- `Project`: Main project entity with name, description, external/internal flag, DOI, and contact information
- `Contact`: Contact person/institution associated with projects

**Key Relationships**:
- `Project` 1→N `Patient` (CASCADE delete: deleting a project deletes all patients)
- `Project` N→1 `Contact` (optional: projects can have an associated contact)

**Key Methods**:
- `Project.by_name(session, name)`: Find project by name
- `Project.make_dataframe()`: Get dataframe of all images in project
- `Project.get_patient_by_identifier(identifier)`: Find patient within project

#### Patient ([patient.py](patient.py))

**Purpose**: Represents an individual subject/patient in a project.

**Classes**:
- `Patient`: Patient entity with identifier, birth date, sex, and project association

**Key Relationships**:
- `Patient` N→1 `Project` (required: every patient belongs to a project)
- `Patient` 1→N `Study` (CASCADE delete: deleting a patient deletes all studies)
- `Patient` 1→N `Annotation` (annotations can be at patient level)
- `Patient` 1→N `FormAnnotation` (form annotations can be at patient level)

**Key Methods**:
- `Patient.by_project_and_identifier(session, project_id, identifier)`: Find patient by project and identifier
- `Patient.by_identifier(session, identifier)`: Find all patients with identifier (may be multiple across projects)
- `Patient.get_study_by_date(date)`: Get study for a specific date
- `Patient.get_images(where, include_inactive)`: Get all images for patient

#### Study ([study.py](study.py))

**Purpose**: Represents a patient visit/study session, typically grouping images taken on the same day.

**Classes**:
- `Study`: Study entity with date, description, round number, and patient association

**Key Relationships**:
- `Study` N→1 `Patient` (required: every study belongs to a patient, CASCADE delete)
- `Study` 1→N `Series` (CASCADE delete: deleting a study deletes all series)
- `Study` 1→N `Annotation` (annotations can be at study level)
- `Study` 1→N `FormAnnotation` (form annotations can be at study level)
- `Study` 1→N `StudyTagLink` (tags can be attached to studies)

**Key Methods**:
- `Study.by_patient_and_date(session, patient_id, study_date)`: Find study by patient and date
- `Study.age_years`: Property calculating patient age at study date
- `Study.get_images(where, include_inactive)`: Get all images for study

**Constraints**:
- Unique constraint on `(PatientID, StudyDate)` - one study per patient per day

#### Series ([series.py](series.py))

**Purpose**: Groups related images taken together during a study (e.g., all images from a single imaging session).

**Classes**:
- `Series`: Series entity with DICOM identifiers (SeriesInstanceUID, StudyInstanceUID) and series number

**Key Relationships**:
- `Series` N→1 `Study` (required: every series belongs to a study, CASCADE delete)
- `Series` 1→N `ImageInstance` (CASCADE delete: deleting a series deletes all images)
- `Series` 1→N `Annotation` (annotations can be at series level)

**Key Methods**:
- `Series.get_images(where)`: Get active images in series

**Constraints**:
- Unique constraint on `(StudyInstanceUID, SeriesInstanceUID)` - unique series identifiers

#### ImageInstance ([image_instance.py](image_instance.py))

**Purpose**: Represents an individual image with all its metadata, file paths, and relationships.

**Classes**:
- `ImageInstance`: Main image entity with extensive metadata (dimensions, modality, laterality, DICOM info, file paths, etc.)
- `DeviceModel`: Device manufacturer and model information
- `DeviceInstance`: Specific device instance with serial number
- `SourceInfo`: Source database/path information
- `ModalityTable`: Modality lookup table
- `Scan`: Scan mode/type information

**Key Relationships**:
- `ImageInstance` N→1 `Series` (required: every image belongs to a series, CASCADE delete)
- `ImageInstance` N→1 `DeviceInstance` (required: device that captured the image)
- `ImageInstance` N→1 `DeviceModel` (via DeviceInstance)
- `ImageInstance` N→1 `SourceInfo` (required: source information)
- `ImageInstance` N→1 `ModalityTable` (required: modality type)
- `ImageInstance` N→1 `Scan` (optional: scan mode)
- `ImageInstance` 1→N `Annotation` (many annotations per image)
- `ImageInstance` 1→N `Segmentation` (many segmentations per image)
- `ImageInstance` 1→N `ModelSegmentation` (model-generated segmentations)
- `ImageInstance` 1→N `FormAnnotation` (form annotations on images)
- `ImageInstance` 1→N `AttributeValue` (computed attributes)
- `ImageInstance` 1→N `ImageInstanceTagLink` (tags on images)
- `ImageInstance` 1→N `SubTaskImageLink` (links to workflow tasks)

**Key Properties**:
- `ImageInstance.path`: Path to image file
- `ImageInstance.Study`: Access parent study (via Series)
- `ImageInstance.Patient`: Access parent patient (via Series → Study)
- `ImageInstance.shape`: Image dimensions as (frames, rows, columns)
- `ImageInstance.is_3d` / `ImageInstance.is_2d`: Check if image is 3D or 2D

**Key Methods**:
- `ImageInstance.pixel_array`: Load image data as numpy array
- `ImageInstance.calc_data_hash()`: Calculate hash of image data
- `ImageInstance.calc_file_checksum()`: Calculate file checksum



## Class Reference by Domain

### Core Data Model

#### [project.py](project.py)

**Purpose**: Defines project-level entities that group patients and hold project metadata.

**Classes**:
- **`Project`**: Top-level container for organizing patients and studies
  - Primary key: `ProjectID`
  - Unique: `ProjectName`
  - Relationships: `Contact` (optional), `Patients` (1→N, CASCADE)
  - Key methods: `by_name()`, `make_dataframe()`, `get_patient_by_identifier()`

- **`Contact`**: Contact person or institution associated with projects
  - Primary key: `ContactID`
  - Unique constraint: `(Name, Email, Institute)`
  - Relationships: `Projects` (1→N), `Tasks` (1→N)

#### [patient.py](patient.py)

**Purpose**: Defines patient entities representing individual subjects.

**Classes**:
- **`Patient`**: Individual patient/subject in a project
  - Primary key: `PatientID`
  - Unique constraint: `(ProjectID, PatientIdentifier)` - patient identifiers are unique within a project
  - Relationships: `Project` (N→1, required), `Studies` (1→N, CASCADE), `Annotations` (1→N), `FormAnnotations` (1→N)
  - Key methods: `by_project_and_identifier()`, `by_identifier()`, `get_study_by_date()`, `get_images()`

#### [study.py](study.py)

**Purpose**: Defines study entities representing patient visits/imaging sessions.

**Classes**:
- **`Study`**: A visit/study session for a patient, typically grouping images from the same day
  - Primary key: `StudyID`
  - Unique constraint: `(PatientID, StudyDate)` - one study per patient per day
  - Relationships: `Patient` (N→1, required, CASCADE), `Series` (1→N, CASCADE), `Annotations` (1→N), `FormAnnotations` (1→N), `StudyTagLinks` (1→N)
  - Key methods: `by_patient_and_date()`, `get_images()`
  - Properties: `age_years` (calculated from study date and patient birth date)

#### [series.py](series.py)

**Purpose**: Defines series entities that group related images from a study.

**Classes**:
- **`Series`**: Groups related images taken together during a study
  - Primary key: `SeriesID`
  - Unique constraint: `(StudyInstanceUID, SeriesInstanceUID)` - DICOM identifiers
  - Relationships: `Study` (N→1, required, CASCADE), `ImageInstances` (1→N, CASCADE), `Annotations` (1→N)
  - Key methods: `get_images()`

#### [image_instance.py](image_instance.py)

**Purpose**: Defines image entities and related device/source metadata.

**Classes**:
- **`ImageInstance`**: Individual image with metadata, file paths, and relationships
  - Primary key: `ImageInstanceID`
  - Unique: `SOPInstanceUid` (DICOM identifier), `(SourceInfoID, DatasetIdentifier)`
  - Extensive metadata: dimensions, modality, laterality, DICOM fields, file paths, quality metrics
  - Relationships: `Series` (N→1, required, CASCADE), `DeviceInstance` (N→1), `SourceInfo` (N→1), `ModalityTable` (N→1), `Scan` (N→1, optional), plus many annotation/segmentation relationships
  - Key properties: `path`, `Study`, `Patient`, `shape`, `is_3d`, `is_2d`
  - Key methods: `pixel_array`, `calc_data_hash()`, `calc_file_checksum()`, `get_annotations_for_creator()`

- **`DeviceModel`**: Device manufacturer and model information
  - Primary key: `DeviceModelID`
  - Unique constraint: `(Manufacturer, ManufacturerModelName)`
  - Relationships: `DeviceInstances` (1→N)
  - Key methods: `by_manufacturer()`

- **`DeviceInstance`**: Specific device instance with serial number
  - Primary key: `DeviceInstanceID`
  - Unique constraint: `(DeviceModelID, Description)`
  - Relationships: `DeviceModel` (N→1), `ImageInstances` (1→N)

- **`SourceInfo`**: Source database/path information
  - Primary key: `SourceInfoID`
  - Unique: `SourceName`, `SourcePath`, `ThumbnailPath`
  - Relationships: `ImageInstances` (1→N)

- **`ModalityTable`**: Modality type lookup table
  - Primary key: `ModalityID`
  - Unique: `ModalityTag`
  - Relationships: `ImageInstances` (1→N)
  - Key methods: `by_tag()`

- **`Scan`**: Scan mode/type information
  - Primary key: `ScanID`
  - Unique: `ScanMode`
  - Relationships: `ImageInstances` (1→N, optional)
  - Key methods: `by_mode()`

### Annotation & Analysis

#### [annotation.py](annotation.py)

**Purpose**: Defines annotation system for manual annotations with metadata and data storage.

**Classes**:
- **`Annotation`**: Annotation metadata linking to patient/study/series/image, creator, feature, and type
  - Primary key: `AnnotationID`
  - Relationships: `Patient` (N→1, required), `Study` (N→1, optional), `Series` (N→1, optional), `ImageInstance` (N→1, optional, CASCADE), `Creator` (N→1, required), `Feature` (N→1, required), `AnnotationType` (N→1, required), `AnnotationReference` (self-referential, optional, for annotation hierarchies), `AnnotationData` (1→N)
  - Key methods: `create()` - factory method for creating annotations

- **`AnnotationData`**: Stores the actual annotation data (masks, images, etc.)
  - Composite primary key: `(AnnotationID, ScanNr)`
  - Stores data as: `ValueInt`, `ValueFloat`, `ValueBlob`, or file reference via `DatasetIdentifier`
  - Relationships: `Annotation` (N→1, required, CASCADE)
  - Key methods: `by_composite_id()`, `load_data()`, `get_mask()` - loads annotation data and converts to masks
  - Properties: `path`, `segmentation_mask`, `questionable_mask`

- **`AnnotationType`**: Defines types of annotations and their interpretation
  - Primary key: `AnnotationTypeID`
  - Unique constraint: `(AnnotationTypeName, Interpretation)`
  - Relationships: `Annotations` (1→N)

#### [form_annotation.py](form_annotation.py)

**Purpose**: Defines structured form-based annotation system.

**Classes**:
- **`FormSchema`**: Defines the structure/schema for form annotations
  - Primary key: `FormSchemaID`
  - Unique: `SchemaName`
  - Stores schema definition as JSON
  - Relationships: `FormAnnotations` (1→N)

- **`FormAnnotation`**: Structured form annotation with JSON data
  - Primary key: `FormAnnotationID`
  - Can attach to: `Patient` (required), `Study` (optional), `ImageInstance` (optional, CASCADE)
  - Relationships: `FormSchema` (N→1, required), `Patient` (N→1, required), `Study` (N→1, optional), `ImageInstance` (N→1, optional), `Creator` (N→1, required), `SubTask` (N→1, optional), `FormAnnotationReference` (self-referential, optional, for form hierarchies), `FormAnnotationTagLinks` (1→N)
  - Key methods: `by_schema_and_creator()`, `export_formannotations_by_schema()` - export to DataFrame
  - Properties: `flat_data` - flattened form data with metadata

#### [segmentation.py](segmentation.py)

**Purpose**: Defines segmentation system for pixel-level image analysis, features, and models.

**Classes**:
- **`SegmentationBase`** (abstract): Base class for segmentation entities with common functionality
  - Abstract base providing: zarr storage integration, data representation types, shape/dtype handling
  - Key properties: `shape`, `is_3d`, `is_2d`, `is_sparse`, `dtype`
  - Key methods: `write_data()`, `read_data()`, `write_empty()` - zarr storage operations

- **`Segmentation`**: Manual segmentation created by a creator for a specific feature
  - Primary key: `SegmentationID`
  - Inherits from `SegmentationBase`
  - Relationships: `ImageInstance` (N→1, required, CASCADE), `Creator` (N→1, required), `Feature` (N→1, required), `SubTask` (N→1, optional), `ReferenceSegmentation` (self-referential, optional), `SegmentationTagLinks` (1→N), `AttributeValues` (1→N)

- **`ModelSegmentation`**: Model-generated segmentation
  - Primary key: `ModelSegmentationID`
  - Inherits from `SegmentationBase`
  - Relationships: `ImageInstance` (N→1, required, CASCADE), `Model` (N→1, required), `AttributeValues` (1→N)
  - Properties: `groupname` - zarr group name based on model name and version

- **`Feature`**: Defines what is being segmented (e.g., "Vessel", "Optic Disc")
  - Primary key: `FeatureID`
  - Unique: `FeatureName`
  - Relationships: `Segmentations` (1→N), `SegmentationModels` (1→N), `FeatureAssociations` (parent side, 1→N), `ChildFeatureAssociations` (child side, 1→N)
  - Key methods: `from_list()` - create feature hierarchy from list
  - Properties: `has_segmentations`, `is_child`, `subfeatures_list`, `json`

- **`FeatureFeatureLink`**: Links features in parent-child relationships (composite features)
  - Composite primary key: `(ParentFeatureID, ChildFeatureID, FeatureIndex)`
  - Relationships: `Feature` (parent side), `Child` (child side)
  - Allows features to have sub-features (e.g., "Vessel" with sub-features "Artery" and "Vein")

- **`Model`**: Base class for AI/ML models (polymorphic)
  - Primary key: `ModelID`
  - Unique constraint: `(ModelName, Version)`
  - Polymorphic on `ModelType` (Segmentation or Attributes)
  - Relationships: `ProducedAttributeValues` (1→N)

- **`SegmentationModel`**: Model that produces segmentations
  - Primary key: `ModelID` (inherited from Model)
  - Polymorphic identity: `ModelKind.Segmentation`
  - Relationships: `Feature` (N→1, optional - the feature this model segments), `Segmentations` (1→N, via ModelSegmentation)

##### Rules and workflows for segmentations

The segmentations in Eyened ORM follow a few rules:

- All segmentations are attached to a single image instance
- All segmentations have shape (D, H, W)
- the Depth, Height, Width columns of the Segmentation object must always match the shape of the stored numpy array data and should not be updated
- Segmentations shape and parameteres defines how the annotation is matched to the image volume.
- After a segmentation is created it can only be replaced with an annotation of the same shape. This is intentional to encourage consistency.

By default segmentation.shape == image.shape. That is:
- Segmentation.Depth == ImageInstance.NrOfFrames or 1 
- Segmentation.Height == ImageInstance.Rows_y
- Segmentation.Width == ImageInstance.Columns_x
However, if ImageProjectionMatrix is provided, two dimensions may differ and SparseAxis must indicate the dimension that is not modified (0=Depth, 1=Height, 2=Width). If only a SparseAxis is provided, the dimension in that axis can differ.

SliceIndices is used to indicate which slices along SparseAxis have valid data (e.g. when annotating a subset of B-scans in an OCT volume).

Along SparseAxis, the segmentation shape must be equal to the image shape, or it must be 1 (this is used for 2D on 3D annotations not associated with a slice, e.g. enface-projection)


### examples of valid annotation shapes

**2D color fundus**
 - ImageInstance.shape: [1, 1632, 2464]
 - Segmentation.shape: [1, 1632, 2464]
 - SparseAxis: 0
 - ScanIndices: NULL
 - ImageProjectionMatrix: NULL

**2D color fundus, with transformation matrix**
 - ImageInstance.shape: [1, 1632, 2464]
 - Segmentation.shape: [1, 1024, 1024]
 - SparseAxis: 0
 - ScanIndices: NULL
 - ImageProjectionMatrix: [[0.6, 0, 100], [0, 0.6, 100], [0, 0, 1]]


**3D OCT, sparse B-scans**
 - ImageInstance.shape: [128, 885, 512]
 - Segmentation.shape: [128, 885, 512]
 - SparseAxis: 0
 - ScanIndices: [54, 62, 81]
 - ImageProjectionMatrix: NULL

 
**3D OCT, full volume**
 - image shape: [128, 885, 512]
 - Segmentation.shape: [128, 885, 512]
 - SparseAxis: 0
 - ScanIndices: NULL
 - ImageProjectionMatrix: NULL


**3D OCT, enface projection**
 - image shape: [128, 885, 512]
 - Segmentation.shape: [128, 1, 512]
 - SparseAxis: 1
 - ScanIndices: NULL
 - ImageProjectionMatrix: NULL

##### Reference segmentations

Segmentations can be linked to other segmentations via ReferenceSegmentationID. The referred and referring segmentations must have the same dimensions. To linked segmentations, make sure the parent is flushed first before inserting the child / referring segmentations:

```
# Create parent/reference segmentation
reference_segmentation = Segmentation(
    ImageInstanceID=image_instance.ImageInstanceID,
    CreatorID=creator.CreatorID,
    FeatureID=vessels_feature.FeatureID,
    Depth=1,
    Height=1024,
    Width=1024,
    SparseAxis=0,
    DataRepresentation=DataRepresentation.Binary,
    DataType=Datatype.R8UI,
)
session.add(reference_segmentation)
session.flush([reference_segmentation])  # assigns SegmentationID

# Create first child segmentation
artery_segmentation = Segmentation(
    ImageInstanceID=image_instance.ImageInstanceID,
    CreatorID=creator.CreatorID,
    FeatureID=artery_feature.FeatureID,
    Depth=1,
    Height=1024,
    Width=1024,
    SparseAxis=0,
    DataRepresentation=DataRepresentation.Binary,
    DataType=Datatype.R8UI,
    ReferenceSegmentationID=reference_segmentation.SegmentationID,
)

# Create second child segmentation
vein_segmentation = Segmentation(
    ImageInstanceID=image_instance.ImageInstanceID,
    CreatorID=creator.CreatorID,
    FeatureID=vein_feature.FeatureID,
    Depth=1,
    Height=1024,
    Width=1024,
    SparseAxis=0,
    DataRepresentation=DataRepresentation.Binary,
    DataType=Datatype.R8UI,
    ReferenceSegmentationID=reference_segmentation.SegmentationID,
)

session.add_all([artery_segmentation, vein_segmentation])
session.flush([artery_segmentation, vein_segmentation])

# optional: write masks once ImageInstance is attached
reference_segmentation.write_data(vessels_mask)
artery_segmentation.write_data(artery_mask)
vein_segmentation.write_data(vein_mask)

session.commit()
```

### Metadata & Organization

#### [tag.py](tag.py)

**Purpose**: Defines flexible tagging system for organizing entities.

**Classes**:
- **`Tag`**: Tag entity that can be applied to multiple entity types
  - Primary key: `TagID`
  - Unique constraint: `(TagName, TagType)` - tag names are unique within a type
  - `TagType` enum: Study, ImageInstance, Annotation, Segmentation, FormAnnotation
  - Relationships: `Creator` (N→1, required - who created the tag), `StudyTagLinks` (1→N), `ImageInstanceTagLinks` (1→N), `AnnotationTagLinks` (1→N), `SegmentationTagLinks` (1→N), `FormAnnotationTagLinks` (1→N), `CreatorTagLinks` (1→N, for starred tags)

- **`StudyTagLink`**: Links tags to studies
  - Composite primary key: `(TagID, StudyID)`
  - Relationships: `Tag` (N→1, CASCADE), `Study` (N→1, CASCADE), `Creator` (N→1 - who applied the tag)

- **`ImageInstanceTagLink`**: Links tags to image instances
  - Composite primary key: `(TagID, ImageInstanceID)`
  - Relationships: `Tag` (N→1, CASCADE), `ImageInstance` (N→1, CASCADE), `Creator` (N→1)

- **`AnnotationTagLink`**: Links tags to annotations
  - Composite primary key: `(TagID, AnnotationID)`
  - Relationships: `Tag` (N→1, CASCADE), `Annotation` (N→1, CASCADE), `Creator` (N→1)

- **`SegmentationTagLink`**: Links tags to segmentations
  - Composite primary key: `(TagID, SegmentationID)`
  - Relationships: `Tag` (N→1, CASCADE), `Segmentation` (N→1, CASCADE), `Creator` (N→1)

- **`FormAnnotationTagLink`**: Links tags to form annotations
  - Composite primary key: `(TagID, FormAnnotationID)`
  - Relationships: `Tag` (N→1, CASCADE), `FormAnnotation` (N→1, CASCADE), `Creator` (N→1)

- **`CreatorTagLink`**: Links creators to tags they've starred/favorited
  - Composite primary key: `(TagID, CreatorID)`
  - Relationships: `Tag` (N→1, CASCADE), `Creator` (N→1, CASCADE)

#### [attributes.py](attributes.py)

**Purpose**: Defines attribute system for computed attributes and model outputs.

**Classes**:
- **`AttributeDefinition`**: Defines what attribute is being measured
  - Primary key: `AttributeID`
  - Unique: `AttributeName`
  - `AttributeDataType` enum: String, Float, Int, JSON
  - Relationships: `AttributeValues` (1→N), `ProducingModels` (N→M, via AttributesModelOutput)

- **`AttributeValue`**: Stores a computed or manual attribute value for an entity
  - Primary key: `AttributeValueID`
  - Unique constraints: separate constraints for each entity type (ImageInstance, Segmentation, ModelSegmentation) with AttributeID and ModelID
  - Check constraint: exactly one of ImageInstanceID, SegmentationID, or ModelSegmentationID must be non-null
  - Can attach to: `ImageInstance` (optional), `Segmentation` (optional), `ModelSegmentation` (optional)
  - Relationships: `AttributeDefinition` (N→1, required), `ProducingModel` (N→1, optional), `ImageInstance` (N→1, optional, CASCADE), `Segmentation` (N→1, optional, CASCADE), `ModelSegmentation` (N→1, optional, CASCADE), `InputValues` (provenance tracking, N→M), `UsedByValues` (provenance tracking, N→M)
  - Stores value as: `ValueFloat`, `ValueInt`, `ValueText`, or `ValueJSON` depending on attribute type

- **`AttributesModel`**: Model that produces attribute values (polymorphic)
  - Primary key: `ModelID` (inherited from Model)
  - Polymorphic identity: `ModelKind.Attributes`
  - Relationships: `ModelInputs` (1→N), `OutputAttributes` (N→M, via AttributesModelOutput), `ProducedAttributeValues` (1→N)

- **`ModelInput`**: Defines what attributes a model requires as input
  - Primary key: `ModelInputID`
  - Unique constraint: `(ModelID, InputAttributeID)`
  - Relationships: `AttributesModel` (N→1, CASCADE), `InputAttribute` (N→1, CASCADE)

- **`AttributesModelOutput`**: Junction table declaring what attributes a model produces
  - Composite primary key: `(ModelID, AttributeID)`
  - Links: `AttributesModel` to `AttributeDefinition`

- **`AttributeValueInput`**: Tracks provenance - which attribute values were used to compute another
  - Composite primary key: `(OutputAttributeValueID, InputAttributeValueID)`
  - Relationships: `OutputValue` (N→1), `InputValue` (N→1)
  - Enables tracking computation chains

### Workflow

#### [task.py](task.py)

**Purpose**: Defines task system for managing annotation workflows.

**Classes**:
- **`TaskDefinition`**: Defines what type of task this is
  - Primary key: `TaskDefinitionID`
  - Unique: `TaskDefinitionName`
  - Stores task configuration as JSON
  - Relationships: `Tasks` (1→N)

- **`Task`**: Top-level task entity
  - Primary key: `TaskID`
  - Unique: `TaskName`
  - Relationships: `TaskDefinition` (N→1, required), `Creator` (N→1, optional), `Contact` (N→1, optional), `TaskState` (enum), `SubTasks` (1→N, CASCADE)
  - Key methods: `create_from_imagesets()` - factory method, `get_form_annotations()` - get all form annotations for task

- **`SubTask`**: Individual work item within a task
  - Primary key: `SubTaskID`
  - Relationships: `Task` (N→1, required, CASCADE), `Creator` (N→1, optional), `SubTaskState` (enum), `SubTaskImageLinks` (1→N, CASCADE), `FormAnnotations` (1→N), `Segmentations` (1→N)
  - Key methods: `create_from_image_ids()` - factory method

- **`SubTaskImageLink`**: Links subtasks to image instances (many-to-many)
  - Composite primary key: `(SubTaskID, ImageInstanceID)`
  - Relationships: `SubTask` (N→1, CASCADE), `ImageInstance` (N→1, CASCADE)
  - Allows a subtask to work on multiple images

### Supporting Classes

#### [creator.py](creator.py)

**Purpose**: Defines creator entities representing humans or AI models that create annotations, segmentations, etc.

**Classes**:
- **`Creator`**: Entity representing who created something (human annotator or AI model)
  - Primary key: `CreatorID`
  - Unique: `CreatorName`
  - Fields: `IsHuman` (boolean), `EmployeeIdentifier`, `Path`, `Version`, `Description`, `Role`
  - Authentication fields (private): `Password`, `PasswordHash`
  - Relationships: `Annotations` (1→N), `FormAnnotations` (1→N), `Segmentations` (1→N), `Tags` (1→N), `Tasks` (1→N), `SubTasks` (1→N), `StarredTags` (N→M, via CreatorTagLink)
  - Used throughout the system to track who created annotations, segmentations, tags, etc.

