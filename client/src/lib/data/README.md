# Data Layer - Usage Guide

A minimal reactive data management layer using plain objects and SvelteMaps.

## File Structure

```
data/
├── stores.svelte.ts   # ReactiveMap stores + ingest functions
├── helpers.ts         # CRUD helper functions  
├── api.ts             # API fetch functions
└── index.ts           # Re-exports
```

## Implementation Overview

### ReactiveMap

The data layer extends Svelte's `SvelteMap` with a custom `ReactiveMap` class that adds array-like methods:

```typescript
class ReactiveMap<K, V> extends SvelteMap<K, V> {
  filter(predicate: (value: V, key: K) => boolean): V[]
  map<U>(callback: (value: V, key: K) => U): U[]
  find(predicate: (value: V, key: K) => boolean): V | undefined
  some(predicate: (value: V, key: K) => boolean): boolean
  every(predicate: (value: V, key: K) => boolean): boolean
  reduce<U>(callback: (acc: U, value: V, key: K) => U, initial: U): U
  forEach(callback: (value: V, key: K) => void): void
}
```

### Stores

All data is stored in global `ReactiveMap` instances keyed by ID:

```typescript
// Primary stores
export const instances = new ReactiveMap<number, InstanceGET>()
export const instanceMetas = new ReactiveMap<number, InstanceMeta>()  // Lightweight references
export const studies = new ReactiveMap<number, StudyGET>()
export const tags = new ReactiveMap<number, TagGET>()
export const features = new ReactiveMap<number, FeatureGET>()
export const formSchemas = new ReactiveMap<number, FormSchemaGET>()
export const segmentations = new ReactiveMap<number, SegmentationGET>()
export const modelSegmentations = new ReactiveMap<number, ModelSegmentationGET>()
export const formAnnotations = new ReactiveMap<number, FormAnnotationGET>()
export const tasks = new ReactiveMap<number, TaskGET>()
export const subtasks = new ReactiveMap<number, SubTaskGET | SubTaskWithImagesGET>()

// Secondary indexes for name-based lookups
export const formSchemasByName = new ReactiveMap<string, FormSchemaGET>()
export const featuresByName = new ReactiveMap<string, FeatureGET>()
export const tagsByName = new ReactiveMap<string, TagGET>()
```

## Data Types and Relationships

### InstanceGET vs InstanceMeta

**InstanceGET** - Full instance object with all properties:
- Contains: `sop_instance_uid`, `rows`, `columns`, `study: StudyMeta`, `series: SeriesMeta`
- Optional embedded data: `segmentations?`, `form_annotations?`, `model_segmentations?` (requires `with_*` flags)
- Full metadata: `project: ProjectMeta`, `patient: PatientMeta`, `device: DeviceMeta`, `scan: ScanMeta`
- Attributes: `attributes: Dict[str, Dict[str, Any]]`

**InstanceMeta** - Lightweight reference with minimal fields:
- Contains only: `id`, `thumbnail_path`, `modality`, `dicom_modality`, `etdrs_field`, `laterality`, `anatomic_region`, `device: DeviceMeta`, `tags: TagMeta[]`
- Used in search responses when full data isn't needed

**Example:**
```typescript
// From /instances/search - returns InstanceGET[]
const instance = instances.get(123)!;
console.log(instance.sop_instance_uid);  // ✅ Available
console.log(instance.rows);              // ✅ Available

// From /studies/search - returns InstanceMeta[]
const meta = instanceMetas.get(123)!;
console.log(meta.sop_instance_uid);      // ❌ Not available
console.log(meta.modality);              // ✅ Available
```

### StudyGET with Embedded Series

**StudyGET** contains embedded `series?: SeriesGET[]` (full objects, not just IDs):

```typescript
type StudyGET = {
  id: number;
  description?: string | null;
  date: string;
  age?: number | null;
  project: ProjectMeta;
  patient: PatientMeta;
  series?: SeriesGET[] | null;  // Full SeriesGET objects!
  tags: TagMeta[];
}
```

**SeriesGET** contains `instance_ids?: number[]` (references to instances):

```typescript
type SeriesGET = {
  id: number;
  laterality?: 'L' | 'R' | null;
  series_number?: number | null;
  series_instance_uid: string;
  instance_ids?: number[];  // References to instances
}
```

### Meta Types

Meta types are lightweight references containing only essential fields:

