"""Pipeline hop between adjacent tinygrad ranks.

Frames are length-prefixed. Hidden-state bytes stay raw. A single TCP
connection joins each rank to the next: hidden states travel forward and the
sampled token travels back. ``world_size == 1`` never constructs a transport.
"""

from __future__ import annotations

import array
import socket
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Literal, Protocol, final

from pydantic import Field, ValidationError

from wexo.backends.tinygrad_hidden_state import HiddenStateBuffer, HiddenStateDTypeName
from wexo.backends.tinygrad_progress import (
    DEFAULT_TINYGRAD_PROGRESS_BUDGETS,
    TinygradProgressDeadlineError,
    progress_is_overdue,
)
from wexo.shared.types.common import Host
from wexo.utils.pydantic_ext import FrozenModel

_KIND_HANDSHAKE = 1
_KIND_HIDDEN = 2
_KIND_TOKEN = 3
_KIND_CANCEL = 4
_KIND_REDUCE = 5
_MAX_FRAME_BYTES = 512 * 1024 * 1024
_HANDSHAKE_TIMEOUT_SECONDS = 30.0
_RECEIVE_POLL_SECONDS = 0.05
_DTYPE_CODE: dict[HiddenStateDTypeName, int] = {
    "float16": 0,
    "bfloat16": 1,
    "float32": 2,
}
_DTYPE_BY_CODE: dict[int, HiddenStateDTypeName] = {
    code: name for name, code in _DTYPE_CODE.items()
}
_DTYPE_ITEMSIZE: dict[HiddenStateDTypeName, int] = {
    "float16": 2,
    "bfloat16": 2,
    "float32": 4,
}
_FINISH_CODE: dict[Literal["stop", "length"] | None, int] = {
    None: 0,
    "stop": 1,
    "length": 2,
}
_FINISH_BY_CODE: dict[int, Literal["stop", "length"] | None] = {
    code: reason for reason, code in _FINISH_CODE.items()
}

type _FrameAction = Literal["payload", "cancelled", "ignore"]


@final
class TinygradPipelineError(Exception):
    """Raised when a pipeline peer cannot be reached or a frame is invalid.

    ``exo.worker.runner.bootstrap.entrypoint`` handles this by publishing
    ``RunnerTerminationError`` and exiting the runner.
    """


@final
class PipelineHandshakeIdentity(FrozenModel):
    """Identity exchanged before a tinygrad pipeline moves hidden states."""

    instance_id: str = Field(min_length=1)
    device_rank: int = Field(ge=0)
    world_size: int = Field(ge=2)
    model_id: str = Field(min_length=1)
    protocol: Literal["tinygrad-pipeline", "tinygrad-tensor"] = "tinygrad-pipeline"
    protocol_version: Literal[1] = 1


def encode_handshake_frame(identity: PipelineHandshakeIdentity) -> bytes:
    """Return the length-prefixed handshake frame for ``identity``."""
    payload = identity.model_dump_json().encode("utf-8")
    return encode_frame(_KIND_HANDSHAKE, "", payload)


