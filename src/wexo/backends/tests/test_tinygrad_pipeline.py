"""Pipeline hops between tinygrad ranks, in memory and over TCP."""

from __future__ import annotations

import socket
import threading
import time

import pytest

from wexo.backends.tinygrad_hidden_state import HiddenStateBuffer
from wexo.backends.tinygrad_pipeline import (
    PipelineHandshakeIdentity,
    PipelineTokenResult,
    TcpPipelineTransport,
    TinygradPipelineError,
    connect_memory_pipeline,
    encode_handshake_frame,
)
from wexo.backends.tinygrad_progress import TinygradProgressDeadlineError
from wexo.shared.types.common import Host
from wexo.utils.ports import random_ephemeral_port


class _ScriptedClock:
    def __init__(self, readings: tuple[float, ...]) -> None:
        self._readings = readings
        self._index = 0

    def __call__(self) -> float:
        reading = self._readings[self._index]
        if self._index + 1 < len(self._readings):
            self._index += 1
        return reading


def _identity(rank: int, model_id: str = "qwen") -> PipelineHandshakeIdentity:
    return PipelineHandshakeIdentity(
        instance_id="instance",
        device_rank=rank,
        world_size=2,
        model_id=model_id,
    )


def test_tcp_pipeline_round_trip() -> None:
    first_port = random_ephemeral_port()
    second_port = random_ephemeral_port()
    first = TcpPipelineTransport(
        device_rank=0,
        hosts=(
            Host(ip="0.0.0.0", port=first_port),
            Host(ip="127.0.0.1", port=second_port),
        ),
        identity=_identity(0),
    )
    second = TcpPipelineTransport(
        device_rank=1,
        hosts=(
            Host(ip="127.0.0.1", port=first_port),
            Host(ip="0.0.0.0", port=second_port),
        ),
        identity=_identity(1),
    )
    errors: list[BaseException] = []

    def open_second() -> None:
        try:
            second.open()
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=open_second)
    thread.start()
    try:
        first.open()
        thread.join(5)
        assert not thread.is_alive()
        assert errors == []
        hidden_state = HiddenStateBuffer(
            dtype="float32",
            shape=(1, 1, 1),
            data=b"\x00\x00\x80\x3f",
        )
        first.send_hidden_state("task", hidden_state)
        assert second.receive_hidden_state("task") == hidden_state
        result = PipelineTokenResult(
            token_id=3,
            text="a",
            finish_reason="length",
            prompt_token_count=1,
            completion_token_count=1,
        )
        second.send_token_result("task", result)
        assert first.receive_token_result("task") == result
    finally:
        first.close()
        second.close()
        thread.join(5)


def test_cancel_frame_unblocks_a_waiting_receive() -> None:
    transports = connect_memory_pipeline(2)
    delivered: list[HiddenStateBuffer | None] = []
    errors: list[BaseException] = []
    started = threading.Event()

    def wait_for_hidden() -> None:
        started.set()
        try:
            delivered.append(transports[1].receive_hidden_state("task"))
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=wait_for_hidden)
    thread.start()
    assert started.wait(2)
    time.sleep(0.1)
    transports[0].signal_cancellation("task")
    thread.join(2)
    assert not thread.is_alive()
    assert errors == []
    assert delivered == [None]


def test_handshake_rejects_a_different_model() -> None:
    first_port = random_ephemeral_port()
    second_port = random_ephemeral_port()
    ready = threading.Event()
    server_errors: list[BaseException] = []

    def serve() -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", second_port))
            listener.listen(1)
            listener.settimeout(5)
            ready.set()
            connection = listener.accept()[0]
            try:
                connection.sendall(encode_handshake_frame(_identity(1, "other-model")))
                connection.settimeout(2)
                _ = connection.recv(65536)
            finally:
                connection.close()
        except BaseException as error:
            server_errors.append(error)
        finally:
            listener.close()

    thread = threading.Thread(target=serve)
    thread.start()
    assert ready.wait(2)
    transport = TcpPipelineTransport(
        device_rank=0,
        hosts=(
            Host(ip="0.0.0.0", port=first_port),
            Host(ip="127.0.0.1", port=second_port),
        ),
        identity=_identity(0),
    )
    try:
        with pytest.raises(TinygradPipelineError, match="model does not match"):
            transport.open()
    finally:
        transport.close()
        thread.join(5)
    assert server_errors == []
    assert not thread.is_alive()


def test_transport_deadline_ends_a_silent_receive() -> None:
    transports = connect_memory_pipeline(2)
    transports[1].progress_clock = _ScriptedClock((0.0, 0.0, 10.0))
    transports[1].transport_budget_seconds = 1.0
    with pytest.raises(TinygradProgressDeadlineError, match="transport"):
        _ = transports[1].receive_hidden_state("task")