- **StudyMeta**: `{ id: number, date: string }`
- **SeriesMeta**: `{ id: number }`
- **PatientMeta**: `{ id: number, identifier: string, birth_date?: string | null }`
- **ProjectMeta**: `{ id: number, name: string }`
- **TagMeta**: `{ id: number, name: string, tagger: CreatorMeta, date: string, comment?: string | null }`
- **DeviceMeta**: `{ manufacturer: string, model: string }`
- **ScanMeta**: `{ mode: string }`

### Relationship Pattern

Relationships are traversed via Meta references:

```typescript
// InstanceGET has study: StudyMeta (just ID + date)
const instance = instances.get(123)!;
const studyId = instance.study.id;  // Get ID from Meta

// Look up full StudyGET from stores
const study = studies.get(studyId);  // May be undefined!

// StudyGET has embedded series (full objects)
const series = study?.series;  // SeriesGET[] | null | undefined

// SeriesGET has instance_ids (array of IDs)
const instanceIds = series?.[0]?.instance_ids ?? [];
const instanceRefs = instanceIds.map(id => instanceMetas.get(id));
```

## Usage Examples

### Fetching and Ingesting Data

**Example from `routes/tasks/+page.svelte`:**

```svelte
<script lang="ts">
  import { fetchTasks } from "$lib/data/api";
  
  const loading = fetchTasks();
</script>

{#await loading}
  <p>Loading tasks...</p>
{:then tasks}
  <TasksTable rows={tasks} />
{/await}
```

The `fetchTasks()` function automatically ingests data into stores:

```typescript
export async function fetchTasks(): Promise<TaskGET[]> {
  const res = await api.GET('/task', {});
  const data = (res.data ?? []) as TaskGET[];
  ingestTasks(data);  // Auto-ingests into tasks store
  return data;
}
```

### Accessing Study Series

**Example from `lib/browser/Eye.svelte`:**

```typescript
// StudyGET has embedded series
const allInstanceIds = study.series?.flatMap((series) => series.instance_ids ?? []) ?? [];

// Look up instance metas from store
const allInstances = allInstanceIds.map((id) => instanceMetas.get(id));

// Filter by laterality
const eyeInstanceIds = allInstances
  .filter((instance) => instance?.laterality == laterality)
  .map((instance) => instance!.id);
```

### Fetching Instance with Optional Data

**Example from `api.ts`:**

```typescript
export async function fetchInstance(id: number, options?: {
  with_segmentations?: boolean;
  with_form_annotations?: boolean;
  with_model_segmentations?: boolean;
  with_tag_metadata?: boolean;
}) {
  const res = await api.GET('/instances/{instance_id}', {
    params: { 
      path: { instance_id: id },
      query: { 
        with_tag_metadata: true,
        ...options
      }
    }
  });
  
  if (res.data) {
    const instance = res.data as InstanceGET;
    
    // Ingest the instance
    ingestInstances([instance]);
    
    // Ingest embedded data if present
    if (instance.form_annotations) {
      ingestFormAnnotations(instance.form_annotations);
    }
    if (instance.segmentations) {
      ingestSegmentations(instance.segmentations);
    }
    if (instance.model_segmentations) {
      ingestModelSegmentations(instance.model_segmentations);
    }
  }
  
  return res.data;
}
```

### Tag Operations

**Example from `helpers.ts`:**

```typescript
// Tag an instance
export async function tagInstance(instance: InstanceGET | InstanceMeta, tagId: number, comment?: string) {
  const { data } = await api.POST('/instances/{instance_id}/tags', {
    params: { path: { instance_id: instance.id } },
    body: { tag_id: tagId, comment }
  });
  
  // Update both stores when present
  if (instanceMetas.has(instance.id)) {
    const meta = instanceMetas.get(instance.id)!;
    instanceMetas.set(instance.id, {
      ...meta,
      tags: [...meta.tags, data]
    });
  }
  if (instances.has(instance.id)) {
    const inst = instances.get(instance.id)!;
    instances.set(instance.id, {
      ...inst,
      tags: [...inst.tags, data]
    });
  }
}
```

### Subtask Operations

**Example from `routes/tasks/[taskid]/grade/[setid]/+page.svelte`:**

