import signal
from collections.abc import Callable

import pytest
from exo_tools import cluster
from pytest import MonkeyPatch


@pytest.mark.parametrize("has_hangup_signal", [False, True])
def test_session_registers_only_available_cleanup_signals(
    monkeypatch: MonkeyPatch, has_hangup_signal: bool
) -> None:
    registered_handlers: dict[int, object] = {}
    exit_handlers: list[Callable[[], None]] = []

    def register_signal(signal_number: int, handler: object) -> None:
        registered_handlers[signal_number] = handler

    def register_exit(handler: Callable[[], None]) -> Callable[[], None]:
        exit_handlers.append(handler)
        return handler

    monkeypatch.setattr(cluster.signal, "signal", register_signal)
    monkeypatch.setattr(cluster.atexit, "register", register_exit)
    if has_hangup_signal:
        monkeypatch.setattr(cluster.signal, "SIGHUP", 1, raising=False)
    else:
        monkeypatch.delattr(cluster.signal, "SIGHUP", raising=False)

    session = cluster.EcoSession(user_prefix="test-signals")

    assert set(registered_handlers) == (
        {signal.SIGTERM, 1} if has_hangup_signal else {signal.SIGTERM}
    )
    assert signal.SIGINT not in registered_handlers
    assert exit_handlers == [session.stop_all]

    stopped: list[bool] = []

    def stop_all() -> None:
        stopped.append(True)

    monkeypatch.setattr(session, "stop_all", stop_all)
    handler = registered_handlers[signal.SIGTERM]
    assert callable(handler)
    with pytest.raises(SystemExit) as error:
        handler(signal.SIGTERM, None)
    assert error.value.code == 128 + signal.SIGTERM
    assert stopped == [True]
