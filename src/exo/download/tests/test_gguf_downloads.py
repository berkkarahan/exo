"""Tests for GGUF model completion detection, resolution, and offline discovery.

The tinygrad backend consumes GGUF checkpoints, which have no
``*.safetensors.index.json``. Completeness is decided by the card's
``gguf_filename`` instead.
"""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest

from exo.download.download_utils import (
    _build_file_list_from_local_directory,  # pyright: ignore[reportPrivateUsage]
    _scan_gguf_directory,  # pyright: ignore[reportPrivateUsage]
    build_model_path,
    is_model_directory_complete,
    resolve_existing_model,
)
from exo.shared.models.model_cards import ModelCard, ModelTask
from exo.shared.types.backends import Backend
from exo.shared.types.common import ModelId
from exo.shared.types.memory import Memory

MODEL_ID = ModelId("test-org/test-gguf-model")
NORMALIZED = MODEL_ID.normalize()
GGUF_FILENAME = "model-Q4_K_M.gguf"


def _gguf_card(*, gguf_filename: str | None = GGUF_FILENAME) -> ModelCard:
    return ModelCard(
        model_id=MODEL_ID,
        storage_size=Memory.from_bytes(4096),
        n_layers=4,
        hidden_size=64,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.TinygradMetal],
        gguf_filename=gguf_filename,
    )


def _write_gguf(
    model_dir: Path, *, filename: str = GGUF_FILENAME, size: int = 1024
) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / filename).write_bytes(b"\x00" * size)


# ---------------------------------------------------------------------------
# is_model_directory_complete
# ---------------------------------------------------------------------------


class TestGgufCompleteness:
    def test_complete_when_gguf_file_present(self, tmp_path: Path) -> None:
        model_dir = tmp_path / NORMALIZED
        _write_gguf(model_dir)
        assert is_model_directory_complete(model_dir, _gguf_card()) is True

    def test_incomplete_when_gguf_file_missing(self, tmp_path: Path) -> None:
        model_dir = tmp_path / NORMALIZED
        model_dir.mkdir(parents=True)
        assert is_model_directory_complete(model_dir, _gguf_card()) is False

    def test_incomplete_when_gguf_file_empty(self, tmp_path: Path) -> None:
        model_dir = tmp_path / NORMALIZED
        _write_gguf(model_dir, size=0)
        assert is_model_directory_complete(model_dir, _gguf_card()) is False

    def test_incomplete_when_card_has_no_gguf_filename(self, tmp_path: Path) -> None:
        model_dir = tmp_path / NORMALIZED
        _write_gguf(model_dir)
        # No gguf_filename and no safetensors index -> not complete.
        assert (
            is_model_directory_complete(model_dir, _gguf_card(gguf_filename=None))
            is False
        )

    def test_incomplete_when_a_different_gguf_file_is_present(
        self, tmp_path: Path
    ) -> None:
        model_dir = tmp_path / NORMALIZED
        _write_gguf(model_dir, filename="other.gguf")
        assert is_model_directory_complete(model_dir, _gguf_card()) is False


# ---------------------------------------------------------------------------
# resolve_existing_model / build_model_path
# ---------------------------------------------------------------------------