```typescript
const loadPromise = (async () => {
  const [task, subTask] = await Promise.all([
    fetchTask(Number(taskid)),
    fetchSubTaskByIndex(Number(taskid), Number(subTaskIndex), { with_images: true }),
  ]);
  
  if (!subTask) throw new Error("Subtask not found");
  if (!("images" in subTask)) throw new Error("Subtask missing images; ensure with_images=true");
  
  const instanceIDs = subTask.images.map(img => img.id);
  return { task, subTask, instanceIDs };
})();
```

### Reactive Usage in Components

**Example from `lib/tasks/TasksTable.svelte`:**

```svelte
<script lang="ts">
  import { tasks } from "$lib/data";
  
  let { rows }: { rows: TaskGET[] } = $props();
  
  // Direct access to plain objects
  const columns: ColumnDef<TaskGET>[] = [
    {
      accessorKey: "name",
      header: "Task",
      cell: ({ row }) => {
        const r = row.original as TaskGET;
        const url = `/tasks/${r.id}${typeof window !== "undefined" ? window.location.search : ""}`;
        return renderComponent(TaskNameCell, { task: r, url });
      },
    },
    {
      accessorKey: "task_state",
      header: "State",
      cell: ({ row }) => row.original.task_state ?? "-",
    },
  ];
</script>
```

## Edge Cases and Gotchas

### Ingest Function Validation

**`ingestInstances()` vs `ingestInstanceMetas()`:**

```typescript
export function ingestInstances(instancesData: InstanceGET[]) {
  for (const inst of instancesData) {
    // Validation: Only ingest full InstanceGET objects
    if (!('sop_instance_uid' in inst) || !('rows' in inst)) {
      console.error('ingestInstances() expects InstanceGET, got InstanceMeta. Use ingestInstanceMetas() instead:', inst);
      continue;
    }
    instances.set(inst.id, inst);
  }
}

export function ingestInstanceMetas(metasData: InstanceMeta[]) {
  for (const meta of metasData) {
    instanceMetas.set(meta.id, meta);
  }
}
```

**Important:** Always use the correct ingest function. Using `ingestInstances()` with `InstanceMeta[]` will log errors and skip entries.

### Search Response Types

**`/instances/search`** returns:
- `instances: InstanceGET[]` - Full objects
- `studies: StudyGET[]` - With embedded series

**`/studies/search`** returns:
- `studies: StudyGET[]` - With embedded series
- `instances: InstanceMeta[]` - Lightweight references (not full objects!)

```typescript
// From searchInstances()
const result = await searchInstances({ conditions: [...] });
result.instances.forEach(inst => {
  // inst is InstanceGET - full object
  console.log(inst.sop_instance_uid);  // ✅ Available
});

// From searchStudies()
const result = await searchStudies({ conditions: [...] });
result.instances.forEach(meta => {
  // meta is InstanceMeta - lightweight
  console.log(meta.sop_instance_uid);  // ❌ Not available
  console.log(meta.modality);          // ✅ Available
});
```

### Missing Data

**Always check for `undefined` when looking up objects:**

```typescript
const instance = instances.get(123);
if (!instance) {
  // Instance not in store - may need to fetch it
  await fetchInstance(123);
}

const study = studies.get(instance?.study.id);
if (!study) {
  // Study not in store - may need to fetch it
  await fetchStudy(instance.study.id);
}
```

**In Svelte components, use `$derived` with optional chaining:**

```svelte
<script lang="ts">
  import { instances, studies } from "$lib/data";
  
  const instanceId = 123;
  const instance = $derived(instances.get(instanceId));
  const study = $derived(instance ? studies.get(instance.study.id) : undefined);
  const patient = $derived(study?.patient);
</script>

{instance?.modality}
{study?.description}
{patient?.identifier}
```

### Tag Updates

**Tag operations update both `instances` and `instanceMetas` stores when present:**

```typescript
export async function untagInstance(instance: InstanceGET | InstanceMeta, tagId: number) {
  await api.DELETE('/instances/{instance_id}/tags/{tag_id}', {
    params: { path: { instance_id: instance.id, tag_id: tagId } }
  });
  
  // Update both stores when present
  if (instanceMetas.has(instance.id)) {
    const meta = instanceMetas.get(instance.id)!;
    instanceMetas.set(instance.id, {
      ...meta,
      tags: meta.tags.filter(t => t.id !== tagId)
    });
  }
  if (instances.has(instance.id)) {
    const inst = instances.get(instance.id)!;
    instances.set(instance.id, {
      ...inst,
      tags: inst.tags.filter(t => t.id !== tagId)
    });
  }
}
```

