from wexo.shared.apply import apply
from wexo.shared.models.model_cards import ModelCard, ModelTask
from wexo.shared.types.backends import Backend
from wexo.shared.types.common import ModelId
from wexo.shared.types.events import (
    CustomModelCardAdded,
    CustomModelCardDeleted,
    IndexedEvent,
)
from wexo.shared.types.memory import Memory
from wexo.shared.types.state import State


def _model_card(model_id: ModelId) -> ModelCard:
    return ModelCard(
        model_id=model_id,
        n_layers=1,
        storage_size=Memory.from_bytes(1),
        hidden_size=1,
        supports_tensor=True,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.TinygradMetal],
    )


def test_custom_model_card_added_is_reduced_into_state() -> None:
    card = _model_card(ModelId("custom/model"))

    state = apply(
        State(),
        IndexedEvent(idx=0, event=CustomModelCardAdded(model_card=card)),
    )

    assert state.custom_model_cards == {card.model_id: card}


def test_custom_model_card_deleted_removes_card_from_state() -> None:
    card = _model_card(ModelId("custom/model"))
    state = State(custom_model_cards={card.model_id: card}, last_event_applied_idx=0)

    state = apply(
        state,
        IndexedEvent(idx=1, event=CustomModelCardDeleted(model_id=card.model_id)),
    )

    assert state.custom_model_cards == {}