class TestGgufResolution:
    def test_resolve_finds_gguf_model(self, tmp_path: Path) -> None:
        writable = tmp_path / "writable"
        _write_gguf(writable / NORMALIZED)
        with (
            patch("exo.download.download_utils.EXO_MODELS_READ_ONLY_DIRS", ()),
            patch("exo.download.download_utils.EXO_MODELS_DIRS", (writable,)),
        ):
            assert (
                resolve_existing_model(MODEL_ID, _gguf_card()) == writable / NORMALIZED
            )

    def test_resolve_without_card_does_not_see_gguf(self, tmp_path: Path) -> None:
        writable = tmp_path / "writable"
        _write_gguf(writable / NORMALIZED)
        with (
            patch("exo.download.download_utils.EXO_MODELS_READ_ONLY_DIRS", ()),
            patch("exo.download.download_utils.EXO_MODELS_DIRS", (writable,)),
        ):
            assert resolve_existing_model(MODEL_ID) is None

    def test_build_model_path_returns_found_gguf_dir(self, tmp_path: Path) -> None:
        writable = tmp_path / "writable"
        _write_gguf(writable / NORMALIZED)
        with (
            patch("exo.download.download_utils.EXO_MODELS_READ_ONLY_DIRS", ()),
            patch("exo.download.download_utils.EXO_MODELS_DIRS", (writable,)),
            patch(
                "exo.download.download_utils.EXO_DEFAULT_MODELS_DIR",
                tmp_path / "default",
            ),
        ):
            assert build_model_path(MODEL_ID, _gguf_card()) == writable / NORMALIZED

    def test_build_model_path_finds_gguf_in_non_default_dir(
        self, tmp_path: Path
    ) -> None:
        default = tmp_path / "default"
        default.mkdir()
        writable = tmp_path / "writable"
        _write_gguf(writable / NORMALIZED)
        with (
            patch("exo.download.download_utils.EXO_MODELS_READ_ONLY_DIRS", ()),
            patch("exo.download.download_utils.EXO_MODELS_DIRS", (default, writable)),
            patch("exo.download.download_utils.EXO_DEFAULT_MODELS_DIR", default),
        ):
            assert build_model_path(MODEL_ID, _gguf_card()) == writable / NORMALIZED


# ---------------------------------------------------------------------------
# _scan_gguf_directory / offline discovery
# ---------------------------------------------------------------------------


class TestScanGgufDirectory:
    def test_returns_entries_with_config_sidecar(self, tmp_path: Path) -> None:
        model_dir = tmp_path / NORMALIZED
        _write_gguf(model_dir, size=512)
        (model_dir / "config.json").write_text('{"model_type": "qwen2"}')
        entries = _scan_gguf_directory(model_dir)
        assert entries is not None
        by_path = {entry.path: entry for entry in entries}
        assert by_path[GGUF_FILENAME].size == 512
        assert by_path["config.json"].size is not None

    def test_returns_none_without_gguf(self, tmp_path: Path) -> None:
        model_dir = tmp_path / NORMALIZED
        model_dir.mkdir(parents=True)
        assert _scan_gguf_directory(model_dir) is None

    def test_ignores_partial_files(self, tmp_path: Path) -> None:
        model_dir = tmp_path / NORMALIZED
        model_dir.mkdir(parents=True)
        (model_dir / f"{GGUF_FILENAME}.partial").write_bytes(b"\x00" * 10)
        assert _scan_gguf_directory(model_dir) is None


class TestOfflineGgufDiscovery:
    @pytest.fixture
    async def model_dirs(self, tmp_path: Path) -> AsyncIterator[tuple[Path, Path]]:
        writable = tmp_path / "writable"
        writable.mkdir()
        default = tmp_path / "default"
        default.mkdir()
        with (
            patch("exo.download.download_utils.EXO_MODELS_READ_ONLY_DIRS", ()),
            patch("exo.download.download_utils.EXO_MODELS_DIRS", (writable, default)),
        ):
            yield writable, default

    async def test_discovers_local_gguf_files(
        self, model_dirs: tuple[Path, Path]
    ) -> None:
        writable, _ = model_dirs
        _write_gguf(writable / NORMALIZED, size=256)
        file_list = await _build_file_list_from_local_directory(
            MODEL_ID, recursive=True
        )
        assert file_list is not None
        assert {entry.path for entry in file_list} == {GGUF_FILENAME}

    async def test_safetensors_index_still_wins(
        self, model_dirs: tuple[Path, Path]
    ) -> None:
        writable, _ = model_dirs
        model_dir = writable / NORMALIZED
        model_dir.mkdir(parents=True)
        index = {
            "metadata": {"total_size": 1024},
            "weight_map": {"a": "model.safetensors"},
        }
        (model_dir / "model.safetensors.index.json").write_text(json.dumps(index))
        (model_dir / "model.safetensors").write_bytes(b"weights")
        file_list = await _build_file_list_from_local_directory(
            MODEL_ID, recursive=True
        )
        assert file_list is not None
        assert "model.safetensors" in {entry.path for entry in file_list}

    async def test_returns_none_when_nothing_local(
        self, model_dirs: tuple[Path, Path]
    ) -> None:
        assert (
            await _build_file_list_from_local_directory(MODEL_ID, recursive=True)
            is None
        )