### Optional Embedded Data

**Embedded data requires `with_*` flags and may be `null` or `undefined`:**

```typescript
// Fetch instance with segmentations
const instance = await fetchInstance(123, { with_segmentations: true });

// Check if data is present
if (instance.segmentations) {
  // Ingest segmentations into store
  ingestSegmentations(instance.segmentations);
}

// Access from store
const segs = segmentations.filter(s => s.image_instance_id === instance.id);
```

### SubTask Type Union

**`subtasks` store contains union type `SubTaskGET | SubTaskWithImagesGET`:**

```typescript
export const subtasks = new ReactiveMap<number, SubTaskGET | SubTaskWithImagesGET>();

// Check type at runtime
const subtask = subtasks.get(123);
if (subtask && 'images' in subtask) {
  // subtask is SubTaskWithImagesGET
  const instanceIds = subtask.images.map(img => img.id);
} else {
  // subtask is SubTaskGET - no images
  // Need to fetch with with_images: true
  const fullSubtask = await fetchSubTaskByIndex(taskId, subtask.index, { with_images: true });
}
```

### Form Annotation Data

**`form_data` may be stored separately and requires separate fetch:**

```typescript
// FormAnnotationGET may have form_data, but large data is stored separately
const annotation = formAnnotations.get(123);

// Get form data (may trigger separate API call)
const formData = await getFormAnnotationValue(123);

// Update form data
await setFormAnnotationValue(123, newFormData);

// Store is updated automatically
const updated = formAnnotations.get(123);
console.log(updated.form_data);  // Updated value
```

### Segmentation Data

**Segmentation data requires `getSegmentationData()` - not stored in `SegmentationGET`:**

```typescript
// SegmentationGET contains metadata only
const seg = segmentations.get(123);
console.log(seg.width, seg.height, seg.depth);  // ✅ Available

// Actual data requires separate fetch
const data = await getSegmentationData(123, { scan_nr: 5, sparse_axis: 1 });
// Returns decoded numpy array
```

## API Functions

### Fetch Functions

All fetch functions automatically ingest data into stores:

```typescript
// Basic fetches
await fetchTags();
await fetchFeatures({ with_counts: true });
await fetchFormSchemas();
await fetchTasks();

// Entity fetches
await fetchInstance(id, { 
  with_segmentations: true,
  with_form_annotations: true,
  with_model_segmentations: true,
  with_tag_metadata: true
});
await fetchStudy(id);

// Task fetches
await fetchTask(id);
await fetchSubTasks({
  task_id: id,
  with_images: true,
  limit: 20,
  page: 0,
  subtask_status: 'Ready'
});
await fetchSubTaskByIndex(taskId, subtaskIndex, { 
  with_images: true,
  with_next: false
});
```

### Search Functions

Search functions automatically ingest results:

```typescript
// Instance search
const result = await searchInstances({
  conditions: [
    { type: 'default', variable: 'Laterality', operator: '==', value: 'L' }
  ],
  limit: 100,
  page: 0,
  order_by: 'Study Date',
  order: 'ASC',
  include_count: true
});
// Returns: { instances: InstanceGET[], studies: StudyGET[], result_ids: number[], count?: number, has_more: boolean }

// Study search
const result = await searchStudies({
  conditions: [
    { variable: 'Study Date', operator: '==', value: '2024-01-01' }
  ],
  limit: 50,
  page: 0,
  order_by: 'Study Date',
  order: 'DESC',
  include_count: true
});
// Returns: { studies: StudyGET[], instances: InstanceMeta[], result_ids: number[], count?: number, has_more: boolean }
```

### CRUD Helper Functions

**Tag operations:**
```typescript
await tagInstance(instance, tagId, comment);
await updateTagInstance(instanceId, tagId, comment);
await untagInstance(instance, tagId);

await tagStudy(study, tagId, comment);
await updateTagStudy(studyId, tagId, comment);
await untagStudy(study, tagId);

await tagSegmentation(seg, tagId, comment);
await untagSegmentation(seg, tagId);

await tagFormAnnotation(annotation, tagId, comment);
await updateTagFormAnnotation(annotationId, tagId, comment);
await untagFormAnnotation(annotation, tagId);
```

