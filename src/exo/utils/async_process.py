from __future__ import annotations

import contextlib
import faulthandler
import multiprocessing as mp
import os
import sys
from collections.abc import Callable, Iterable, Mapping
from multiprocessing.process import BaseProcess
from typing import Protocol, TextIO, cast, final

from anyio import (
    TASK_STATUS_IGNORED,
    BrokenResourceError,
    CancelScope,
    CapacityLimiter,
    ClosedResourceError,
    Event,
    create_task_group,
    move_on_after,
    sleep,
    to_thread,
    wait_readable,
)
from anyio.abc import TaskStatus
from loguru import logger

from exo.utils import STDERR_FD, STDIO_FDS, STDOUT_FD
from exo.utils.channels import Receiver, Sender, channel

if sys.platform == "win32":
    import _winapi
    import io
    import msvcrt
    from multiprocessing.context import get_spawning_popen
else:
    from multiprocessing.resource_sharer import DupFd

_READ_CHUNK_SIZE = 64 * 1024
_WINDOWS_PIPE_POLL_INTERVAL_SECONDS = 0.05
_JOIN_GRACE_SECONDS = 3.0
_TERMINATE_GRACE_SECONDS = 5.0
_TERMINATE_RETRY_GRACE_SECONDS = 2.0
_TERMINATE_ATTEMPTS = 10
_KILL_GRACE_SECONDS = 2.0


class _SupportsDetach(Protocol):
    def detach(self) -> int: ...


class _SpawningPopen(Protocol):
    def duplicate_for_child(self, handle: int) -> int: ...


if sys.platform == "win32":

    @final
    class _WindowsChildHandle:
        def __init__(self, handle: int) -> None:
            self._handle = handle

        def __reduce__(self) -> tuple[type[int], tuple[int]]:
            spawning_popen = cast(_SpawningPopen | None, get_spawning_popen())
            if spawning_popen is None:
                raise RuntimeError("pipe handle can only be serialized while spawning")
            return int, (spawning_popen.duplicate_for_child(self._handle),)


