from __future__ import annotations

import multiprocessing as mp
from os import PathLike
from typing import Any, Iterable, Iterator, List, Optional, Protocol, Tuple, TypeVar

T = TypeVar("T")
S = TypeVar("S")
U = TypeVar("U")


class InferencePipeline(Protocol[T, S, U]):
    """Protocol defining the three-stage inference pipeline.
    
    This protocol defines the contract for inference pipelines that can be used
    with MultiProcessInference. Any class implementing these three methods
    can be used as a pipeline.
    """
    
    def preprocess(self, image_path: PathLike[str]) -> T:
        """Preprocess a single image path into a preprocessed format.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Preprocessed item of type T
        """
        ...
    
    def gpu_batch_process(self, prep_batch: List[T]) -> List[S]:
        """Process a batch of preprocessed items on GPU.
        
        Args:
            prep_batch: List of preprocessed items
            
        Returns:
            List of GPU outputs of type S
        """
        ...
    
    def postprocess(self, prep_item: T, gpu_output: S) -> U:
        """Postprocess a single GPU output into final result.
        
        Args:
            prep_item: The preprocessed item that was used to generate gpu_output
            gpu_output: The output from GPU batch processing
            
        Returns:
            Final result of type U
        """
        ...


def prep_worker(
    work_q: mp.Queue,
    prep_q: mp.Queue,
    pipeline: Any,  # InferencePipeline[T, S, U] - using Any for multiprocessing compatibility
) -> None:
    for item in iter(work_q.get, None):
        iid, image_path = item
        prep_q.put((iid, pipeline.preprocess(image_path)))
    prep_q.put(None)


class MultiProcessInference:
    def __init__(
        self,
        items: Iterable[Tuple[int, PathLike[str]]],
        pipeline: InferencePipeline[T, S, U],
        n_workers: int = 8,
        batch_size: int = 8,
        queue_max_size: Optional[int] = None
    ) -> None:
        """Initialize MultiProcessInference.
        
        Args:
            items: Iterable of (image_id, image_path) tuples
            pipeline: InferencePipeline object implementing the three-stage pipeline
            n_workers: Number of preprocessing worker processes
            batch_size: Batch size for GPU processing
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

    def _gpu_consumer(self) -> Iterator[Tuple[int, T, S]]:
        buffer: List[Tuple[int, T]] = []
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
                prep_batch = [prep_item for _, prep_item in buffer]
                gpu_outputs = self.pipeline.gpu_batch_process(prep_batch)
                for (iid, prep_item), gpu_output in zip(buffer, gpu_outputs):
                    yield iid, prep_item, gpu_output
                buffer = []

    def run(self) -> Iterator[Tuple[int, U]]:
        self._start_workers()
        try:
            for iid, prep_item, gpu_output in self._gpu_consumer():
                result = self.pipeline.postprocess(prep_item, gpu_output)
                yield iid, result
        finally:
            for p in self._workers:
                p.join()
