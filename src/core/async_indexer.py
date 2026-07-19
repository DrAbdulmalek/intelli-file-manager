"""
Async Indexer — non-blocking file ingestion pipeline.

This is a STUB file proposing the API for the async indexer described in
docs/DEVELOPMENT_ROADMAP.md (Section 6.1).

Goal: keep the UI responsive while ingesting large file collections.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Callable, Optional


class AsyncIndexer:
    """
    Async file indexer using a queue + thread pool.

    Usage:
        indexer = AsyncIndexer(processor_callback=my_processor)
        await indexer.start()
        await indexer.add_to_queue("/path/to/file")
        ...
        await indexer.stop()
    """

    def __init__(
        self,
        max_workers: int = 4,
        processor_callback: Optional[Callable[[str, str], Dict[str, Any]]] = None,
    ):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.processor_callback = processor_callback
        self.indexing_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self._worker_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Start the indexing worker."""
        if self.is_running:
            return
        self.is_running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Stop the indexing worker gracefully (waits for queue to drain)."""
        self.is_running = False
        await self.indexing_queue.join()
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        self.executor.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def add_to_queue(self, file_path: str) -> None:
        await self.indexing_queue.put(file_path)

    async def add_many_to_queue(self, file_paths: List[str]) -> None:
        for path in file_paths:
            await self.indexing_queue.put(path)

    def queue_size(self) -> int:
        return self.indexing_queue.qsize()

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------
    async def _worker_loop(self) -> None:
        while self.is_running:
            try:
                file_path = await self.indexing_queue.get()
            except asyncio.CancelledError:
                break

            try:
                await self._index_file(file_path)
            except Exception as exc:
                print(f"[AsyncIndexer] Error indexing {file_path}: {exc}")
            finally:
                self.indexing_queue.task_done()

    async def _index_file(self, file_path: str) -> Dict[str, Any]:
        """Read + process a single file off the event loop."""
        loop = asyncio.get_event_loop()

        # Read the file (use aiofiles when available)
        content = await self._read_file(file_path)

        # Run CPU-bound work in the thread pool
        result = await loop.run_in_executor(
            self.executor,
            self._process_file,
            file_path,
            content,
        )
        return result

    async def _read_file(self, file_path: str) -> str:
        """Async file read.

        TODO: switch to aiofiles when the dependency is added.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._sync_read, file_path)

    @staticmethod
    def _sync_read(file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError:
            return ""

    def _process_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Delegate to the processor callback if provided."""
        if self.processor_callback is None:
            return {"file_path": file_path, "indexed": False}
        return self.processor_callback(file_path, content)
