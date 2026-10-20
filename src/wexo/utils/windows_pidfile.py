"""Single-instance guard used by ``exo.main`` on Windows.

``exo_rs.Pidfile`` locks with POSIX ``flock`` and is not available on Windows.
``main`` constructs this object before serving, calls ``write`` with the
process id, and calls ``close`` from its ``finally`` block. ``PidfileError``
is handled there by printing the message and exiting.

The lock is a separate file held until ``close``. ``write`` only updates the
pid text; it does not release the lock.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import final

from filelock import FileLock, Timeout


class PidfileError(Exception):
    """Another exo process already holds this pidfile.

    Handled in ``exo.main.main``, which prints the message and exits.
    """


@final
class Pidfile:
    def __init__(self, path: Path, mode: int) -> None:
        self._path = path
        self._closed = False
        # thread_local would hide the lock from a different thread's close().
        self._lock = FileLock(
            path.with_suffix(".lock"),
            timeout=0,
            mode=mode,
            thread_local=False,
        )
        try:
            _ = self._lock.acquire()
        except Timeout as error:
            raise PidfileError(f"exo is already running (locked {path})") from error

    def write(self) -> None:
        """Record this process id. The lock stays held."""
        _ = self._path.write_text(str(os.getpid()), encoding="utf-8")

    def close(self) -> None:
        """Release the lock and remove the pid file. A second call does nothing."""
        if self._closed:
            return
        self._closed = True
        self._lock.release()
        self._path.unlink(missing_ok=True)
