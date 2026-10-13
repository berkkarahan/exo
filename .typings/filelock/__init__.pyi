import os
from types import TracebackType
from typing import Self

class Timeout(TimeoutError):
    def __init__(self, lock_file: str) -> None: ...
    @property
    def lock_file(self) -> str: ...

class FileLock:
    def __init__(
        self,
        lock_file: str | os.PathLike[str],
        timeout: float = -1,
        mode: int = 0o644,
        thread_local: bool = True,
        *,
        blocking: bool = True,
        is_singleton: bool = False,
    ) -> None: ...
    def acquire(
        self,
        timeout: float | None = None,
        poll_interval: float = 0.05,
        *,
        blocking: bool | None = None,
    ) -> object: ...
    def release(self, force: bool = False) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
