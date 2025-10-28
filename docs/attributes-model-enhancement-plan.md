# Extend Attributes System with Unified Attribute Values

## Overview

Create a unified attribute system where attribute definitions are reusable across models, and a single `AttributeValue` table stores values for both images and segmentations. Includes full provenance tracking to know exactly which inputs produced which outputs.

## Core Changes

### 1. Rename and make Attribute table globally reusable

**File**: `orm/eyened_orm/attributes.py`

Rename `Attribute` → `AttributeDefinition`:

- Remove `ModelID` foreign key
- Make `AttributeName` globally unique
- Remove Model relationship

### 2. Replace ImageAttribute and create unified AttributeValue table

**File**: `orm/eyened_orm/attributes.py`

Replace `ImageAttribute` with new `AttributeValue` table:

- `AttributeValueID` INT PK
- `AttributeID` INT FK → AttributeDefinition.AttributeID
- `ModelID` INT FK → Model.ModelID (which model produced this)
- Nullable entity FKs (exactly one must be set):
  - `ImageInstanceID` INT FK → ImageInstance.ImageInstanceID
  - `SegmentationID` INT FK → Segmentation.SegmentationID
  - `ModelSegmentationID` INT FK → ModelSegmentation.ModelSegmentationID
- Value fields: `ValueFloat`, `ValueInt`, `ValueText`, `ValueJSON`
- Check constraint: exactly one entity FK must be non-null
- Unique constraint: (ImageInstanceID, SegmentationID, ModelSegmentationID, AttributeID, ModelID)

### 3. Create AttributesModelOutput junction table

**File**: `orm/eyened_orm/attributes.py`

Declares which attributes a model produces:

- `ModelID` INT FK → AttributesModel.ModelID, PK
- `AttributeID` INT FK → AttributeDefinition.AttributeID, PK

### 4. Create ModelInput table

**File**: `orm/eyened_orm/attributes.py`

Declares attribute dependencies:

- `ModelInputID` INT PK
- `ModelID` INT FK → AttributesModel.ModelID
- `InputAttributeID` INT FK → AttributeDefinition.AttributeID
- `InputName` VARCHAR(255) - human-readable label
- Unique constraint on (ModelID, InputAttributeID)

### 5. Create AttributeValueInput lineage table

**File**: `orm/eyened_orm/attributes.py`

Unified provenance tracking (AttributeValue → AttributeValue dependencies):

- `OutputAttributeValueID` INT FK → AttributeValue.AttributeValueID, PK
- `InputAttributeValueID` INT FK → AttributeValue.AttributeValueID, PK

This single table handles all lineage cases:

- ImageAttribute → ImageAttribute (e.g., resolution estimate using multiple image features)
- SegmentationAttribute → ImageAttribute (e.g., grid area using fovea coords)
- SegmentationAttribute → SegmentationAttribute (e.g., combining vessel features)

### 6. Update relationships

**Files**: `orm/eyened_orm/attributes.py`, `orm/eyened_orm/segmentation.py`, `orm/eyened_orm/image_instance.py`

Add relationships:

- `AttributesModel.ModelInputs` → ModelInput
- `AttributesModel.OutputAttributes` → AttributeDefinition (via AttributesModelOutput)
- `AttributeDefinition.AttributeValues` → AttributeValue
- `AttributeValue.InputValues` → AttributeValue (self-referential via AttributeValueInput)
- `AttributeValue.UsedByValues` → AttributeValue (reverse relationship)
- `ImageInstance.AttributeValues` → AttributeValue
- `Segmentation.AttributeValues` → AttributeValue
- `ModelSegmentation.AttributeValues` → AttributeValue
- `Model.ProducedAttributeValues` → AttributeValue

### 7. Create migration

**File**: `orm/migrations/alembic/versions/2025_10_22-unified_attribute_values.py`

Migration steps:

- Rename `Attributes` table to `AttributeDefinition`
- Create `AttributesModelOutput` table
- Migrate existing `Attribute.ModelID` data to `AttributesModelOutput`
- Drop `ModelID` column from `AttributeDefinition`
- Rename `ImageAttributes` to `AttributeValue`
- Add nullable `SegmentationID` and `ModelSegmentationID` columns
- Add `ModelID` column to `AttributeValue`
- Update unique constraints and indexes
- Create `ModelInput` table
- Create `AttributeValueInput` table
- Add check constraint for entity FKs

## Standard Application Attributes

Define common attributes once for reuse:

