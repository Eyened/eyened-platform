"""Chunked run loop shared by segmentation CLI / worker entrypoints."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class SegmentationBatchPipeline(Protocol):
    def filter_image_ids(self, image_ids: Iterable[int]) -> set[int]: ...

    def run(self, image_ids: Iterable[int]) -> None: ...


def run_segmentation_batches(
    session,
    image_ids: Iterable[int],
    pipeline: SegmentationBatchPipeline,
    *,
    overwrite: bool = False,
    commit_after_chunk: bool = False,
) -> int:
    """Filter, run, and optionally commit per chunk. Returns images processed."""
    from eyened_orm.commands.targets import iter_image_id_chunks

    image_ids_set = set(image_ids)
    total_processed = 0
    chunks = list(iter_image_id_chunks(image_ids_set))
    for chunk_idx, chunk in enumerate(chunks, start=1):
        filtered = chunk if overwrite else pipeline.filter_image_ids(chunk)
        if not filtered:
            continue
        print(
            f"Processing {len(filtered)} images "
            f"(chunk {chunk_idx}/{len(chunks)}"
            f"{', overwrite' if overwrite else ', after filtering existing'})"
        )
        pipeline.run(filtered)
        if commit_after_chunk:
            session.commit()
        total_processed += len(filtered)

    if total_processed == 0:
        print("No images to process")
        return 0
    print(f"Completed processing {total_processed} images")
    return total_processed
