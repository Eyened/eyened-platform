# Side-by-Side Comparison: data vs data2

This guide shows how to accomplish the same tasks in both implementations.

## Setup

### Old (`/lib/data/`)
```typescript
import { GlobalContext } from '$lib/data/globalContext.svelte';
import { TagsRepo } from '$lib/data/repos.svelte';

const gc = new GlobalContext();
await gc.init(pathname);

// Tags are already on globalContext
const tags = gc.tags;
```

### New (`/lib/data2/`)
```typescript
import { GlobalContext } from '$lib/data2/globalContext.svelte';

const gc = new GlobalContext();
await gc.init(pathname);

// Tags are on globalContext
const tags = gc.tags;
```

✅ **Similar setup, but simpler types**

---

## Fetching Data

### Old
```typescript
// Fetch all tags
await gc.tags.fetchAll();

// Access all items
const allTags = gc.tags.all; // Returns TGet[] (plain objects)
```

### New
```typescript
// Fetch all tags  
await gc.tags.fetchAll();

// Access all items
const allTags = gc.tags.all; // Returns Tag[] (class instances)
```

✅ **Same API, but returns class instances instead of plain objects**

---

## Accessing Properties

### Old
```typescript
const tagId = 123;
const tagObject = gc.tags.object(tagId);

// Need to use .$ to access data
console.log(tagObject.$.name);
console.log(tagObject.$.description);
console.log(tagObject.$.tag_type);
```

### New
```typescript
const tagId = 123;
const tag = gc.tags.get(tagId);

// Direct property access
console.log(tag.name);
console.log(tag.description);
console.log(tag.tagType);
```

✅ **Much cleaner - no .$ accessor needed!**

---

## Reactive Filtering

### Old
```typescript
const studyTags = $derived(
  gc.tags.all.filter(t => t.tag_type === 'Study')
);
```

### New  
```typescript
const studyTags = $derived(
  gc.tags.all.filter(t => t.tagType === 'Study')
);
```

✅ **Same pattern, but cleaner property names**

---

## Creating Items

### Old
```typescript
const newTag = await gc.tags.create({
  name: 'Important',
  tag_type: 'Study',
  description: 'Important studies'
});

// newTag is a DataObject<TagGET>
// Access properties via .$
console.log(newTag.$.name);
```

### New
```typescript
const newTag = await gc.tags.create({
  name: 'Important',
  tag_type: 'Study', 
  description: 'Important studies'
});

// newTag is a Tag instance
// Access properties directly
console.log(newTag.name);
```

✅ **Same API, cleaner access**

---

## Updating Items

### Old
```typescript
const tag = gc.tags.object(123);

// Optimistic update
tag.updateLocal({ name: 'New Name' });

// Save to server
await tag.save({ name: 'New Name' });

// Or via repo
await gc.tags.remoteUpdate(123, { name: 'New Name' });
```

### New
```typescript
const tag = gc.tags.get(123);

// Optimistic update
tag.updateLocal({ name: 'New Name' });

// Save to server (if implemented on the class)
await tag.save({ name: 'New Name' });

// Or via repo
await gc.tags.update(123, { name: 'New Name' });
```

✅ **Very similar, method names slightly cleaner**

---

## Traversing Relationships

### Old
```typescript
// Instance -> Study -> Patient
const instance = gc.instances.object(instanceId);
const studyId = instance.$.study.id;
const study = gc.studies.object(studyId);
const description = study.$.description;

// Multi-step, verbose
```

### New
```typescript
// Instance -> Study -> Patient
const instance = gc.instances.get(instanceId);
const description = instance.study?.description;

// Direct, clean traversal
```

✅ **Much more intuitive!**

---

## Custom Methods

### Old
```typescript
const instance = gc.instances.object(123);

// Tag instance
await api.POST('/instances/{instance_id}/tags', ...);
instance.updateLocal({ tags: [...instance.$.tags, newTag] });

// Methods defined on InstanceObject class
await instance.tag(5);
```

