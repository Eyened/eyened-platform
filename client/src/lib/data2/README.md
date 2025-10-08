# Data2 - Simplified Reactive Data Layer

This is an alternative implementation of the data layer that prioritizes **simplicity** and **intuitiveness** over flexibility.

## Key Differences from `/lib/data/`

### Architecture

**Old (`/lib/data/`):**
```typescript
repo.store = $state<Record<Id, PlainObject>>({});
const object = repo.object(id); // Creates wrapper
object.$.modality; // Access via .$ 
```

**New (`/lib/data2/`):**
```typescript
repo.items = new SvelteMap<Id, ClassInstance>();
const instance = repo.get(id); // Get class instance
instance.modality; // Direct access!
```

### Key Benefits

1. **SvelteMap provides built-in reactivity** - no need for `$derived` wrappers or reassignment tricks
2. **Direct property access** - `instance.modality` instead of `instance.$.modality`
3. **Simpler types** - `Repo<TData, TInstance>` instead of `Repo<TGet, TCreate, TPatch, ListParams, TDataObject>`
4. **Class instances with methods** - Each item IS an actual class with behavior
5. **Access to other repos** - Items can access `this.repos` to traverse relationships

## Usage Examples

### Basic Usage

```svelte
<script lang="ts">
  import { GlobalContext } from '$lib/data2/globalContext.svelte';
  
  const gc = new GlobalContext();
  await gc.init(pathname);
  
  // Fetch data
  await gc.instances.fetchAll();
  
  // Access items - reactive!
  const leftInstances = $derived(
    gc.instances.all.filter(i => i.laterality === 'L')
  );
</script>

{#each leftInstances as instance (instance.id)}
  <div>
    <!-- Direct property access -->
    {instance.modality} - {instance.laterality}
    
    <!-- Traverse relationships -->
    Study: {instance.study?.description}
    
    <!-- Access nested data -->
    {#each instance.tags as tag}
      <span style="color: {tag.color}">{tag.name}</span>
    {/each}
  </div>
{/each}
```

### Working with Items

```typescript
// Get a specific instance
const instance = gc.instances.get(123);

// Call methods on it
await instance.tag(5);
await instance.untag(5);

// Update locally (optimistic)
instance.updateLocal({ laterality: 'R' });

// Traverse relationships
const study = instance.study;
const series = instance.series;
const segmentations = instance.segmentations;

// Fetch from server
const fresh = await gc.instances.fetchOne(123);
```

### Creating Items

```typescript
// Create a new tag
const tag = await gc.tags.create({
  name: 'Important',
  tag_type: 'Study',
  color: '#ff0000'
});

// Use it immediately
console.log(tag.name); // 'Important'
await tag.star();
```

### Updating Items

```typescript
const tag = gc.tags.get(5);

// Option 1: Update via repo
await gc.tags.update(5, { name: 'Very Important' });

// Option 2: Update via item (if implemented)
await tag.save({ name: 'Very Important' });

// Optimistic update
tag.updateLocal({ name: 'Very Important' });
```

## Implementation Details

### Repo Class

- Uses `SvelteMap` for automatic reactivity
- Simple API: `get()`, `all`, `upsert()`, `remove()`
- API methods: `fetchAll()`, `fetchOne()`, `create()`, `update()`, `delete()`
- Type-safe with separate `TCreate` and `TPatch` types

### RepoItem Base Class

- All items inherit from this
- Holds reactive `_data` using `$state`
- Provides access to global repos via `this.repos`
- Supports immutable updates via `updateLocal()`
- Can override `save()`, `delete()`, `refresh()` methods

### Model Classes

- Extend `RepoItem<TData>`
- Define getters for clean property access
- Implement custom methods (e.g., `tag()`, `untag()`, `getData()`)
- Can traverse relationships via `this.repos`

## Comparison Table

| Feature | Old (`/lib/data/`) | New (`/lib/data2/`) |
|---------|-------------------|---------------------|
| Storage | `$state` object | `SvelteMap` |
| Reactivity | Manual `$derived` | Automatic |
| Property access | `obj.$.prop` | `obj.prop` |
| Type params | 5 generics | 2-4 generics |
| Data location | Repo store | Class instance |
| Relationships | Via methods | Via getters |
| Immutability | Yes | Yes |
| Unsaved objects | Supported | Not yet |

## Testing Alongside Old Implementation

Both implementations can coexist:

```typescript
// Old way
import { GlobalContext as OldGC } from '$lib/data/globalContext.svelte';

// New way
import { GlobalContext as NewGC } from '$lib/data2/globalContext.svelte';

// Use whichever you prefer
const gc = new NewGC();
```

## Migration Path

1. **Test in parallel** - Use `data2` in new components
2. **Compare ergonomics** - See which feels better
3. **Identify gaps** - What's missing from `data2`?
4. **Iterate** - Add missing features to `data2`
5. **Decide** - Choose one approach going forward

## Known Limitations

- ❌ No support for unsaved/draft objects (yet)
- ❌ No multiple wrapper instances for same data
- ❌ Less flexibility in type separation (though still type-safe)
- ❌ Not all models implemented yet (e.g., Patient, Task)

## Future Enhancements

- [ ] Add support for draft objects (not in repo)
- [ ] Add Patient, Project, Task models
- [ ] Add pagination support
- [ ] Add query/filter helpers
- [ ] Add devtools integration

