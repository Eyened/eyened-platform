# run-models Command Implementation

## Overview

The `run-models` command serves as a **thin wrapper** around any `AttributesModel`, providing a standardized interface for connecting external inference models to the database. The implementation is **model-agnostic**—it doesn't care what the model actually does—and focuses primarily on managing the interaction between models and the database, particularly:

- **Checking existing values**: Automatically queries the database to determine which images already have results, enabling idempotent operation
- **Saving results**: Handles persistence of model outputs to the `AttributeValue` table with proper data type handling
- **Database entity management**: Creates or retrieves `AttributesModel` and `AttributeDefinition` entities as needed

Models can be defined externally to the platform and integrated by implementing a simple pipeline interface. Common processing steps (preprocessing, batch processing, postprocessing) are **optional** and can be implemented only if needed by the specific model.

### Supported Models (Examples)

The following models are currently implemented as examples:
- **cfi-roi**: CFI ROI detection - extracts CFI bounds from fundus images
- **cfi-keypoints**: CFI keypoints detection - detects fovea and disc edge locations
- **cfi-odfd**: Optic Disc to Fovea Distance estimation - calculates distance in pixels
- **cfi-quality**: Image quality assessment

## Architecture Overview

The implementation provides a **thin wrapper framework** that connects external models to the database:

- **Database-First**: Core functionality is database interaction—checking existing `AttributeValue` records and persisting new results
- **Model-Agnostic**: No constraints on what the model does; only requires results can be saved as attribute values
- **Optional Pipeline Stages**: Models can optionally implement preprocessing, batch processing, and postprocessing stages
- **Optional Infrastructure**: Provides parallel preprocessing, batch processing, and efficient commits when needed

## Key Implementation Choices

### Pipeline Architecture

The pipeline system provides an **optional** framework for models that need structured processing stages. Models can implement as many or as few stages as needed.

#### BaseInferencePipeline

The function `image_path → value` is broken up into **optional** pipeline stages that models can implement:

- `preprocess(image_path) -> S`: Optional preprocessing (default: pass-through) - transforms image path to preprocessed item
- `process_batch(prep_batch: List[S]) -> List[T]`: Optional batch processing (default: pass-through) - processes batch of preprocessed items to batch outputs
- `postprocess(prep_item: S, batch_output: T) -> value`: Optional postprocessing (default: pass-through) - transforms batch output to final result (stored in `AttributeValue`)

The pipeline flow: `image_path → S → T → value`, where **value will be stored in `AttributeValue`**. Models only implement the stages they need.

#### AttributeInferencePipeline

Extends `BaseInferencePipeline` with **core database integration**:

- **Database Entity Management**: Creates/retrieves `AttributesModel` and `AttributeDefinition` entities
- **Result Persistence**: Saves results via `AttributeValue.upsert()` with proper data type handling
- **Result Filtering**: `filter_image_ids()` queries database for existing `AttributeValue` records, enabling idempotent operation
- **Lazy Model Loading**: Optional `_load_models()` hook for model initialization

Subclasses define model metadata: `model_name`, `model_version`, `attribute_name`, `attribute_data_type`.

### Optional Infrastructure

The framework provides optional infrastructure for models that need it:

- **Multi-Process Preprocessing**: Parallel preprocessing using worker processes for I/O-bound tasks
- **Batch Processing**: Batch processing support for GPU-accelerated models
- **Error Handling**: Failed processing yields `None` results without crashing the pipeline

### Database Transaction Management

Results are committed in batches (`commit_interval`, default: 100) to balance performance and data safety, with a final commit ensuring all results are persisted.

### Result Filtering (Database Interaction)

The **core functionality** is checking existing values in the database:

- `filter_image_ids()` queries the `AttributeValue` table to check which images already have results
- By default, images with existing results are automatically skipped (idempotent operation)
- The `--overwrite` flag disables filtering to allow reprocessing all images

This database interaction is the **primary purpose** of the wrapper.

### Model-Agnostic Design

The framework is **agnostic of what the model actually does**. Models can be defined externally and integrated by:

1. Inheriting from `AttributeInferencePipeline`
2. Defining model metadata (name, version, attribute name, data type)
3. Optionally implementing pipeline stages as needed

The wrapper handles all database interaction automatically and doesn't care about the model's internal logic.

## Execution Flow

The command execution focuses on database interaction:

1. **Load Image IDs**: Reads image IDs from the specified file (one ID per line)
2. **Initialize Database**: Creates database session using environment configuration
3. **Model Selection**: If a specific model is provided, runs only that model; otherwise runs all models sequentially
4. **For Each Model**:
   - Instantiate the pipeline class
   - **Database Query**: Filter image IDs by querying for existing `AttributeValue` records (unless `--overwrite` is set)
   - Run inference via `pipeline.run(image_ids, commit_interval)` - model-specific logic happens here
   - **Database Persistence**: Results are automatically saved to `AttributeValue` table via `AttributeValue.upsert()`
   - Commit final results

## Pipeline Execution Details

The `process()` method orchestrates optional pipeline stages (`preprocess`, `process_batch`, `postprocess`), which models can implement as needed. The `run()` method wraps `process()` and handles **database persistence**—the core wrapper functionality:

- Iterates over `(image_id, result)` tuples
- Commits at specified intervals
- **Saves results via `_save_result()`**: Connects model outputs to the database via `AttributeValue.upsert()`
- Performs final commit

## Design Rationale

The implementation is intentionally a **thin wrapper** that focuses on database interaction rather than model logic:

- **Database-Centric**: Primary purpose is managing interaction between models and the database—checking existing values and persisting results
- **Model-Agnostic**: Models can be defined externally; the wrapper doesn't care about model internals, only that results can be saved as attribute values
- **Optional Infrastructure**: Pipeline stages (preprocessing, batch processing, postprocessing) are optional helpers that models can use as needed
- **Idempotency**: Enables safe re-runs by automatically skipping already-processed images

## Related Files

- [`model_processing.py`](model_processing.py) - Main command implementation (`run_models` function)
- [`../inference/attribute_inference.py`](../inference/attribute_inference.py) - `AttributeInferencePipeline` base class
- [`../inference/multi_process_inference.py`](../inference/multi_process_inference.py) - `MultiProcessInference` orchestrator and `BaseInferencePipeline`
- [`../inference/cfi_roi.py`](../inference/cfi_roi.py) - Example: simple preprocessing-only model
- [`../inference/cfi_keypoints.py`](../inference/cfi_keypoints.py) - Example: full pipeline with batch processing and ensemble models
- [`../inference/cfi_odfd.py`](../inference/cfi_odfd.py) - Example: regression model with coordinate transformation
- [`../inference/cfi_quality.py`](../inference/cfi_quality.py) - Example: quality assessment model