### New
```typescript
const instance = gc.instances.get(123);

// Methods directly on instance
await instance.tag(5);
await instance.untag(5);

// Clean and obvious
```

✅ **Same capability, but more discoverable**

---

## Working with Segmentations

### Old
```typescript
const seg = gc.segmentations.object(segId);

// Access data
const instanceId = seg.$.image_instance_id;
const featureId = seg.$.feature_id;

// Get related data
const instance = gc.instances.object(instanceId);
const feature = gc.features.object(featureId);

// Get numpy data
const data = await gc.segmentations.getData(segId);
```

### New
```typescript
const seg = gc.segmentations.get(segId);

// Access data
const instanceId = seg.instanceId;
const featureName = seg.featureName; // Embedded!

// Get related data (reactive getters)
const instance = seg.instance;
const feature = seg.feature;

// Get numpy data (method on instance)
const data = await seg.getData();
```

✅ **Much cleaner, relationships are getters**

---

## Reactivity

### Old
```typescript
// Store is $state<Record<Id, TGet>>
// Needs reassignment for reactivity
this.store = { ...this.store };

// DataObjects use $derived to track changes
const obj = repo.object(id);
$effect(() => {
  console.log(obj.$.name); // Reactive
});
```

### New
```typescript
// Store is SvelteMap<Id, Instance>
// Automatic reactivity, no reassignment

// Instances are reactive via $state
const instance = repo.get(id);
$effect(() => {
  console.log(instance.name); // Reactive
});
```

✅ **Simpler, built-in reactivity**

---

## Type Safety

### Old
```typescript
class Repo<
  TGet extends { id: Id },
  TCreate = Partial<TGet>,
  TPatch = Partial<TGet>,
  ListParams = unknown,
  TDataObject extends DataObject<TGet, TPatch> = DataObject<TGet, TPatch>
> {
  // 5 type parameters!
}
```

### New
```typescript
class Repo<
  TData extends { id: Id },
  TItem extends RepoItem<TData>,
  TCreate = Partial<TData>,
  TPatch = Partial<TData>
> {
  // 2-4 type parameters, clearer names
}
```

✅ **Simpler types, easier to understand**

---

## In Svelte Components

### Old
```svelte
<script lang="ts">
  const { instances } = globalContext;
  
  const leftInstances = $derived(
    instances.all.filter(i => i.laterality === 'L')
  );
</script>

{#each leftInstances as inst (inst.id)}
  <div>
    {inst.modality} - {inst.laterality}
    Study: {instances.object(inst.study.id).$.description}
  </div>
{/each}
```

### New
```svelte
<script lang="ts">
  const { instances } = globalContext;
  
  const leftInstances = $derived(
    instances.all.filter(i => i.laterality === 'L')
  );
</script>

{#each leftInstances as inst (inst.id)}
  <div>
    {inst.modality} - {inst.laterality}
    Study: {inst.study?.description}
  </div>
{/each}
```

✅ **Cleaner templates, more readable**

---

## Summary

| Feature | Old (`/lib/data/`) | New (`/lib/data2/`) | Winner |
|---------|-------------------|---------------------|--------|
| Property access | `obj.$.prop` | `obj.prop` | ✅ New |
| Relationship traversal | Multi-step | Direct getters | ✅ New |
| Type complexity | 5 generics | 2-4 generics | ✅ New |
| Reactivity mechanism | `$derived` wrapper | `SvelteMap` + `$state` | ✅ New |
| Learning curve | Steeper | Gentler | ✅ New |
| Flexibility | More options | More opinionated | Old |
| Unsaved objects | Supported | Not yet | Old |
| Multiple wrappers | Supported | N/A | Old |

**Recommendation:** Use `data2` for new development unless you specifically need unsaved/draft objects or multiple wrapper instances.

