"""Worker custom-card hydration from the durable TOML store."""

import anyio
import pytest

from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.types.backends import Backend
from exo.shared.types.commands import ForwarderCommand, ForwarderDownloadCommand
from exo.shared.types.common import ModelId, NodeId
from exo.shared.types.events import Event, IndexedEvent
from exo.shared.types.memory import Memory
from exo.shared.types.state import State
from exo.utils.channels import channel
from exo.worker.main import Worker, with_persisted_custom_cards


def _card(model_id: str, *, is_custom: bool = True) -> ModelCard:
    return ModelCard(
        model_id=ModelId(model_id),
        storage_size=Memory.from_bytes(1024),
        n_layers=4,
        hidden_size=64,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.TinygradMetal],
        is_custom=is_custom,
    )


def _make_worker() -> Worker:
    _, event_receiver = channel[IndexedEvent]()
    event_sender, _ = channel[Event]()
    command_sender, _ = channel[ForwarderCommand]()
    download_sender, _ = channel[ForwarderDownloadCommand]()
    return Worker(
        NodeId("test-node"),
        event_receiver=event_receiver,
        event_sender=event_sender,
        command_sender=command_sender,
        download_command_sender=download_sender,
        api_port=0,
    )


def test_hydrates_custom_cards_into_empty_state() -> None:
    card = _card("org/gguf")
    state = with_persisted_custom_cards(State(), [card])
    assert state.custom_model_cards == {card.model_id: card}


def test_ignores_cards_that_are_not_custom() -> None:
    card = _card("org/builtin", is_custom=False)
    state = with_persisted_custom_cards(State(), [card])
    assert state.custom_model_cards == {}


def test_does_not_duplicate_cards_already_in_state() -> None:
    card = _card("org/gguf")
    initial = State(custom_model_cards={card.model_id: card})
    state = with_persisted_custom_cards(initial, [card])
    assert state.custom_model_cards == {card.model_id: card}


def test_hydrates_multiple_cards() -> None:
    first = _card("org/one")
    second = _card("org/two")
    state = with_persisted_custom_cards(State(), [first, second])
    assert state.custom_model_cards == {
        first.model_id: first,
        second.model_id: second,
    }


def test_preserves_last_event_applied_idx() -> None:
    card = _card("org/gguf")
    initial = State(last_event_applied_idx=7)
    state = with_persisted_custom_cards(initial, [card])
    assert state.last_event_applied_idx == 7


@pytest.mark.asyncio
async def test_hydrate_reads_state_after_await(monkeypatch: pytest.MonkeyPatch) -> None:
    """Events applied while the durable load runs must not be discarded."""
    worker = _make_worker()
    card = _card("org/gguf")
    started = anyio.Event()
    release = anyio.Event()

    async def slow_load() -> list[ModelCard]:
        started.set()
        await release.wait()
        return [card]

    monkeypatch.setattr("exo.worker.main.load_persisted_custom_cards", slow_load)

    async with anyio.create_task_group() as tg:
        tg.start_soon(worker._hydrate_custom_cards)  # pyright: ignore[reportPrivateUsage]
        await started.wait()
        # Simulate _event_applier advancing state while the load is in flight.
        worker.state = State(last_event_applied_idx=5)
        release.set()

    assert worker.state.last_event_applied_idx == 5
    assert card.model_id in worker.state.custom_model_cards
