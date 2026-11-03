"""Run any registered model over a set of images and store the results."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from sqlalchemy.exc import OperationalError
from tqdm import tqdm

from eyened_orm import ImageInstance
from eyened_orm.inference.model_inputs import attribute_value_data, resolve_inputs_for_images
from eyened_orm.inference.multi_process_inference import MultiProcessInference
from eyened_orm.inference.outputs import MODES, Mode
from eyened_orm.inference.pipeline import InferenceItem, Pipeline
from eyened_orm.inference.registry import ModelSpec, get_spec

# MySQL: 1205 lock wait timeout, 1213 deadlock
_RETRYABLE_MYSQL_ERRNOS = frozenset({1205, 1213})
_MAX_COMMIT_ATTEMPTS = 3


@dataclass
class RunSummary:
    candidates: int = 0
    pending: int = 0
    processed: int = 0
    skipped_missing_inputs: int = 0
    failed: list[int] = field(default_factory=list)
    errors: list[int] = field(default_factory=list)
    """Images whose results could not be saved."""


def resolve_device(pipeline_cls: type[Pipeline], device: Any = None) -> Any:
    """Torch device for pipelines that need one; ``None`` otherwise."""
    if not pipeline_cls.needs_torch:
        return None
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "This model needs PyTorch, which is not installed. "
            "See the inference documentation for how to run models that need it: "
            "https://eyened.github.io/eyened-platform/orm/inference/#workers-and-images"
        ) from exc
    if device is None:
        from eyened_orm.inference.utils import auto_device

        return auto_device()
    return device if isinstance(device, torch.device) else torch.device(device)


def _is_retryable(exc: BaseException) -> bool:
    orig = getattr(exc, "orig", None)
    errno = getattr(orig, "args", (None,))[0] if orig is not None else None
    return errno in _RETRYABLE_MYSQL_ERRNOS


def _resolve_inputs(
    session, pipeline: Pipeline, image_ids: set[int]
) -> tuple[set[int], dict[int, dict[str, Any]], dict[int, list[int]]]:
    """Return ``(ready_ids, plain input values, input AttributeValueIDs)`` per image.

    Only plain values and IDs are kept: the MPI feeder thread must not touch
    live ORM objects, and commits mid-run would expire them.
    """
    if not pipeline.inputs:
        return image_ids, {}, {}
    resolved = resolve_inputs_for_images(session, image_ids, pipeline.inputs)
    names = {spec.resolved_input_name for spec in pipeline.inputs}
    ready = {i for i, inputs in resolved.items() if names <= inputs.keys()}
    values = {
        i: {name: attribute_value_data(av) for name, av in resolved[i].items()}
        for i in ready
    }
    av_ids = {i: [av.AttributeValueID for av in resolved[i].values()] for i in ready}
    return ready, values, av_ids


def _iter_items(
    session, pipeline: Pipeline, image_ids: Iterable[int], values: dict[int, dict]
) -> Iterator[tuple[int, InferenceItem | None]]:
    """Decode one image at a time in a dedicated session (safe in the feeder thread)."""
    from sqlalchemy.orm import sessionmaker

    with sessionmaker(bind=session.get_bind())() as load_session:
        for image_id in image_ids:
            try:
                image = load_session.get(ImageInstance, image_id)
                if image is None:
                    print(f"Image {image_id} not found")
                    yield image_id, None
                    continue
                item = InferenceItem(pipeline.load_image(image), values.get(image_id))
                load_session.expunge(image)
            except Exception as exc:
                print(f"Failed to load image {image_id}: {exc}")
                load_session.rollback()
                item = None
            yield image_id, item


def _commit(session, sink, batch, av_ids, *, overwrite: bool, summary: RunSummary) -> None:
    """Save and commit ``batch``; replay the whole batch on MySQL lock/deadlock errors."""
    if not batch:
        return
    for attempt in range(1, _MAX_COMMIT_ATTEMPTS + 1):
        try:
            for image_id, result in batch:
                if result is None:
                    sink.save_failure(image_id)
                else:
                    sink.save(
                        image_id, result, input_av_ids=av_ids.get(image_id, ()), overwrite=overwrite
                    )
            session.commit()
            break
        except OperationalError as exc:
            if not _is_retryable(exc) or attempt == _MAX_COMMIT_ATTEMPTS:
                raise
            print(f"commit batch ({len(batch)} images): {exc.orig}; retry {attempt}")
            session.rollback()
            time.sleep(0.5 * 2 ** (attempt - 1))
        except Exception as exc:
            session.rollback()
            ids = [image_id for image_id, _ in batch]
            print(f"Could not save results for images {ids}: {exc}", flush=True)
            summary.errors.extend(ids)
            batch.clear()
            return
    for image_id, result in batch:
        if result is None:
            summary.failed.append(image_id)
        else:
            summary.processed += 1
    batch.clear()


def run_model(
    session,
    slug: str,
    image_ids: Iterable[int],
    *,
    device: Any = None,
    mode: Mode = "default",
    upscale: bool = False,
    batch_size: int | None = None,
    n_workers: int | None = None,
    commit_interval: int | None = None,
) -> RunSummary:
    """Run model ``slug`` on ``image_ids`` and store its output.

    Images of other modalities are ignored. ``mode`` selects which images are
    (re)processed; see the output's ``pending``. Raises after the run when
    results could not be saved, or when images failed for an output that does
    not record failures (so queued jobs are marked failed).
    """
    from eyened_orm.commands.targets import (
        PIPELINE_IMAGE_CHUNK_SIZE,
        filter_image_ids_by_modalities,
        iter_image_id_chunks,
    )

    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}; choose from {', '.join(MODES)}")
    spec: ModelSpec = get_spec(slug)
    pipeline_cls = spec.load()
    summary = RunSummary()

    ids = filter_image_ids_by_modalities(
        session, set(image_ids), spec.modalities, chunk_size=PIPELINE_IMAGE_CHUNK_SIZE
    )
    summary.candidates = len(ids)
    if not ids:
        print(f"{slug}: no {'/'.join(m.name for m in spec.modalities)} images in target")
        return summary

    pipeline = pipeline_cls(
        resolve_device(pipeline_cls, device), upscale=upscale and spec.supports_upscale
    )
    sink = pipeline.output.register(session, pipeline.inputs)
    session.commit()

    pending = sink.pending(ids, mode)
    summary.pending = len(pending)
    chunks = list(iter_image_id_chunks(pending))
    print(f"{slug}: {len(ids)} candidates, {len(pending)} pending (mode={mode}), {len(chunks)} chunk(s)")

    interval = commit_interval or pipeline.output.commit_interval
    for index, chunk in enumerate(chunks, start=1):
        ready, values, av_ids = _resolve_inputs(session, pipeline, set(chunk))
        summary.skipped_missing_inputs += len(chunk) - len(ready)
        print(
            f"{slug} chunk {index}/{len(chunks)}: {len(ready)} to process"
            + (f", {len(chunk) - len(ready)} missing inputs" if len(ready) < len(chunk) else "")
        )
        if not ready:
            continue
        pipeline.ensure_loaded()
        ordered = sorted(ready)
        mpi = MultiProcessInference(
            _iter_items(session, pipeline, ordered, values),
            pipeline=pipeline,
            n_workers=spec.n_workers if n_workers is None else n_workers,
            batch_size=batch_size or spec.batch_size,
        )
        batch: list[tuple[int, Any]] = []
        for image_id, result in tqdm(mpi.run(), total=len(ordered), desc=slug):
            if result is None:
                print(f"Image {image_id} failed to process")
            batch.append((image_id, result))
            if len(batch) >= interval:
                _commit(session, sink, batch, av_ids, overwrite=mode == "overwrite", summary=summary)
        _commit(session, sink, batch, av_ids, overwrite=mode == "overwrite", summary=summary)

    print(
        f"{slug}: processed {summary.processed}, failed {len(summary.failed)}, "
        f"missing inputs {summary.skipped_missing_inputs}, not saved {len(summary.errors)}"
    )
    unrecorded = [] if pipeline.output.records_failures else summary.failed
    if summary.errors or unrecorded:
        raise RuntimeError(
            f"{slug}: {len(summary.errors) + len(unrecorded)} image(s) failed: "
            f"{sorted(summary.errors + unrecorded)}"
        )
    return summary
