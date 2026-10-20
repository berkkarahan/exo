"""The catalogue exposes GGUF weights, which is all this fork runs."""

from __future__ import annotations

from exo.shared.models.catalogue import (
    advertised_catalogue_formats,
    catalogue_searches,
    model_card_catalogue_format,
    model_card_matches_catalogue,
)
from exo.shared.models.model_cards import ModelCard, ModelId, ModelTask, card_cache
from exo.shared.types.backends import Backend
from exo.shared.types.memory import Memory


def _card(*backends: Backend, gguf_filename: str | None = None) -> ModelCard:
    return ModelCard(
        model_id=ModelId("catalogue-probe"),
        storage_size=Memory.from_mb(1),
        n_layers=1,
        hidden_size=8,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=list(backends),
        gguf_filename=gguf_filename,
    )


def test_advertised_backends_all_yield_the_gguf_format() -> None:
    assert advertised_catalogue_formats([Backend.WinAMD]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.WinCUDA]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.WinCPU]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.TinygradAmd]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.TinygradMetal]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.TinygradCpu]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.TinygradCuda]) == frozenset({"gguf"})
    assert advertised_catalogue_formats(
        [Backend.TinygradMetal, Backend.WinAMD]
    ) == frozenset({"gguf"})
    assert advertised_catalogue_formats(()) == frozenset()


def test_card_listing_gguf_backends_without_a_gguf_filename_is_gguf() -> None:
    card = _card(*Backend)
    assert model_card_catalogue_format(card) == "gguf"
    assert model_card_matches_catalogue(card, [Backend.TinygradMetal])
    assert model_card_matches_catalogue(card, [Backend.WinAMD])
    assert model_card_matches_catalogue(card, ())


def test_catalogue_search_always_targets_gguf() -> None:
    for advertised in ([Backend.WinAMD], [Backend.TinygradMetal], []):
        searches = catalogue_searches(advertised)
        assert len(searches) == 1
        assert searches[0].author is None
        assert searches[0].huggingface_filter == "gguf"


async def test_builtin_catalogue_only_lists_gguf_cards() -> None:
    cards = await card_cache.list_all()
    for advertised in ([Backend.WinAMD], [Backend.TinygradMetal]):
        listed = [
            card
            for card in cards
            if model_card_matches_catalogue(card, advertised)
        ]
        assert listed
        assert all(model_card_catalogue_format(card) == "gguf" for card in listed)
        assert any(card.gguf_filename is not None for card in listed)
