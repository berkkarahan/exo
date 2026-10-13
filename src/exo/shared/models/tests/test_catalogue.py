"""The catalogue keeps MLX weights for MLX backends and GGUF weights for GGUF backends."""

from __future__ import annotations

from anyio import Path

from exo.shared.constants import RESOURCES_DIR
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


def test_windows_and_mac_catalogue_formats_follow_the_advertised_backend() -> None:
    assert advertised_catalogue_formats([Backend.WinAMD]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.WinCUDA]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.WinCPU]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.TinygradAmd]) == frozenset({"gguf"})
    assert advertised_catalogue_formats([Backend.MlxMetal]) == frozenset({"mlx"})
    assert advertised_catalogue_formats([Backend.MlxCpu]) == frozenset({"mlx"})
    assert advertised_catalogue_formats([Backend.MlxCuda]) == frozenset({"mlx"})
    assert advertised_catalogue_formats(
        [Backend.MlxMetal, Backend.WinAMD]
    ) == frozenset({"mlx", "gguf"})
    assert advertised_catalogue_formats(()) == frozenset()


def test_safetensors_card_that_lists_every_backend_stays_on_mac() -> None:
    card = _card(*Backend, gguf_filename=None)
    assert model_card_catalogue_format(card) == "mlx"
    assert model_card_matches_catalogue(card, [Backend.MlxMetal])
    assert not model_card_matches_catalogue(card, [Backend.WinAMD])
    assert model_card_matches_catalogue(card, ())


def test_catalogue_search_follows_the_advertised_backend() -> None:
    windows = catalogue_searches([Backend.WinAMD])
    assert len(windows) == 1
    assert windows[0].author is None
    assert windows[0].huggingface_filter == "gguf"

    mac = catalogue_searches([Backend.MlxMetal])
    assert len(mac) == 1
    assert mac[0].author == "mlx-community"
    assert mac[0].huggingface_filter is None

    both = catalogue_searches([Backend.TinygradMetal, Backend.MlxMetal])
    assert [search.author for search in both] == ["mlx-community", None]
    assert [search.huggingface_filter for search in both] == [None, "gguf"]

    assert catalogue_searches(())[0].author == "mlx-community"


async def test_builtin_catalogue_splits_gguf_from_mlx() -> None:
    cards = await card_cache.list_all()
    windows = [
        card for card in cards if model_card_matches_catalogue(card, [Backend.WinAMD])
    ]
    mac = [
        card for card in cards if model_card_matches_catalogue(card, [Backend.MlxMetal])
    ]
    assert windows
    assert mac
    assert all(model_card_catalogue_format(card) == "gguf" for card in windows)
    assert all(model_card_catalogue_format(card) == "mlx" for card in mac)
    assert {card.model_id for card in windows}.isdisjoint(
        {card.model_id for card in mac}
    )
    assert any(card.gguf_filename is not None for card in windows)
    assert any(str(card.model_id).startswith("mlx-community/") for card in mac)

    image = await ModelCard.load_from_path(
        Path(RESOURCES_DIR / "image_model_cards" / "exolabs--FLUX.1-schnell.toml")
    )
    assert model_card_matches_catalogue(image, [Backend.MlxMetal])
    assert not model_card_matches_catalogue(image, [Backend.WinCPU])
