"""Durable-event replay on master startup."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from exo.master.main import Master
from exo.routing.router import get_node_zid
from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.types.backends import Backend
from exo.shared.types.commands import ForwarderCommand, ForwarderDownloadCommand
from exo.shared.types.common import ModelId, SessionId
from exo.shared.types.events import (
    CustomModelCardAdded,
    CustomModelCardDeleted,
    Event,
    GlobalForwarderEvent,
    LocalForwarderEvent,
    NodeGatheredInfo,
)
from exo.shared.types.memory import Memory
from exo.shared.types.profiling import MemoryUsage
from exo.utils.channels import Receiver, channel
from exo.utils.disk_event_log import DiskEventLog


def _card(model_id: str) -> ModelCard:
    return ModelCard(
        model_id=ModelId(model_id),
        storage_size=Memory.from_bytes(1024),
        n_layers=4,
        hidden_size=64,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.TinygradMetal],
        is_custom=True,
    )


def _build_master(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> tuple[Master, Receiver[GlobalForwarderEvent]]:
    monkeypatch.setattr("exo.master.main.EXO_EVENT_LOG_DIR", tmp_path / "event_log")
    node_id = get_node_zid()
    session_id = SessionId(master_node_id=node_id, election_clock=1)
    global_sender, global_receiver = channel[GlobalForwarderEvent]()
    command_sender, command_receiver = channel[ForwarderCommand]()
    _ = command_sender
    local_sender, local_receiver = channel[LocalForwarderEvent]()
    _ = local_sender
    download_sender, download_receiver = channel[ForwarderDownloadCommand]()
    _ = download_receiver
    event_sender, _event_receiver = channel[Event]()
    master = Master(
        node_id,
        session_id,
        event_sender=event_sender,
        global_event_sender=global_sender,
        local_event_receiver=local_receiver,
        command_receiver=command_receiver,
        download_command_sender=download_sender,
    )
    return master, global_receiver


@pytest.mark.asyncio
async def test_replay_restores_custom_cards_and_skips_ephemeral(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    log_dir = tmp_path / "event_log" / "master"
    writer = DiskEventLog(log_dir)
    card = _card("org/gguf-model")
    writer.append(CustomModelCardAdded(model_card=card))
    writer.append(
        NodeGatheredInfo(
            when=str(datetime.now(tz=timezone.utc)),
            node_id=get_node_zid(),
            info=MemoryUsage(
                ram_total=Memory.from_bytes(1024),
                ram_available=Memory.from_bytes(512),
                swap_total=Memory.from_bytes(0),
                swap_available=Memory.from_bytes(0),
            ),
        )
    )
    writer.close()

    master, global_receiver = _build_master(tmp_path, monkeypatch)

    await master._replay_durable_events()  # pyright: ignore[reportPrivateUsage]

    assert ModelId("org/gguf-model") in master.state.custom_model_cards
    # Ephemeral events are not replayed.
    assert master.state.node_memory == {}
    # Durable events are re-broadcast for the worker and API.
    broadcast = [event.event for event in global_receiver.collect()]
    assert any(isinstance(event, CustomModelCardAdded) for event in broadcast)


@pytest.mark.asyncio
async def test_replay_honours_delete_after_add(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    log_dir = tmp_path / "event_log" / "master"
    writer = DiskEventLog(log_dir)
    card = _card("org/removed-model")
    writer.append(CustomModelCardAdded(model_card=card))
    writer.append(CustomModelCardDeleted(model_id=card.model_id))
    writer.close()

    master, _ = _build_master(tmp_path, monkeypatch)

    await master._replay_durable_events()  # pyright: ignore[reportPrivateUsage]

    assert master.state.custom_model_cards == {}


@pytest.mark.asyncio
async def test_replay_dedups_repeated_events(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    log_dir = tmp_path / "event_log" / "master"
    writer = DiskEventLog(log_dir)
    card = _card("org/dup-model")
    event = CustomModelCardAdded(model_card=card)
    writer.append(event)
    writer.append(event)  # same event_id, re-appended across restarts
    writer.close()

    master, global_receiver = _build_master(tmp_path, monkeypatch)

    await master._replay_durable_events()  # pyright: ignore[reportPrivateUsage]

    assert list(master.state.custom_model_cards) == [card.model_id]
    assert len(global_receiver.collect()) == 1


@pytest.mark.asyncio
async def test_replay_without_history_is_noop(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    master, global_receiver = _build_master(tmp_path, monkeypatch)

    await master._replay_durable_events()  # pyright: ignore[reportPrivateUsage]

    assert master.state.custom_model_cards == {}
    assert global_receiver.collect() == []