```python
# Image-level attributes
AttributeDefinition(AttributeName="fovea_x", AttributeDataType=AttributeDataType.Float)
AttributeDefinition(AttributeName="fovea_y", AttributeDataType=AttributeDataType.Float)
AttributeDefinition(AttributeName="cf_quality", AttributeDataType=AttributeDataType.Float)
AttributeDefinition(AttributeName="cf_roi", AttributeDataType=AttributeDataType.JSON)
AttributeDefinition(AttributeName="estimated_image_res_mm_per_pix", AttributeDataType=AttributeDataType.Float)

# Segmentation-level attributes
AttributeDefinition(AttributeName="vessel_tortuosity", AttributeDataType=AttributeDataType.Float)
AttributeDefinition(AttributeName="crae", AttributeDataType=AttributeDataType.Float)
AttributeDefinition(AttributeName="vascular_density_pct", AttributeDataType=AttributeDataType.Float)
AttributeDefinition(AttributeName="etdrs_grid_area_mm2", AttributeDataType=AttributeDataType.Float)
```

## Usage Examples

### Example 1: Fovea Detection (Image → Image Attributes)

```python
# Get reusable attribute definitions
fovea_x = AttributeDefinition.by_name(session, "fovea_x")
fovea_y = AttributeDefinition.by_name(session, "fovea_y")

# Create fovea detection model
fovea_model = AttributesModel(ModelName="FoveaDetector", Version="1.0")
session.add(fovea_model)
session.flush()

# Declare outputs (design-time schema)
session.add_all([
    AttributesModelOutput(ModelID=fovea_model.ModelID, AttributeID=fovea_x.AttributeID),
    AttributesModelOutput(ModelID=fovea_model.ModelID, AttributeID=fovea_y.AttributeID)
])

# Run model and store results (runtime values)
session.add_all([
    AttributeValue(ImageInstanceID=img.ImageInstanceID, AttributeID=fovea_x.AttributeID,
                   ModelID=fovea_model.ModelID, ValueFloat=512.3),
    AttributeValue(ImageInstanceID=img.ImageInstanceID, AttributeID=fovea_y.AttributeID,
                   ModelID=fovea_model.ModelID, ValueFloat=384.7)
])
```

### Example 2: VascX Features (Segmentation → Segmentation Attributes)

```python
# VascX produces vessel segmentation
vascx_model = SegmentationModel(ModelName="VascX", Version="2.0", FeatureID=vessels_feature.FeatureID)
vessel_seg = ModelSegmentation(ModelID=vascx_model.ModelID, ImageInstanceID=img.ImageInstanceID, ...)

# VascXFeatures analyzes segmentation
vascx_features = AttributesModel(ModelName="VascXFeatures", Version="1.0")

# Declare outputs
tortuosity = AttributeDefinition.by_name(session, "vessel_tortuosity")
crae = AttributeDefinition.by_name(session, "crae")
density = AttributeDefinition.by_name(session, "vascular_density_pct")

session.add_all([
    AttributesModelOutput(ModelID=vascx_features.ModelID, AttributeID=tortuosity.AttributeID),
    AttributesModelOutput(ModelID=vascx_features.ModelID, AttributeID=crae.AttributeID),
    AttributesModelOutput(ModelID=vascx_features.ModelID, AttributeID=density.AttributeID)
])

# Store segmentation attributes (note: same AttributeValue table, different FK)
session.add_all([
    AttributeValue(ModelSegmentationID=vessel_seg.ModelSegmentationID,
                   AttributeID=tortuosity.AttributeID, ModelID=vascx_features.ModelID,
                   ValueFloat=1.23),
    AttributeValue(ModelSegmentationID=vessel_seg.ModelSegmentationID,
                   AttributeID=crae.AttributeID, ModelID=vascx_features.ModelID,
                   ValueFloat=145.6),
    AttributeValue(ModelSegmentationID=vessel_seg.ModelSegmentationID,
                   AttributeID=density.AttributeID, ModelID=vascx_features.ModelID,
                   ValueFloat=42.3)
])
```

### Example 3: ETDRS Grid Area with Full Provenance

