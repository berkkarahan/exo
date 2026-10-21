"""Durable-event replay on master startup."""

from datetime import datetime, timezone
from pathlib import Path

import msgspec
import pytest
import zstandard
from anyio import EndOfStream
from pydantic import ValidationError
from pytest import MonkeyPatch

from wexo.master.main import Master
from wexo.routing.router import get_node_zid
from wexo.shared.models.model_cards import ModelCard, ModelTask
from wexo.shared.types.backends import Backend
from wexo.shared.types.commands import ForwarderCommand, ForwarderDownloadCommand
from wexo.shared.types.common import ModelId, SessionId
from wexo.shared.types.events import (
    CustomModelCardAdded,
    CustomModelCardDeleted,
    Event,
    GlobalForwarderEvent,
    InstanceLinkCreated,
    InstanceLinkDeleted,
    LocalForwarderEvent,
    NodeDownloadProgress,
    NodeGatheredInfo,
)
from wexo.shared.types.instance_link import InstanceLink, InstanceLinkId
from wexo.shared.types.memory import Memory
from wexo.shared.types.profiling import MemoryUsage
from wexo.shared.types.worker.downloads import DownloadPending
from wexo.shared.types.worker.instances import InstanceId
from wexo.shared.types.worker.shards import PipelineShardMetadata
from wexo.utils.channels import Receiver, channel
from wexo.utils.disk_event_log import DiskEventLog, PersistedEventError


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
    monkeypatch.setattr("wexo.master.main.EXO_EVENT_LOG_DIR", tmp_path / "event_log")
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


def _archive(directory: Path, payloads: list[bytes]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "events.2026-01-01_00-00-00.bin.zst"
    records = b"".join(
        len(payload).to_bytes(4, "big") + payload for payload in payloads
    )
    path.write_bytes(zstandard.ZstdCompressor().compress(records))
    return path


async def test_legacy_download_history_preserves_durable_state_across_restarts(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    card = _card("org/preserved")
    download = NodeDownloadProgress(
        download_progress=DownloadPending(
            node_id=get_node_zid(),
            shard_metadata=PipelineShardMetadata(
                model_card=card,
                device_rank=0,
                world_size=1,
                start_layer=0,
                end_layer=4,
                n_layers=4,
            ),
        )
    )
    legacy_json = download.model_dump_json().replace('"TinygradMetal"', '"MlxMetal"')
    # This is a valid old event whose nested backend is no longer supported.
    with pytest.raises(ValidationError, match="MlxMetal"):
        NodeDownloadProgress.model_validate_json(legacy_json)
    legacy = msgspec.msgpack.encode(
        msgspec.json.decode(legacy_json, type=dict[str, object])
    )
    link = InstanceLink(
        link_id=InstanceLinkId(),
        prefill_instances=[InstanceId()],
        decode_instances=[InstanceId()],
    )
    deleted_link = link.model_copy(update={"link_id": InstanceLinkId()})
    added = CustomModelCardAdded(model_card=card)
    events: list[Event] = [
        added,
        added,
        CustomModelCardAdded(model_card=_card("org/deleted")),
        CustomModelCardDeleted(model_id=ModelId("org/deleted")),
        InstanceLinkCreated(link=link),
        InstanceLinkCreated(link=deleted_link),
        InstanceLinkDeleted(link_id=deleted_link.link_id),
    ]
    archive = _archive(
        tmp_path / "event_log" / "master",
        [legacy, *(msgspec.msgpack.encode(e.model_dump(mode="json")) for e in events)],
    )
    original = archive.read_bytes()
    for _ in range(2):
        master, receiver = _build_master(tmp_path, monkeypatch)
        await master._replay_durable_events()  # pyright: ignore[reportPrivateUsage]
        assert master.state.custom_model_cards == {card.model_id: card}
        assert master.state.instance_links == {link.link_id: link}
        assert master.state.downloads == {}
        assert len(receiver.collect()) == 6
        master._event_log.close()  # pyright: ignore[reportPrivateUsage]
    assert archive.read_bytes() == original


async def test_invalid_durable_record_reports_location_and_closes_master(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    archive = _archive(
        tmp_path / "event_log" / "master",
        [msgspec.msgpack.encode({"CustomModelCardAdded": {"model_card": {}}})],
    )
    original = archive.read_bytes()
    master, receiver = _build_master(tmp_path, monkeypatch)
    with pytest.raises(PersistedEventError) as caught:
        await master.run()
    error = caught.value
    assert str(archive) in str(error)
    assert "record 0, byte 0" in str(error)
    assert isinstance(error.__cause__, ValidationError)
    assert not (archive.parent / "events.bin").exists()
    assert archive.read_bytes() == original
    with pytest.raises(EndOfStream):
        receiver.receive_nowait()
