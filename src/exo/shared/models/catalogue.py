"""Choose catalogue entries the cluster's advertised backends can run.

Mac nodes advertise MLX backends and see MLX weights. Windows and other
tinygrad nodes advertise GGUF backends and see GGUF weights. A cluster that
advertises both keeps both. An empty advertisement keeps the full catalogue
until a node reports a backend.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final, Literal, final

from exo.shared.models.gguf_card import TINYGRAD_GGUF_BACKENDS
from exo.shared.models.model_cards import ModelCard
from exo.shared.types.backends import Backend
from exo.utils.pydantic_ext import FrozenModel

CatalogueFormat = Literal["mlx", "gguf"]

MLX_CATALOGUE_BACKENDS: Final[frozenset[Backend]] = frozenset(
    {
        Backend.MlxMetal,
        Backend.MlxCuda,
        Backend.MlxCpu,
    }
)
_GGUF_CATALOGUE_BACKENDS: Final[frozenset[Backend]] = frozenset(TINYGRAD_GGUF_BACKENDS)


@final
class CatalogueSearch(FrozenModel):
    """One Hugging Face query for a catalogue format."""

    author: str | None = None
    huggingface_filter: str | None = None


def advertised_catalogue_formats(
    backends: Iterable[Backend],
) -> frozenset[CatalogueFormat]:
    """Return the weight formats ``backends`` can place."""
    available = frozenset(backends)
    formats: set[CatalogueFormat] = set()
    if available & MLX_CATALOGUE_BACKENDS:
        formats.add("mlx")
    if available & _GGUF_CATALOGUE_BACKENDS:
        formats.add("gguf")
    return frozenset(formats)


def model_card_catalogue_format(card: ModelCard) -> CatalogueFormat | None:
    """Return the weight format a card places, when the card names one.

    A GGUF filename wins. A card that lists only tinygrad or Windows backends
    is GGUF. A card that lists an MLX backend is MLX, including a safetensors
    card that also names every other backend.
    """
    if card.gguf_filename is not None:
        return "gguf"
    backends = frozenset(card.backends)
    has_gguf = bool(backends & _GGUF_CATALOGUE_BACKENDS)
    has_mlx = bool(backends & MLX_CATALOGUE_BACKENDS)
    if has_gguf and not has_mlx:
        return "gguf"
    if has_mlx:
        return "mlx"
    return None


def model_card_matches_catalogue(card: ModelCard, backends: Iterable[Backend]) -> bool:
    """Return whether ``card`` belongs in the catalogue for ``backends``.

    No advertised backend keeps every card. A card with no MLX or GGUF format
    stays hidden once the cluster has chosen one of those formats.
    """
    formats = advertised_catalogue_formats(backends)
    if not formats:
        return True
    return model_card_catalogue_format(card) in formats


def catalogue_searches(backends: Iterable[Backend]) -> tuple[CatalogueSearch, ...]:
    """Return the Hugging Face queries for the formats ``backends`` can run.

    No advertised backend keeps the historical MLX Community query.
    """
    formats = advertised_catalogue_formats(backends)
    mlx = CatalogueSearch(author="mlx-community")
    gguf = CatalogueSearch(huggingface_filter="gguf")
    if formats == frozenset({"gguf"}):
        return (gguf,)
    if formats == frozenset({"mlx", "gguf"}):
        return (mlx, gguf)
    return (mlx,)