```python
# Get attribute definitions
fovea_x_def = AttributeDefinition.by_name(session, "fovea_x")
fovea_y_def = AttributeDefinition.by_name(session, "fovea_y")
resolution_def = AttributeDefinition.by_name(session, "estimated_image_res_mm_per_pix")
grid_area_def = AttributeDefinition.by_name(session, "etdrs_grid_area_mm2")

# Create ETDRS calculator
etdrs_area_model = AttributesModel(ModelName="ETDRSGridAreaCalculator", Version="1.0")

# Declare inputs (design-time dependencies)
session.add_all([
    ModelInput(ModelID=etdrs_area_model.ModelID, InputAttributeID=fovea_x_def.AttributeID, InputName="fovea_x"),
    ModelInput(ModelID=etdrs_area_model.ModelID, InputAttributeID=fovea_y_def.AttributeID, InputName="fovea_y"),
    ModelInput(ModelID=etdrs_area_model.ModelID, InputAttributeID=resolution_def.AttributeID, InputName="resolution")
])

# Declare output
session.add(AttributesModelOutput(ModelID=etdrs_area_model.ModelID, AttributeID=grid_area_def.AttributeID))

# Get input values (runtime - query specific model versions)
fovea_x_val = session.query(AttributeValue).filter_by(
    ImageInstanceID=img.ImageInstanceID, AttributeID=fovea_x_def.AttributeID,
    ModelID=fovea_model.ModelID
).first()

fovea_y_val = session.query(AttributeValue).filter_by(
    ImageInstanceID=img.ImageInstanceID, AttributeID=fovea_y_def.AttributeID,
    ModelID=fovea_model.ModelID
).first()

resolution_val = session.query(AttributeValue).filter_by(
    ImageInstanceID=img.ImageInstanceID, AttributeID=resolution_def.AttributeID,
    ModelID=resolution_model.ModelID
).first()

# Run calculation on drusen segmentation
drusen_seg = ModelSegmentation.query.filter_by(...).first()
area_value = calculate_etdrs_area(drusen_seg, fovea_x_val.ValueFloat,
                                   fovea_y_val.ValueFloat, resolution_val.ValueFloat)

# Store result (segmentation attribute)
grid_area_val = AttributeValue(
    ModelSegmentationID=drusen_seg.ModelSegmentationID,
    AttributeID=grid_area_def.AttributeID,
    ModelID=etdrs_area_model.ModelID,
    ValueFloat=area_value
)
session.add(grid_area_val)
session.flush()

# Track provenance - record which inputs were used
session.add_all([
    AttributeValueInput(OutputAttributeValueID=grid_area_val.AttributeValueID,
                       InputAttributeValueID=fovea_x_val.AttributeValueID),
    AttributeValueInput(OutputAttributeValueID=grid_area_val.AttributeValueID,
                       InputAttributeValueID=fovea_y_val.AttributeValueID),
    AttributeValueInput(OutputAttributeValueID=grid_area_val.AttributeValueID,
                       InputAttributeValueID=resolution_val.AttributeValueID)
])

# Later, trace provenance:
# grid_area_val.InputValues → [fovea_x_val, fovea_y_val, resolution_val]
# Know exactly which model versions produced which values
```

## Database Schema Overview

### Modified Tables

**AttributeDefinition** (renamed from Attributes, removed ModelID)

```
AttributeID          INT           PK
AttributeName        VARCHAR(255)  UNIQUE
AttributeDataType    ENUM          (String, Float, Int, JSON)
```

**AttributeValue** (renamed/extended from ImageAttributes - unified storage)

```
AttributeValueID       INT           PK
AttributeID            INT           FK → AttributeDefinition.AttributeID
ModelID                INT           FK → Model.ModelID
ImageInstanceID        INT           FK → ImageInstance.ImageInstanceID (nullable)
SegmentationID         INT           FK → Segmentation.SegmentationID (nullable)
ModelSegmentationID    INT           FK → ModelSegmentation.ModelSegmentationID (nullable)
ValueFloat             FLOAT         nullable
ValueInt               INT           nullable
ValueText              VARCHAR(255)  nullable
ValueJSON              JSON          nullable
UNIQUE (ImageInstanceID, SegmentationID, ModelSegmentationID, AttributeID, ModelID)
CHECK (exactly one of ImageInstanceID, SegmentationID, ModelSegmentationID is non-null)
```

### New Tables

**AttributesModelOutput** (declares model output schema)

```
ModelID              INT    FK → AttributesModel.ModelID, PK
AttributeID          INT    FK → AttributeDefinition.AttributeID, PK
```

**ModelInput** (declares model input dependencies)

```
ModelInputID         INT           PK
ModelID              INT           FK → AttributesModel.ModelID
InputAttributeID     INT           FK → AttributeDefinition.AttributeID
InputName            VARCHAR(255)
UNIQUE (ModelID, InputAttributeID)
```

**AttributeValueInput** (provenance tracking - unified for all types)

```
OutputAttributeValueID    INT    FK → AttributeValue.AttributeValueID, PK
InputAttributeValueID     INT    FK → AttributeValue.AttributeValueID, PK
```

## Files to Modify

- `orm/eyened_orm/attributes.py` - Core schema changes (rename Attribute, create AttributeValue, add junction tables)
- `orm/eyened_orm/segmentation.py` - Add AttributeValues relationship
- `orm/eyened_orm/image_instance.py` - Update AttributeValues relationship
- New migration file: `orm/migrations/alembic/versions/2025_10_22-unified_attribute_values.py`

## Implementation Todos

- [ ] Rename Attribute to AttributeDefinition, remove ModelID FK and relationship
- [ ] Create AttributeValue table with entity FKs (ImageInstance, Segmentation, ModelSegmentation) and check constraint
- [ ] Create AttributesModelOutput junction table
- [ ] Create ModelInput table for dependency declarations
- [ ] Create AttributeValueInput table for lineage tracking
- [ ] Add all necessary ORM relationships across files
- [ ] Generate Alembic migration to transform schema and migrate data