**Segmentation operations:**
```typescript
await createSegmentation(metadata, np_array);
await createSegmentationFrom(image, feature_id, data_representation, data_type, threshold, sparse_axis, subtask_id);
await fetchSegmentation(id);
await updateSegmentation(id, { threshold, reference_segmentation_id });
await deleteSegmentation(id);
await getSegmentationData(id, { scan_nr, sparse_axis });
await updateSegmentationData(id, arrayBuffer, { scan_nr, sparse_axis });
await getModelSegmentationData(id, { axis, scan_nr, sparse_axis });
```

**Form annotation operations:**
```typescript
await fetchFormAnnotation(id);
await fetchFormAnnotations({ patient_id, study_id, image_instance_id, form_schema_id, sub_task_id });
await createFormAnnotation({ form_schema_id, patient_id, study_id, image_instance_id, laterality, sub_task_id, form_data, form_annotation_reference_id });
await deleteFormAnnotation(id);
await getFormAnnotationValue(id);
await setFormAnnotationValue(id, form_data);
```

**Feature operations:**
```typescript
await createFeature({ name, subfeature_ids });
await updateFeature(featureId, { name, subfeature_ids });
await deleteFeature(featureId);
```

**Tag operations:**
```typescript
await createTag(name, tagType, description);
await deleteTag(tagId);
await starTag(tagId);
await unstarTag(tagId);
```

**Task operations:**
```typescript
await createTask({ name, description, contact_id, task_definition_id });
await updateTask(id, { name, description, contact_id, task_definition_id, task_state });
await deleteTask(id);
await updateSubTask(subtaskId, { task_state, comments });
await addSubTaskImage(subtaskId, instanceId);
await removeSubTaskImage(subtaskId, instanceId);
await updateSubTaskComments(subtaskId, comments);
```

**Lookup functions:**
```typescript
getInstanceBySOPInstanceUID(SOPInstanceUid: string): InstanceGET | undefined
getInstanceByDataSetIdentifier(datasetIdentifier: string): InstanceGET | undefined
```

## Server-Side API Design

### High-Level Overview

The server uses **SQLAlchemy ORM** with **FastAPI** for the REST API. Data is converted from ORM objects to **DTOs (Data Transfer Objects)** before serialization.

### Eager Loading with selectinload

The server uses SQLAlchemy's `selectinload` for eager loading relationships:

```python
# Example from server/routes/instances.py
opts = [
    # Base graph
    selectinload(ImageInstance.Series).selectinload(Series.Study).selectinload(Study.Patient).selectinload(Patient.Project),
    selectinload(ImageInstance.DeviceInstance).selectinload(DeviceInstance.DeviceModel),
    selectinload(ImageInstance.Scan),
    # Instance tags
    selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Tag),
    selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(ImageInstanceTagLink.Creator),
]
if with_segmentations:
    opts.append(selectinload(ImageInstance.Segmentations))
```

### Response Patterns

**`/instances/search`** returns:
- `instances: InstanceGET[]` - Full objects with all metadata
- `studies: StudyGET[]` - With embedded `series: SeriesGET[]` (full objects)
- Both are ingested into their respective stores

**`/studies/search`** returns:
- `studies: StudyGET[]` - With embedded `series: SeriesGET[]` (full objects)
- `instances: InstanceMeta[]` - Lightweight references (not full objects!)
- Studies are ingested into `studies` store
- Instance metas are ingested into `instanceMetas` store

**`/instances/{id}`** supports optional flags:
- `with_segmentations: bool` - Include `segmentations: SegmentationGET[]`
- `with_form_annotations: bool` - Include `form_annotations: FormAnnotationGET[]`
- `with_model_segmentations: bool` - Include `model_segmentations: ModelSegmentationGET[]`
- `with_tag_metadata: bool` - Include full tag metadata (default: true)

**`/task/{task_id}/subtasks`** supports:
- `with_images: bool` - Include `images: InstanceGET[]` in response (returns `SubTaskWithImagesGET[]`)

### DTO Pattern

ORM objects are converted to DTOs using `DTOConverter`:

```python
# Example from server/dtos/dto_converter.py
@staticmethod
def image_instance_to_get(
    image_instance: "ImageInstance",
    with_tag_metadata: bool = False,
    with_segmentations: bool = False,
    with_form_annotations: bool = False,
    with_model_segmentations: bool = False,
) -> InstanceGET:
    # Convert ORM object to DTO
    return InstanceGET(
        id=image_instance.ImageInstanceID,
        sop_instance_uid=image_instance.SOPInstanceUid,
        study=StudyMeta(id=image_instance.Series.Study.StudyID, date=...),
        series=SeriesMeta(id=image_instance.Series.SeriesID),
        # ... other fields
        segmentations=[...] if with_segmentations else None,
    )
```