def decode_handshake_identity(payload: bytes) -> PipelineHandshakeIdentity:
    """Parse a handshake payload.

    Raises:
        TinygradPipelineError: The runner entrypoint handles an unreadable
            payload by publishing ``RunnerTerminationError``.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TinygradPipelineError("Pipeline handshake identity is invalid") from error
    try:
        return PipelineHandshakeIdentity.model_validate_json(text)
    except ValidationError as error:
        raise TinygradPipelineError("Pipeline handshake identity is invalid") from error


def incompatible_handshake_reason(
    local: PipelineHandshakeIdentity,
    peer: PipelineHandshakeIdentity,
    expected_peer_rank: int,
) -> str | None:
    """Return why ``peer`` cannot join ``local``, or None when it can."""
    if (
        peer.protocol != local.protocol
        or peer.protocol_version != local.protocol_version
    ):
        return "Pipeline handshake protocol does not match"
    if peer.instance_id != local.instance_id:
        return "Pipeline handshake instance does not match"
    if peer.model_id != local.model_id:
        return "Pipeline handshake model does not match"
    if peer.world_size != local.world_size:
        return "Pipeline handshake world size does not match"
    if peer.device_rank != expected_peer_rank:
        return "Pipeline handshake rank does not match"
    return None


def raise_if_transport_overdue(
    *,
    started_at: float,
    now: float,
    budget_seconds: float,
) -> None:
    """Raise when a pipeline receive has waited longer than its budget.

    Raises:
        TinygradProgressDeadlineError: The runner entrypoint handles this by
            publishing ``RunnerTerminationError``.
    """
    if progress_is_overdue(started_at, now, budget_seconds):
        raise TinygradProgressDeadlineError("transport", budget_seconds)


@final
class PipelineTokenResult(FrozenModel):
    """Sampled token carried from the last rank back to rank 0."""

    token_id: int
    text: str
    finish_reason: Literal["stop", "length"] | None
    prompt_token_count: int
    completion_token_count: int


@final
@dataclass(frozen=True)
class _PipelineFrame:
    kind: int
    task_id: str
    payload: bytes


@final
@dataclass(frozen=True)
class _InterpretedFrame:
    action: _FrameAction
    payload: bytes = b""


class PipelineTransport(Protocol):
    """Sockets or queues that move one pipeline step between two ranks."""

    cancellation_probe: Callable[[], bool]
    progress_clock: Callable[[], float]
    transport_budget_seconds: float

    def open(self) -> None:
        """Connect to the neighbouring ranks and exchange a handshake."""
        ...

    def close(self) -> None:
        """Release sockets or mark the in-memory hop closed."""
        ...

    def is_open(self) -> bool:
        """Return whether ``open`` has finished and ``close`` has not."""
        ...

    def send_hidden_state(self, task_id: str, hidden_state: HiddenStateBuffer) -> None:
        """Send one hidden state to the next rank."""
        ...

    def receive_hidden_state(self, task_id: str) -> HiddenStateBuffer | None:
        """Return the next hidden state, or None when the step is cancelled."""
        ...

    def send_token_result(self, task_id: str, result: PipelineTokenResult) -> None:
        """Send one sampled token to the previous rank."""
        ...

    def receive_token_result(self, task_id: str) -> PipelineTokenResult | None:
        """Return the sampled token, or None when the step is cancelled."""
        ...

    def signal_cancellation(self, task_id: str) -> None:
        """Tell both neighbours to leave a blocked receive."""
        ...

    def all_reduce_sum(
        self, task_id: str, hidden_state: HiddenStateBuffer
    ) -> HiddenStateBuffer:
        """Sum ``hidden_state`` along the rank chain.

        Every rank must call this once per partial, in the same order. The
        return value is the sum on every rank.
        """
        ...


def _never_cancelled() -> bool:
    return False


def encode_frame(kind: int, task_id: str, payload: bytes) -> bytes:
    """Return one length-prefixed frame.

    Raises:
        TinygradPipelineError: The runner entrypoint handles a frame larger
            than the receive limit by publishing ``RunnerTerminationError``.
    """
    task_bytes = task_id.encode("utf-8")
    if len(task_bytes) > 0xFFFF:
        raise TinygradPipelineError("Pipeline task id is too long")
    body = bytes([kind]) + len(task_bytes).to_bytes(2, "little") + task_bytes + payload
    if len(body) > _MAX_FRAME_BYTES:
        raise TinygradPipelineError("Pipeline frame exceeds the receive limit")
    return len(body).to_bytes(4, "little") + body


def _decode_body(body: bytes) -> _PipelineFrame:
    if len(body) < 3:
        raise TinygradPipelineError("Pipeline frame is truncated")
    kind = body[0]
    task_length = int.from_bytes(body[1:3], "little")
    if len(body) < 3 + task_length:
        raise TinygradPipelineError("Pipeline frame is truncated")
    try:
        task_id = body[3 : 3 + task_length].decode("utf-8")
    except UnicodeDecodeError as error:
        raise TinygradPipelineError("Pipeline task id is not utf-8") from error
    return _PipelineFrame(kind=kind, task_id=task_id, payload=body[3 + task_length :])


def decode_complete_frame(frame: bytes) -> _PipelineFrame:
    """Decode one buffer that already holds a single length-prefixed frame.

    Raises:
        TinygradPipelineError: The runner entrypoint handles a truncated or
            oversized frame by publishing ``RunnerTerminationError``.
    """
    if len(frame) < 4:
        raise TinygradPipelineError("Pipeline frame is truncated")
    length = int.from_bytes(frame[:4], "little")
    if length > _MAX_FRAME_BYTES:
        raise TinygradPipelineError("Pipeline frame exceeds the receive limit")
    if length != len(frame) - 4:
        raise TinygradPipelineError("Pipeline frame length does not match its body")
    return _decode_body(frame[4:])


def _take_frame(buffer: bytearray) -> _PipelineFrame | None:
    if len(buffer) < 4:
        return None
    length = int.from_bytes(buffer[:4], "little")
    if length > _MAX_FRAME_BYTES:
        raise TinygradPipelineError("Pipeline frame exceeds the receive limit")
    if len(buffer) < 4 + length:
        return None
    body = bytes(buffer[4 : 4 + length])
    del buffer[: 4 + length]
    return _decode_body(body)


def encode_hidden_state(hidden_state: HiddenStateBuffer) -> bytes:
    """Pack dtype, shape, and raw bytes without base64."""
    shape = hidden_state.shape
    if len(shape) > 8:
        raise TinygradPipelineError("Hidden state rank is too high to frame")
    body = bytes([_DTYPE_CODE[hidden_state.dtype], len(shape)])
    for dimension in shape:
        if dimension < 0 or dimension > 0xFFFFFFFF:
            raise TinygradPipelineError("Hidden state dimension does not fit a frame")
        body += dimension.to_bytes(4, "little")
    return body + hidden_state.data


def decode_hidden_state(payload: bytes) -> HiddenStateBuffer:
    """Reverse ``encode_hidden_state``.

    Raises:
        TinygradPipelineError: The runner entrypoint handles a payload whose
            bytes do not match the declared shape.
    """
    if len(payload) < 2:
        raise TinygradPipelineError("Hidden-state frame is truncated")
    dtype_name = _DTYPE_BY_CODE.get(payload[0])
    rank = payload[1]
    if dtype_name is None or rank > 8:
        raise TinygradPipelineError("Hidden-state frame has an unknown dtype")
    header = 2 + 4 * rank
    if len(payload) < header:
        raise TinygradPipelineError("Hidden-state frame is truncated")
    shape = tuple(
        int.from_bytes(payload[2 + 4 * index : 6 + 4 * index], "little")
        for index in range(rank)
    )
    data = payload[header:]
    expected = 1
    for dimension in shape:
        expected *= dimension
    expected *= _DTYPE_ITEMSIZE[dtype_name]
    if len(data) != expected:
        raise TinygradPipelineError(
            f"Hidden state has {len(data)} bytes, expected {expected}"
        )
    return HiddenStateBuffer(dtype=dtype_name, shape=shape, data=data)


def encode_token_result(result: PipelineTokenResult) -> bytes:
    """Pack a sampled token without putting it on the JSON event bus."""
    text = result.text.encode("utf-8")
    if len(text) > 0xFFFFFFFF:
        raise TinygradPipelineError("Pipeline token text exceeds the frame limit")
    finish_code = _FINISH_CODE[result.finish_reason]
    return (
        result.token_id.to_bytes(4, "little", signed=True)
        + bytes([finish_code])
        + result.prompt_token_count.to_bytes(4, "little")
        + result.completion_token_count.to_bytes(4, "little")
        + len(text).to_bytes(4, "little")
        + text
    )


def decode_token_result(payload: bytes) -> PipelineTokenResult:
    """Reverse ``encode_token_result``.

    Raises:
        TinygradPipelineError: The runner entrypoint handles a truncated
            token frame by publishing ``RunnerTerminationError``.
    """
    if len(payload) < 17:
        raise TinygradPipelineError("Token frame is truncated")
    token_id = int.from_bytes(payload[0:4], "little", signed=True)
    finish_reason = _FINISH_BY_CODE.get(payload[4])
    if payload[4] not in _FINISH_BY_CODE:
        raise TinygradPipelineError("Token frame has an unknown finish reason")
    prompt_token_count = int.from_bytes(payload[5:9], "little")
    completion_token_count = int.from_bytes(payload[9:13], "little")
    text_length = int.from_bytes(payload[13:17], "little")
    text_bytes = payload[17:]
    if len(text_bytes) != text_length:
        raise TinygradPipelineError("Token frame text length does not match")
    try:
        text = text_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TinygradPipelineError("Token frame text is not utf-8") from error
    return PipelineTokenResult(
        token_id=token_id,
        text=text,
        finish_reason=finish_reason,
        prompt_token_count=prompt_token_count,
        completion_token_count=completion_token_count,
    )


def _interpret_frame(
    frame: _PipelineFrame,
    *,
    expected_kind: int,
    task_id: str,
    allow_payload: bool,
    signal: Callable[[str], None],
) -> _InterpretedFrame:
    """Classify one frame for the rank that is currently blocked.

    Frames for a different task are ignored so a cancel left from the
    previous request cannot finish the next one. A cancel for this task is
    forwarded to the other neighbour before the receive returns.
    """
    if frame.task_id != task_id:
        return _InterpretedFrame(action="ignore")
    if frame.kind == _KIND_CANCEL:
        signal(task_id)
        return _InterpretedFrame(action="cancelled")
    if not allow_payload or frame.kind != expected_kind:
        raise TinygradPipelineError("Unexpected pipeline frame")
    return _InterpretedFrame(action="payload", payload=frame.payload)


@final
class _SocketReader:
    """Accumulate bytes from one socket until a full frame is present."""

    def __init__(self, connection: socket.socket) -> None:
        self._connection = connection
        self._buffer = bytearray()

    def read_frame(self, timeout: float) -> _PipelineFrame | None:
        """Return one frame, or None if ``timeout`` elapses first.

        Raises:
            TinygradPipelineError: The runner entrypoint handles a peer that
                closes the connection or sends an oversized frame.
        """
        self._connection.settimeout(0.0 if timeout == 0 else timeout)
        while True:
            framed = _take_frame(self._buffer)
            if framed is not None:
                return framed
            try:
                chunk = self._connection.recv(65536)
            except (BlockingIOError, TimeoutError):
                return None
            except OSError as error:
                raise TinygradPipelineError(
                    "Tinygrad pipeline peer closed the connection"
                ) from error
            if chunk == b"":
                raise TinygradPipelineError(
                    "Tinygrad pipeline peer closed the connection"
                )
            self._buffer.extend(chunk)


def _send_all(connection: socket.socket, payload: bytes) -> None:
    view = memoryview(payload)
    sent = 0
    while sent < len(view):
        try:
            count = connection.send(view[sent:])
        except OSError as error:
            raise TinygradPipelineError("Tinygrad pipeline send failed") from error
        if count == 0:
            raise TinygradPipelineError("Tinygrad pipeline send failed")
        sent += count


def _configure_connection(connection: socket.socket) -> None:
    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    connection.settimeout(None)


def _is_unconnected_host(host: Host) -> bool:
    return host.ip == "198.51.100.1" or host.port == 0


@final
@dataclass
class PipelineMemoryLink:
    """One bidirectional queue pair between rank ``i`` and rank ``i + 1``."""

    forward: Queue[bytes]
    backward: Queue[bytes]


def sum_hidden_states(
    left: HiddenStateBuffer, right: HiddenStateBuffer
) -> HiddenStateBuffer:
    """Add two float32 hidden states elementwise.

    Raises:
        TinygradPipelineError: The runner entrypoint handles a collective
            whose peers produced different shapes or a non-float32 payload.
    """
    if left.dtype != "float32" or right.dtype != "float32":
        raise TinygradPipelineError("Tensor parallel all-reduce expects float32")
    if left.shape != right.shape or len(left.data) != len(right.data):
        raise TinygradPipelineError("Tensor parallel ranks reduced different shapes")
    first: array.array[float] = array.array("f")
    second: array.array[float] = array.array("f")
    first.frombytes(left.data)
    second.frombytes(right.data)
    if len(first) != len(second):
        raise TinygradPipelineError("Tensor parallel ranks reduced different shapes")
    total: array.array[float] = array.array(
        "f", (item + peer for item, peer in zip(first, second, strict=True))
    )
    return HiddenStateBuffer(dtype="float32", shape=left.shape, data=total.tobytes())


def _all_reduce_sum(
    *,
    device_rank: int,
    world_size: int,
    hidden_state: HiddenStateBuffer,
    send_to_next: Callable[[HiddenStateBuffer], None],
    receive_from_previous: Callable[[], HiddenStateBuffer | None],
    send_to_previous: Callable[[HiddenStateBuffer], None],
    receive_from_next: Callable[[], HiddenStateBuffer | None],
) -> HiddenStateBuffer:
    """Sum one tensor along a chain and return that sum on every rank.

    Rank 0 starts the partial. Each later rank adds its own partial and
    forwards the running total. The last rank sends the sum back down the
    same links.

    Raises:
        TinygradPipelineError: The runner entrypoint handles a cancelled
            receive or a chain that was opened for a single rank.
    """
    if world_size < 2:
        raise TinygradPipelineError(
            "Tensor parallel all-reduce needs at least two ranks"
        )
    partial = hidden_state
    if device_rank > 0:
        received = receive_from_previous()
        if received is None:
            raise TinygradPipelineError("Tensor parallel collective was cancelled")
        partial = sum_hidden_states(partial, received)
    if device_rank + 1 < world_size:
        send_to_next(partial)
        total = receive_from_next()
        if total is None:
            raise TinygradPipelineError("Tensor parallel collective was cancelled")
    else:
        total = partial
    if device_rank > 0:
        send_to_previous(total)
    return total


def connect_memory_pipeline(world_size: int) -> list[InMemoryPipelineTransport]:
    """Pair in-memory hops for a test that runs every rank in one process.

    Raises:
        TinygradPipelineError: A caller asked for a single rank. Tests fail
            immediately instead of pretending a hop exists.
    """
    if world_size < 2:
        raise TinygradPipelineError(
            "An in-memory tinygrad pipeline needs at least two ranks"
        )
    links = [
        PipelineMemoryLink(forward=Queue(), backward=Queue())
        for _link in range(world_size - 1)
    ]
    return [
        InMemoryPipelineTransport(device_rank=rank, links=links)
        for rank in range(world_size)
    ]


@final
class InMemoryPipelineTransport:
    """Queue-backed hop used by tests. ``open`` does not touch the network."""

    def __init__(self, device_rank: int, links: Sequence[PipelineMemoryLink]) -> None:
        self.device_rank = device_rank
        self._links = links
        self.cancellation_probe: Callable[[], bool] = _never_cancelled
        self.progress_clock: Callable[[], float] = time.monotonic
        self.transport_budget_seconds = (
            DEFAULT_TINYGRAD_PROGRESS_BUDGETS.transport_seconds
        )
        self._signalled_task_ids: set[str] = set()
        self._closed = False

    def open(self) -> None:
        self._closed = False

    def close(self) -> None:
        self._closed = True

    def is_open(self) -> bool:
        return not self._closed

    def send_hidden_state(self, task_id: str, hidden_state: HiddenStateBuffer) -> None:
        link = self._link_to_next()
        link.forward.put(
            encode_frame(_KIND_HIDDEN, task_id, encode_hidden_state(hidden_state))
        )

    def receive_hidden_state(self, task_id: str) -> HiddenStateBuffer | None:
        payload = self._receive(
            primary=self._link_from_previous().forward,
            secondary=self._optional_backward_from_next(),
            expected_kind=_KIND_HIDDEN,
            task_id=task_id,
        )
        if payload is None:
            return None
        return decode_hidden_state(payload)

    def send_token_result(self, task_id: str, result: PipelineTokenResult) -> None:
        link = self._link_from_previous()
        link.backward.put(
            encode_frame(_KIND_TOKEN, task_id, encode_token_result(result))
        )

    def receive_token_result(self, task_id: str) -> PipelineTokenResult | None:
        payload = self._receive(
            primary=self._link_to_next().backward,
            secondary=self._optional_forward_from_previous(),
            expected_kind=_KIND_TOKEN,
            task_id=task_id,
        )
        if payload is None:
            return None
        return decode_token_result(payload)

    def signal_cancellation(self, task_id: str) -> None:
        if task_id in self._signalled_task_ids:
            return
        self._signalled_task_ids.add(task_id)
        frame = encode_frame(_KIND_CANCEL, task_id, b"")
        if self.device_rank < len(self._links):
            self._links[self.device_rank].forward.put(frame)
        if self.device_rank > 0:
            self._links[self.device_rank - 1].backward.put(frame)

    def all_reduce_sum(
        self, task_id: str, hidden_state: HiddenStateBuffer
    ) -> HiddenStateBuffer:
        return _all_reduce_sum(
            device_rank=self.device_rank,
            world_size=len(self._links) + 1,
            hidden_state=hidden_state,
            send_to_next=lambda payload: self._send_reduce(
                to_next=True, task_id=task_id, payload=payload
            ),
            receive_from_previous=lambda: self._receive_reduce(
                from_previous=True, task_id=task_id
            ),
            send_to_previous=lambda payload: self._send_reduce(
                to_next=False, task_id=task_id, payload=payload
            ),
            receive_from_next=lambda: self._receive_reduce(
                from_previous=False, task_id=task_id
            ),
        )

    def _send_reduce(
        self, *, to_next: bool, task_id: str, payload: HiddenStateBuffer
    ) -> None:
        link = self._link_to_next() if to_next else self._link_from_previous()
        channel = link.forward if to_next else link.backward
        channel.put(encode_frame(_KIND_REDUCE, task_id, encode_hidden_state(payload)))

    def _receive_reduce(
        self, *, from_previous: bool, task_id: str
    ) -> HiddenStateBuffer | None:
        if from_previous:
            payload = self._receive(
                primary=self._link_from_previous().forward,
                secondary=self._optional_backward_from_next(),
                expected_kind=_KIND_REDUCE,
                task_id=task_id,
            )
        else:
            payload = self._receive(
                primary=self._link_to_next().backward,
                secondary=self._optional_forward_from_previous(),
                expected_kind=_KIND_REDUCE,
                task_id=task_id,
            )
        if payload is None:
            return None
        return decode_hidden_state(payload)

    def _link_to_next(self) -> PipelineMemoryLink:
        if self.device_rank >= len(self._links):
            raise TinygradPipelineError(
                "The last tinygrad pipeline rank has no next peer"
            )
        return self._links[self.device_rank]

    def _link_from_previous(self) -> PipelineMemoryLink:
        if self.device_rank == 0:
            raise TinygradPipelineError(
                "The first tinygrad pipeline rank has no previous peer"
            )
        return self._links[self.device_rank - 1]

    def _optional_backward_from_next(self) -> Queue[bytes] | None:
        if self.device_rank >= len(self._links):
            return None
        return self._links[self.device_rank].backward

    def _optional_forward_from_previous(self) -> Queue[bytes] | None:
        if self.device_rank == 0:
            return None
        return self._links[self.device_rank - 1].forward

    def _receive(
        self,
        *,
        primary: Queue[bytes],
        secondary: Queue[bytes] | None,
        expected_kind: int,
        task_id: str,
    ) -> bytes | None:
        started_at = self.progress_clock()
        while True:
            if self.cancellation_probe():
                self.signal_cancellation(task_id)
                return None
            raise_if_transport_overdue(
                started_at=started_at,
                now=self.progress_clock(),
                budget_seconds=self.transport_budget_seconds,
            )
            interpreted = self._poll_queue(secondary, expected_kind, task_id, False)
            if interpreted is not None:
                if interpreted.action == "cancelled":
                    return None
                if interpreted.action == "payload":
                    return interpreted.payload
            interpreted = self._poll_queue(primary, expected_kind, task_id, True)
            if interpreted is not None:
                if interpreted.action == "cancelled":
                    return None
                if interpreted.action == "payload":
                    return interpreted.payload
                continue
            try:
                encoded = primary.get(timeout=_RECEIVE_POLL_SECONDS)
            except Empty:
                continue
            interpreted = _interpret_frame(
                decode_complete_frame(encoded),
                expected_kind=expected_kind,
                task_id=task_id,
                allow_payload=True,
                signal=self.signal_cancellation,
            )
            if interpreted.action == "ignore":
                continue
            if interpreted.action == "cancelled":
                return None
            return interpreted.payload

    def _poll_queue(
        self,
        channel: Queue[bytes] | None,
        expected_kind: int,
        task_id: str,
        allow_payload: bool,
    ) -> _InterpretedFrame | None:
        if channel is None:
            return None
        try:
            encoded = channel.get_nowait()
        except Empty:
            return None
        return _interpret_frame(
            decode_complete_frame(encoded),
            expected_kind=expected_kind,
            task_id=task_id,
            allow_payload=allow_payload,
            signal=self.signal_cancellation,
        )


@final
class TcpPipelineTransport:
    """Length-prefixed TCP hop. ``open`` handshakes before weights load."""

    def __init__(
        self,
        device_rank: int,
        hosts: Sequence[Host],
        identity: PipelineHandshakeIdentity,
    ) -> None:
        if device_rank < 0 or device_rank >= len(hosts):
            raise TinygradPipelineError(
                f"Tinygrad pipeline rank {device_rank} is outside its host list"
            )
        if identity.device_rank != device_rank:
            raise TinygradPipelineError(
                "Pipeline handshake rank does not match this transport"
            )
        if identity.world_size != len(hosts):
            raise TinygradPipelineError(
                "Pipeline handshake world size does not match the host list"
            )
        self.device_rank = device_rank
        self._hosts = hosts
        self._identity = identity
        self.cancellation_probe: Callable[[], bool] = _never_cancelled
        self.progress_clock: Callable[[], float] = time.monotonic
        self.transport_budget_seconds = (
            DEFAULT_TINYGRAD_PROGRESS_BUDGETS.transport_seconds
        )
        self._signalled_task_ids: set[str] = set()
        self._listener: socket.socket | None = None
        self._to_next: socket.socket | None = None
        self._from_previous: socket.socket | None = None
        self._readers: dict[socket.socket, _SocketReader] = {}
        self._is_open = False

    def open(self) -> None:
        """Bind this rank and handshake with the previous and next ranks.

        Raises:
            TinygradPipelineError: The runner entrypoint handles a peer that
                never accepts the handshake. Placement has already failed when
                a neighbour address is missing.
        """
        if self._is_open:
            return
        bind_host = self._hosts[self.device_rank]
        if bind_host.port == 0:
            raise TinygradPipelineError("Tinygrad pipeline rank has no listen port")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((bind_host.ip, bind_host.port))
        except OSError as error:
            listener.close()
            raise TinygradPipelineError(
                f"Tinygrad pipeline rank could not bind {bind_host}"
            ) from error
        listener.listen(1)
        self._listener = listener
        deadline = time.monotonic() + _HANDSHAKE_TIMEOUT_SECONDS
        try:
            if self.device_rank + 1 < len(self._hosts):
                self._to_next = self._connect_until(
                    self._hosts[self.device_rank + 1], deadline
                )
                self._readers[self._to_next] = _SocketReader(self._to_next)
                self._exchange_handshake(self._to_next, deadline, self.device_rank + 1)
            if self.device_rank > 0:
                self._from_previous = self._accept_until(listener, deadline)
                self._readers[self._from_previous] = _SocketReader(self._from_previous)
                self._exchange_handshake(
                    self._from_previous, deadline, self.device_rank - 1
                )
        except TinygradPipelineError:
            self.close()
            raise
        self._is_open = True

    def close(self) -> None:
        self._is_open = False
        for connection in (self._to_next, self._from_previous, self._listener):
            if connection is None:
                continue
            try:
                connection.close()
            except OSError:
                # Close is cleanup. A peer that already hung up is still closed
                # locally, so the runner can exit the generation loop.
                continue
        self._to_next = None
        self._from_previous = None
        self._listener = None
        self._readers.clear()

    def is_open(self) -> bool:
        return self._is_open

    def send_hidden_state(self, task_id: str, hidden_state: HiddenStateBuffer) -> None:
        connection = self._require_next()
        _send_all(
            connection,
            encode_frame(_KIND_HIDDEN, task_id, encode_hidden_state(hidden_state)),
        )

    def receive_hidden_state(self, task_id: str) -> HiddenStateBuffer | None:
        payload = self._receive(self._require_previous(), _KIND_HIDDEN, task_id)
        if payload is None:
            return None
        return decode_hidden_state(payload)

    def send_token_result(self, task_id: str, result: PipelineTokenResult) -> None:
        connection = self._require_previous()
        _send_all(
            connection,
            encode_frame(_KIND_TOKEN, task_id, encode_token_result(result)),
        )

    def receive_token_result(self, task_id: str) -> PipelineTokenResult | None:
        payload = self._receive(self._require_next(), _KIND_TOKEN, task_id)
        if payload is None:
            return None
        return decode_token_result(payload)

    def signal_cancellation(self, task_id: str) -> None:
        if task_id in self._signalled_task_ids:
            return
        self._signalled_task_ids.add(task_id)
        frame = encode_frame(_KIND_CANCEL, task_id, b"")
        for connection in (self._to_next, self._from_previous):
            if connection is None:
                continue
            try:
                _send_all(connection, frame)
            except TinygradPipelineError:
                # The neighbour is already gone. This rank still has to leave
                # its own receive, so a failed cancel send is not fatal.
                continue

    def all_reduce_sum(
        self, task_id: str, hidden_state: HiddenStateBuffer
    ) -> HiddenStateBuffer:
        return _all_reduce_sum(
            device_rank=self.device_rank,
            world_size=len(self._hosts),
            hidden_state=hidden_state,
            send_to_next=lambda payload: self._send_reduce(
                self._require_next(), task_id, payload
            ),
            receive_from_previous=lambda: self._receive_reduce(
                self._require_previous(), task_id
            ),
            send_to_previous=lambda payload: self._send_reduce(
                self._require_previous(), task_id, payload
            ),
            receive_from_next=lambda: self._receive_reduce(
                self._require_next(), task_id
            ),
        )

    def _send_reduce(
        self, connection: socket.socket, task_id: str, payload: HiddenStateBuffer
    ) -> None:
        _send_all(
            connection,
            encode_frame(_KIND_REDUCE, task_id, encode_hidden_state(payload)),
        )

    def _receive_reduce(
        self, connection: socket.socket, task_id: str
    ) -> HiddenStateBuffer | None:
        payload = self._receive(connection, _KIND_REDUCE, task_id)
        if payload is None:
            return None
        return decode_hidden_state(payload)

    def _require_next(self) -> socket.socket:
        connection = self._to_next
        if connection is None or not self._is_open:
            raise TinygradPipelineError(
                "The last tinygrad pipeline rank has no next peer"
            )
        return connection

    def _require_previous(self) -> socket.socket:
        connection = self._from_previous
        if connection is None or not self._is_open:
            raise TinygradPipelineError(
                "The first tinygrad pipeline rank has no previous peer"
            )
        return connection

    def _secondary(self, primary: socket.socket) -> socket.socket | None:
        if primary is self._to_next:
            return self._from_previous
        return self._to_next

    def _receive(
        self, primary: socket.socket, expected_kind: int, task_id: str
    ) -> bytes | None:
        secondary = self._secondary(primary)
        started_at = self.progress_clock()
        while True:
            if self.cancellation_probe():
                self.signal_cancellation(task_id)
                return None
            raise_if_transport_overdue(
                started_at=started_at,
                now=self.progress_clock(),
                budget_seconds=self.transport_budget_seconds,
            )
            for connection, allow_payload in (
                (secondary, False),
                (primary, True),
            ):
                if connection is None:
                    continue
                frame = self._readers[connection].read_frame(0)
                if frame is None:
                    continue
                interpreted = _interpret_frame(
                    frame,
                    expected_kind=expected_kind,
                    task_id=task_id,
                    allow_payload=allow_payload,
                    signal=self.signal_cancellation,
                )
                if interpreted.action == "ignore":
                    continue
                if interpreted.action == "cancelled":
                    return None
                return interpreted.payload
            frame = self._readers[primary].read_frame(_RECEIVE_POLL_SECONDS)
            if frame is None:
                continue
            interpreted = _interpret_frame(
                frame,
                expected_kind=expected_kind,
                task_id=task_id,
                allow_payload=True,
                signal=self.signal_cancellation,
            )
            if interpreted.action == "ignore":
                continue
            if interpreted.action == "cancelled":
                return None
            return interpreted.payload

    def _connect_until(self, host: Host, deadline: float) -> socket.socket:
        if _is_unconnected_host(host):
            raise TinygradPipelineError(
                f"Tinygrad pipeline rank {self.device_rank + 1} has no address"
            )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TinygradPipelineError(
                    f"Timed out connecting to tinygrad pipeline peer {host}"
                )
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection.settimeout(min(0.2, remaining))
            try:
                connection.connect((host.ip, host.port))
            except (TimeoutError, OSError):
                connection.close()
                continue
            _configure_connection(connection)
            return connection

    def _accept_until(self, listener: socket.socket, deadline: float) -> socket.socket:
        listener.settimeout(0.2)
        while True:
            if time.monotonic() >= deadline:
                raise TinygradPipelineError(
                    "Timed out accepting a tinygrad pipeline peer"
                )
            try:
                connection = listener.accept()[0]
            except TimeoutError:
                continue
            _configure_connection(connection)
            return connection

    def _exchange_handshake(
        self,
        connection: socket.socket,
        deadline: float,
        expected_peer_rank: int,
    ) -> None:
        _send_all(connection, encode_handshake_frame(self._identity))
        reader = self._readers[connection]
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TinygradPipelineError(
                    "Timed out waiting for a tinygrad pipeline handshake"
                )
            frame = reader.read_frame(min(remaining, 0.2))
            if frame is None:
                continue
            if frame.kind != _KIND_HANDSHAKE:
                raise TinygradPipelineError(
                    "Pipeline handshake received an unexpected frame"
                )
            peer = decode_handshake_identity(frame.payload)
            reason = incompatible_handshake_reason(
                self._identity, peer, expected_peer_rank
            )
            if reason is not None:
                raise TinygradPipelineError(reason)
            return
