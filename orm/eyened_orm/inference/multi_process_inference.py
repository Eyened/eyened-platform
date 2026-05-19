from __future__ import annotations

import multiprocessing as mp
import sys
from typing import Any, Generic, Iterable, Iterator, List, Optional, Sequence, Tuple, TypeVar

InT = TypeVar("InT")
PrepT = TypeVar("PrepT")
BatchOutT = TypeVar("BatchOutT")
OutT = TypeVar("OutT")


class BaseInferencePipeline(Generic[InT, PrepT, BatchOutT, OutT]):
    """Inference pipeline with pass-through defaults."""

    def preprocess(self, item: InT) -> PrepT:
        return item  # type: ignore[return-value]

    def process_batch(self, prep_batch: List[PrepT]) -> Iterable[BatchOutT]:
        return prep_batch  # type: ignore[return-value]

    def postprocess(self, prep_item: PrepT, batch_output: BatchOutT) -> OutT:
        return batch_output  # type: ignore[return-value]


def prep_worker(
    work_q: mp.Queue,
    prep_q: mp.Queue,
    pipeline: BaseInferencePipeline[InT, PrepT, BatchOutT, OutT],
) -> None:
    for item in iter(work_q.get, None):
        iid, input_item = item
        try:
            prep_q.put((iid, pipeline.preprocess(input_item)))
        except Exception as e:
            print(f"Error preprocessing image {iid}: {e}", file=sys.stderr)
            prep_q.put((iid, None))
    prep_q.put(None)


class MultiProcessInference(Generic[InT, PrepT, BatchOutT, OutT]):
    def __init__(
        self,
        items: Iterable[Tuple[int, InT]],
        pipeline: BaseInferencePipeline[InT, PrepT, BatchOutT, OutT],
        n_workers: int = 8,
        batch_size: int = 8,
        queue_max_size: Optional[int] = None
    ) -> None:
        """Initialize MultiProcessInference.
        
        Args:
            items: Iterable of (image_id, input_item) tuples
            pipeline: BaseInferencePipeline object implementing pipeline stages
            n_workers: Number of preprocessing worker processes
            batch_size: Batch size for batch processing
            queue_max_size: Maximum size of preprocessing queue
        """
        self.items = items
        self.pipeline = pipeline
        self.n_workers = n_workers
        self.batch_size = batch_size
        self.queue_max_size = queue_max_size or batch_size
        self._ctx = mp.get_context()

        self._work_q = self._ctx.Queue()
        for item in self.items:
            self._work_q.put(item)
        for _ in range(self.n_workers):
            self._work_q.put(None)

        self._prep_q = self._ctx.Queue(maxsize=self.queue_max_size)

        self._workers = []

    def _start_workers(self) -> None:
        self._workers = [
            self._ctx.Process(
                target=prep_worker,
                args=(self._work_q, self._prep_q, self.pipeline),
            )
            for _ in range(self.n_workers)
        ]
        for p in self._workers:
            p.start()

    def _batch_consumer(self) -> Iterator[Tuple[int, Optional[PrepT], Optional[BatchOutT]]]:
        buffer: List[Tuple[int, Optional[PrepT]]] = []
        finished = 0
        while finished < self.n_workers:
            item = self._prep_q.get()
            if item is None:
                finished += 1
            else:
                buffer.append(item)

            if buffer and (
                len(buffer) == self.batch_size
                or (item is None and finished == self.n_workers)
            ):
                # Separate successful and failed preprocessing results
                successful_items: List[Tuple[int, PrepT]] = [
                    (iid, prep_item) for iid, prep_item in buffer if prep_item is not None
                ]
                failed_items: List[Tuple[int, None]] = [
                    (iid, prep_item) for iid, prep_item in buffer if prep_item is None
                ]
                
                # Yield None for items that failed preprocessing
                for iid, _ in failed_items:
                    yield iid, None, None
                
                # Process successful items in batch
                if successful_items:
                    prep_batch = [prep_item for _, prep_item in successful_items]
                    try:
                        batch_outputs = self.pipeline.process_batch(prep_batch)
                        for (iid, prep_item), batch_output in zip(successful_items, batch_outputs):
                            yield iid, prep_item, batch_output
                    except Exception as e:
                        iids = [iid for iid, _ in successful_items]
                        print(f"Error processing batch for images {iids}: {e}", file=sys.stderr)
                        # Yield None for each item in the failed batch
                        for iid, _ in successful_items:
                            yield iid, None, None
                buffer = []

    def run(self) -> Iterator[Tuple[int, Optional[OutT]]]:
        self._start_workers()
        try:
            for iid, prep_item, batch_output in self._batch_consumer():
                if batch_output is None:
                    yield iid, None
                else:
                    try:
                        # If batch_output is not None, prep_item should also be present.
                        result = self.pipeline.postprocess(prep_item, batch_output)  # type: ignore[arg-type]
                        yield iid, result
                    except Exception as e:
                        print(f"Error postprocessing image {iid}: {e}", file=sys.stderr)
                        yield iid, None
        finally:
            for p in self._workers:
                p.join()