### Embedded vs Referenced Data

**Embedded data** (full objects in response):
- `StudyGET.series: SeriesGET[]` - Full series objects with `instance_ids`
- `SubTaskWithImagesGET.images: InstanceGET[]` - Full instance objects
- `InstanceGET.segmentations?: SegmentationGET[]` - When `with_segmentations=true`
- `InstanceGET.form_annotations?: FormAnnotationGET[]` - When `with_form_annotations=true`

**Referenced data** (Meta objects with just IDs):
- `InstanceGET.study: StudyMeta` - Just `{ id: number, date: string }`
- `InstanceGET.series: SeriesMeta` - Just `{ id: number }`
- `InstanceGET.patient: PatientMeta` - Just `{ id: number, identifier: string, birth_date?: string }`
- `SeriesGET.instance_ids?: number[]` - Just array of IDs, not full objects

**Relationship traversal:**
1. Get ID from Meta reference: `instance.study.id`
2. Look up full object from store: `studies.get(instance.study.id)`
3. Access embedded data: `study.series` (full objects)
4. Use IDs to look up related objects: `series.instance_ids.map(id => instanceMetas.get(id))`

## Things to Pay Attention To

### Always Use Correct Ingest Function

- Use `ingestInstances()` for `InstanceGET[]`
- Use `ingestInstanceMetas()` for `InstanceMeta[]`
- Using the wrong function will log errors and skip entries

### Check for Undefined

- Always check for `undefined` when looking up objects: `const instance = instances.get(id)`
- Use optional chaining in Svelte: `const study = $derived(instance ? studies.get(instance.study.id) : undefined)`
- Missing data may require a separate fetch: `if (!study) await fetchStudy(id)`

### Use $derived for Reactive Lookups

- In Svelte components, use `$derived` for reactive lookups:
  ```svelte
  const instance = $derived(instances.get(instanceId));
  const study = $derived(instance ? studies.get(instance.study.id) : undefined);
  ```

### Tag Operations Update Stores Immediately

- Tag operations (`tagInstance`, `untagInstance`, etc.) update stores immediately
- No need to refetch after tagging - stores are already updated
- Both `instances` and `instanceMetas` stores are updated when present

### Form Annotation Data May Need Separate Fetch

- `FormAnnotationGET.form_data` may be `null` or `undefined`
- Use `getFormAnnotationValue(id)` to fetch form data separately
- Use `setFormAnnotationValue(id, data)` to update form data

### Segmentation Data Requires Separate Fetch

- `SegmentationGET` contains metadata only (width, height, depth, etc.)
- Use `getSegmentationData(id, params)` to fetch actual data
- Returns decoded numpy array

### Check SubTask Type at Runtime

- `subtasks` store contains union type `SubTaskGET | SubTaskWithImagesGET`
- Check `'images' in subtask` to verify type
- Use `fetchSubTaskByIndex(taskId, index, { with_images: true })` to get images

### Secondary Indexes Are Updated Automatically

- `tagsByName`, `featuresByName`, `formSchemasByName` are updated automatically by ingest functions
- No need to manually update indexes
- Use for name-based lookups: `const tag = tagsByName.get('my-tag')`

### Optional Embedded Data Requires Flags

- `InstanceGET.segmentations`, `form_annotations`, `model_segmentations` are optional
- Use `with_*` flags when fetching: `fetchInstance(id, { with_segmentations: true })`
- Check for `null` or `undefined` before accessing: `if (instance.segmentations) { ... }`

### Search Responses Have Different Types

- `/instances/search` returns `InstanceGET[]` in `result.instances`
- `/studies/search` returns `InstanceMeta[]` in `result.instances` (not full objects!)
- Always check which search endpoint you're using

### Study Series Are Embedded

- `StudyGET.series` contains full `SeriesGET[]` objects (not just IDs)
- Access directly: `study.series?.forEach(series => { ... })`
- Series contain `instance_ids?: number[]` for looking up instances

### Instance Relationships Use Meta

- `InstanceGET.study: StudyMeta` - just ID and date
- `InstanceGET.series: SeriesMeta` - just ID
- Look up full objects: `studies.get(instance.study.id)`
- Full objects may not be in store - may need to fetch