@final
class AsyncProcess:
    def __init__(
        self,
        target: Callable[..., object] | None = None,
        name: str | None = None,
        args: Iterable[object] = (),
        kwargs: Mapping[str, object] | None = None,
        *,
        daemon: bool | None = None,
    ) -> None:
        # setup state
        self._target = target
        self._name = name
        self._args = args
        self._kwargs = kwargs
        self._daemon = daemon

        # lifecycle state
        self._process: BaseProcess | None = None
        self._pid: int | None = None
        self._stdout_tx, self._stdout_rx = channel[bytes]()
        self._stderr_tx, self._stderr_rx = channel[bytes]()
        self._started = Event()
        self._done = Event()
        self._run_cancel_scope: CancelScope | None = None
        self._start_error: BaseException | None = None
        self._exitcode: int | None = None

    async def run(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
        if self._run_cancel_scope is not None or self._done.is_set():
            raise RuntimeError("process has already been started")

        stdout_read_fd: int | None = None
        stdout_write_fd: int | None = None
        stderr_read_fd: int | None = None
        stderr_write_fd: int | None = None

        def cleanup_stdio_fd() -> None:
            nonlocal stdout_read_fd, stdout_write_fd, stderr_read_fd, stderr_write_fd
            stdout_read_fd = _close_fd(stdout_read_fd)
            stdout_write_fd = _close_fd(stdout_write_fd)
            stderr_read_fd = _close_fd(stderr_read_fd)
            stderr_write_fd = _close_fd(stderr_write_fd)

        try:
            with CancelScope() as run_cancel_scope:
                self._run_cancel_scope = run_cancel_scope
                stdout_read_fd, stdout_write_fd = os.pipe()
                stderr_read_fd, stderr_write_fd = os.pipe()

                if sys.platform == "win32":
                    drain_fd = _drain_fd_windows
                    child_target: Callable[..., None] = _run_with_captured_stdio_windows
                    stdout_child_argument: object = _WindowsChildHandle(
                        msvcrt.get_osfhandle(stdout_write_fd)
                    )
                    stderr_child_argument: object = _WindowsChildHandle(
                        msvcrt.get_osfhandle(stderr_write_fd)
                    )
                else:
                    drain_fd = _drain_fd
                    child_target = _run_with_captured_stdio
                    stdout_child_argument = DupFd(stdout_write_fd)
                    stderr_child_argument = DupFd(stderr_write_fd)

                process = mp.Process(
                    target=child_target,
                    name=self._name,
                    args=(
                        stdout_child_argument,
                        stderr_child_argument,
                        self._target,
                        *self._args,
                    ),
                    kwargs={} if self._kwargs is None else self._kwargs,
                    daemon=self._daemon,
                )
                process.start()
                pid = process.pid
                if pid is None:
                    raise RuntimeError("started process has no pid")

                # important to close parent write-side FD to prevent hangs
                stdout_write_fd = _close_fd(stdout_write_fd)
                stderr_write_fd = _close_fd(stderr_write_fd)

                self._process = process
                self._pid = pid
                self._started.set()

                async with create_task_group() as tg:
                    try:
                        tg.start_soon(drain_fd, stdout_read_fd, self._stdout_tx)
                        stdout_read_fd = None
                        tg.start_soon(drain_fd, stderr_read_fd, self._stderr_tx)
                        stderr_read_fd = None
                        task_status.started()
                        await self.wait()
                    finally:
                        with CancelScope(shield=True):
                            await self._terminate_if_still_alive()
        except BaseException as exc:
            if not self._started.is_set():
                self._start_error = exc
                self._started.set()
            raise
        finally:
            try:
                with CancelScope(shield=True):
                    await self._terminate_if_still_alive()
            finally:
                cleanup_stdio_fd()
                for tx in (self._stdout_tx, self._stderr_tx):
                    with contextlib.suppress(Exception):
                        await tx.aclose()
                if self._process is not None:
                    with contextlib.suppress(ValueError):
                        self._process.close()
                self._run_cancel_scope = None
                self._done.set()

    async def stop(self) -> None:
        if self._run_cancel_scope is None and not self._done.is_set():
            raise RuntimeError("process has not been started")
        if self._run_cancel_scope is not None:
            self._run_cancel_scope.cancel()
        await self._done.wait()

    async def aclose(self) -> None:
        await self.stop()

    async def wait(self) -> int:
        if self._exitcode is not None:
            return self._exitcode

        await self._started.wait()
        if self._start_error is not None:
            raise self._start_error
        assert self._process is not None

        while True:
            exitcode = self.exitcode
            if exitcode is not None:
                return exitcode
            await sleep(0.01)

    @property
    def pid(self) -> int:
        if self._pid is None:
            raise RuntimeError("process has not been started")
        return self._pid

    @property
    def exitcode(self) -> int | None:
        if self._exitcode is not None:
            return self._exitcode
        if self._process is None:
            return None

        with contextlib.suppress(ValueError):
            exitcode = self._process.exitcode
            if exitcode is not None:
                self._exitcode = exitcode
            return exitcode
        return None

    def is_alive(self) -> bool:
        if self._process is None:
            return False

        with contextlib.suppress(ValueError):
            return self._process.is_alive()
        return False

    # TODO: maybe in the future if needed, create stdin that is also installed,
    #       and a ByteSendStream handle is provided for it :)

    @property
    def stdout(self) -> Receiver[bytes]:
        return self._stdout_rx

    @property
    def stderr(self) -> Receiver[bytes]:
        return self._stderr_rx

    async def _terminate_if_still_alive(self) -> None:
        process = self._process
        if process is None or self.exitcode is not None:
            return

        with contextlib.suppress(ValueError):
            await to_thread.run_sync(process.join, _JOIN_GRACE_SECONDS)
            if self.exitcode is not None or not process.is_alive():
                return

            logger.warning("Child process didn't shut down successfully, terminating")
            process.terminate()
            with move_on_after(_TERMINATE_GRACE_SECONDS):
                await self.wait()

            if self.exitcode is not None or not process.is_alive():
                logger.warning("Terminated nicely in the first attempt!")
                return

            for attempt in range(2, _TERMINATE_ATTEMPTS + 1):
                process.terminate()
                with move_on_after(_TERMINATE_RETRY_GRACE_SECONDS):
                    await self.wait()

                if self.exitcode is not None or not process.is_alive():
                    logger.warning(f"That took {attempt} attempts :)")
                    return

            logger.critical("Child process didn't respond to SIGTERM, killing")
            j = 0
            while True:
                process.kill()
                with move_on_after(_KILL_GRACE_SECONDS):
                    await self.wait()
                j += 1
                if self.exitcode is not None or not process.is_alive():
                    break
            logger.warning(f"That took {j} attempts :(")


# Spawn-mode multiprocessing requires a module-level target that can be pickled.
def _run_with_captured_stdio(
    stdout: _SupportsDetach,
    stderr: _SupportsDetach,
    target: Callable[..., object] | None,
    *target_args: object,
    **target_kwargs: object,
) -> None:
    stdout_fd = stdout.detach()
    stderr_fd = stderr.detach()

    try:
        os.dup2(stdout_fd, STDOUT_FD)
        os.dup2(stderr_fd, STDERR_FD)
    finally:
        for fd in (stdout_fd, stderr_fd):
            if fd not in STDIO_FDS:
                _close_fd(fd)

    faulthandler.enable(file=sys.stderr, all_threads=True)
    if target is not None:
        target(*target_args, **target_kwargs)


async def _drain_fd(fd: int, tx: Sender[bytes]) -> None:
    try:
        while True:
            await wait_readable(fd)
            chunk = os.read(fd, _READ_CHUNK_SIZE)
            if not chunk:
                return
            await tx.send(chunk)
    except (BrokenPipeError, BrokenResourceError, ClosedResourceError):
        pass
    finally:
        _close_fd(fd)
        await tx.aclose()


def _close_fd(fd: int | None) -> None:
    if fd is None:
        return
    with contextlib.suppress(OSError):
        os.close(fd)


if sys.platform == "win32":

    def _peek_named_pipe_chunk(fd: int) -> bytes | None:
        pipe_handle = msvcrt.get_osfhandle(fd)
        try:
            peek_result = _winapi.PeekNamedPipe(pipe_handle, 0)
        except OSError as error:
            if error.winerror == _winapi.ERROR_BROKEN_PIPE:
                return b""
            raise
        # CPython's actual runtime return for size=0 is always the 2-tuple
        # (available, bytes_left_this_message); the stub types it as a union
        # with the 3-tuple size>0 shape, so narrow by length to satisfy the
        # type checker instead of indexing blindly.
        if len(peek_result) != 2:
            raise RuntimeError(f"unexpected PeekNamedPipe(size=0) result: {peek_result!r}")
        available, _bytes_left_this_message = peek_result
        if available == 0:
            return None
        return os.read(fd, min(available, _READ_CHUNK_SIZE))

    async def _drain_fd_windows(fd: int, tx: Sender[bytes]) -> None:
        # abandon_on_cancel=False (unlike channels.py:269,348) shields this
        # wait, so cancellation blocks until the in-flight peek/read returns
        # rather than abandoning the worker thread. That's safe here because
        # each call is bounded (one non-blocking PeekNamedPipe plus a sized
        # os.read), and it guarantees no thread still touches fd when finally
        # closes it.
        limiter = CapacityLimiter(1)
        try:
            while True:
                chunk = await to_thread.run_sync(
                    _peek_named_pipe_chunk, fd, limiter=limiter, abandon_on_cancel=False
                )
                if chunk is None:
                    await sleep(_WINDOWS_PIPE_POLL_INTERVAL_SECONDS)
                    continue
                if not chunk:
                    return
                await tx.send(chunk)
        except (BrokenPipeError, BrokenResourceError, ClosedResourceError):
            pass
        finally:
            _close_fd(fd)
            await tx.aclose()

    def _fd_from_native_handle(handle: int) -> int:
        try:
            return msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
        except OSError:
            _winapi.CloseHandle(handle)
            raise

    def _rebuild_text_stream(
        fd: int, template: TextIO, *, line_buffered: bool
    ) -> io.TextIOWrapper:
        raw = io.FileIO(fd, mode="w", closefd=False)
        return io.TextIOWrapper(
            io.BufferedWriter(raw),
            encoding=template.encoding,
            errors=template.errors or "strict",
            newline="\n",
            line_buffering=line_buffered,
            write_through=line_buffered,
        )

    def _run_with_captured_stdio_windows(
        stdout_handle: int,
        stderr_handle: int,
        target: Callable[..., object] | None,
        *target_args: object,
        **target_kwargs: object,
    ) -> None:
        stdout_fd = _fd_from_native_handle(stdout_handle)
        stderr_fd = _fd_from_native_handle(stderr_handle)

        try:
            os.dup2(stdout_fd, STDOUT_FD)
            os.dup2(stderr_fd, STDERR_FD)
        finally:
            for fd in (stdout_fd, stderr_fd):
                if fd not in STDIO_FDS:
                    _close_fd(fd)

        old_stdout, old_stderr = sys.stdout, sys.stderr
        for old_stream in (old_stdout, old_stderr):
            with contextlib.suppress(Exception):
                old_stream.flush()

        # A parent launched from a real console gives the child TextIOWrapper
        # streams backed by _WindowsConsoleIO, which writes via WriteConsoleW.
        # After dup2 rewires fd 1/2 onto our pipe, WriteConsoleW is invalid for
        # that handle and print() raises instead of being captured
        # (https://bugs.python.org/issue30555). Unconditionally rebuild
        # stdout/stderr over a generic FileIO so they can never be
        # console-backed.
        sys.stdout = sys.__stdout__ = _rebuild_text_stream(
            STDOUT_FD, old_stdout, line_buffered=False
        )
        sys.stderr = sys.__stderr__ = _rebuild_text_stream(
            STDERR_FD, old_stderr, line_buffered=True
        )

        faulthandler.enable(file=sys.stderr, all_threads=True)
        if target is not None:
            target(*target_args, **target_kwargs)
