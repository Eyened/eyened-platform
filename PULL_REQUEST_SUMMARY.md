# Pull Request Summary: eyened-platform

## Overview
This pull request includes updates to database schema, user authentication, segmentation storage (zarr), frotend updates and more.

## Major Database Schema Updates

### New Tables Added
- **`Segmentation`** - New table for segmentation data (will replace Annotation/AnnotationData):
  - Zarr array storage
  - Multiple data representations (Binary, DualBitMask, Probability, MultiLabel, MultiClass)
  - Multiple data types (R8, R8UI, R16UI, R32UI, R32F)
  - Image projection matrices and scan indices
- **`Model`** - New table for AI model metadata storage (to replace 'Creator')  
- **`ModelSegmentation`** - New table for model-generated segmentations
- **`CompositeFeature`** - New table for feature hierarchy management

### Main Database Schema Modifications 
- **`ImageInstance`** made `DeviceInstanceID` non-nullable, dropped `ThumbnailIdentifier`
- **`Creator`** - Renamed `MSN` to `EmployeeIdentifier`, added `PasswordHash` field
- **`Feature`** - Dropped `Modality` column
- **`Project`** - Added `DOI` field
- **`Study`** - Added `StudyDate` index
- **`SubTask`** - Added `Comments` field
- **`SubTaskImageLink`** - Dropped `SubTaskImageLinkID` column
- **`TaskDefinition`** - Added `TaskConfig` JSON field

For all changes check `orm/migrations/alembic/versions/2025_07_25-segmentation_update.py`

## ORM changes
- Moved to SQLModel, for more concise model definition, pydantic typing, and integration with FastAPI
- Refactored database connection: now using EyenedSession with config rather than setting properties on Base on initialization 

## Server Changes
- Added segmentation router to main API 
- Improved password security with Argon2 hashing

## Client Features
- Improved segmentation data structures:
    - Flexible Multiclass and Multilabel types
    - Apply masking to any segmentation (previously AnnotationType MaskedSegmentation)
    - Choose between Questionable/Binary/Probability masks
    - convert between data types (e.g. Probability to Binary)
- Improved user interface (subtask management, database object creation routes)

## Client architecture changes
- Moving towards svelte5 runes
- Data model rewritten for cleaner interaction between reactive objects and server API
- More uniform handling of WebGL textures in segmentation / images
- Cleaner and more consistent implementation of gpu/cpu syncing for segmentations


## CLI Commands
- `eorm database-mirror-test` - replaces `eorm test`
- `eorm database-mirror-full` - replaces `eorm full`
- `eorm zarr-tree` - Display zarr store structure
- `eorm defragment-zarr` - Defragment zarr store for better performance

## Testing and Development

### Latest Migration: `2025_07_25-segmentation_update.py`
- **Revision ID**: `9b7fb6c7ead4`
- **Previous Revision**: `832ed384515f`
- **Date**: 2025-07-25 18:29:58.899555

### Breaking Changes
- Database schema changes require migration
- Some API endpoints may have updated response formats
- Updated database session management (ORM)

## Deployment Notes

1. **Database Migration Required**: 
- Apply the latest alembic migration before deployment.
- Run a script to transfer Annotation/AnnotationData to Segmentation
2. **Authentication**: New password hashes are created when users log-in. Old system still supported

---

*Generated on: $(date)*
*Repository: eyened-platform*
*Branch: [Current Branch]* 