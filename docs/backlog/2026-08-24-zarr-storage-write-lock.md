# The segmentation zarr store has no write lock

**Status:** open

## Source

Whole-branch review of `feature/api-layer-concurrency` (PR #219), which
de-scoped five handlers rather than ship this.

## What

The store is a process-wide singleton — `get_zarr_storage_manager` in
`orm/eyened_orm/segmentation_storage.py` is an `lru_cache`d
`ZarrStorageManager` — and nothing on the write path takes a lock:

- `ZarrArray._append_to_array` (`orm/eyened_orm/utils/zarr/zarr_array.py:41`)
  appends and then returns `shape[0] - 1`: check-then-act on array length.
- `ZarrStorageManager.get_array` (`orm/eyened_orm/utils/zarr/manager.py:20`)
  is check-then-create on the named array.
- `ZarrArray.write_slice` read-modify-writes a whole chunk, because chunking is
  `(1, *shape)` — one chunk per segmentation, not one per slice.

Give the store a lock, or a backend that has one. Until then the five
zarr-touching endpoints in `server/routes/segmentations.py`
(`create_segmentation`, `update_segmentation_data`, `get_segmentation_data`,
`get_model_segmentation_data`, `update_model_segmentation_data`) must stay
`async def`, so the event loop rather than the threadpool serializes them.

`server/services/segmentation_data_store.py` already carries the seam: the
`SegmentationDataStore` protocol exists so a locking implementation can be
swapped in at `get_segmentation_data_store` without touching the service, the
routes, or their tests.

## Why

Probed against the real manager with those handlers in the threadpool: 8
concurrent creates all returned index `0` and lost 7 of the 8 segmentations,
and 8 concurrent slice writes silently zeroed 3 slices. Both rows then commit
`ZarrArrayIndex = 0`, so the loss is durable in MySQL and nothing raises. This
is annotation data.

**The de-scope restores single-process protection; it does not make the store
safe.** The same interleaving is reachable across processes today — the docker
stack runs gunicorn with `WORKERS=4` by default, each with its own event loop,
and the CLI and importer write the same store from outside the API entirely. A
real fix has to be cross-process, not merely cross-thread.
