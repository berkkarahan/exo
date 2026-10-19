import sys

from pytest import MonkeyPatch

from exo.main import Args


def test_zenoh_listener_defaults_to_an_ephemeral_port(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["exo"])

    assert Args.parse().zenoh_port == 0


def test_explicit_zenoh_listener_port_is_preserved(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["exo", "--zenoh-port", "52417"])

    assert Args.parse().zenoh_port == 52417
