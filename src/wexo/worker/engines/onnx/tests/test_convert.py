"""Tests for rank-scoped ONNX checkpoint conversion.

Runs on any platform: uses a tiny synthetic safetensors checkpoint and an
injected ``build_model`` fake, never importing torch or onnxruntime_genai.
"""

import json
import struct
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import numpy as np
import pytest
from safetensors.numpy import save_file  # pyright: ignore[reportUnknownVariableType]

from wexo.download.download_utils import InsufficientDiskSpaceError
from wexo.shared.models.model_cards import ModelCard, ModelTask
from wexo.shared.types.backends import Backend
from wexo.shared.types.common import ModelId
from wexo.shared.types.memory import Memory
from wexo.shared.types.worker.shards import PipelineShardMetadata
from wexo.worker.engines.onnx.convert import (
    UnsupportedArchitectureError,
    convert_for_rank,
    plan_rank_tensors,
)

MODEL_ID = ModelId("test-org/tiny-llama")
N_LAYERS = 6


class _RecordingBuilder:
    """Fake ``build_model`` handler that records kwargs and never touches ONNX."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        model_name: str,
        input_path: str,
        output_dir: str,
        precision: str,
        execution_provider: str,
        cache_dir: str,
        **extra_options: bool | int,
    ) -> None:
        self.calls.append(
            {
                "model_name": model_name,
                "input_path": input_path,
                "output_dir": output_dir,
                "precision": precision,
                "execution_provider": execution_provider,
                "cache_dir": cache_dir,
                **extra_options,
            }
        )


def _write_synthetic_checkpoint(
    source_dir: Path,
    *,
    n_layers: int = N_LAYERS,
    architectures: list[str] | None = None,
) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "architectures": architectures or ["LlamaForCausalLM"],
        "hidden_size": 8,
        "num_hidden_layers": n_layers,
    }
    (source_dir / "config.json").write_text(json.dumps(config))

    tensors: dict[str, np.ndarray] = {
        "model.embed_tokens.weight": np.zeros((4, 8), dtype=np.float32),
        "model.norm.weight": np.ones((8,), dtype=np.float32),
        "lm_head.weight": np.zeros((4, 8), dtype=np.float32),
    }
    for i in range(n_layers):
        tensors[f"model.layers.{i}.self_attn.q_proj.weight"] = np.full(
            (8, 8), float(i), dtype=np.float32
        )
    save_file(tensors, str(source_dir / "model.safetensors"))
    weight_map = {name: "model.safetensors" for name in tensors}
    index = {"metadata": {"total_size": None}, "weight_map": weight_map}
    (source_dir / "model.safetensors.index.json").write_text(json.dumps(index))


def _write_bf16_checkpoint(source_dir: Path, *, n_layers: int = N_LAYERS) -> None:
    """Write a safetensors checkpoint containing a BF16 tensor, by hand.

    numpy has no BF16 dtype, so this cannot go through ``safetensors.numpy``.
    The container is built directly from the documented layout:
    ``<u64 le header_length><header JSON><raw tensor data block>``.
    """
    source_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "architectures": ["LlamaForCausalLM"],
        "hidden_size": 8,
        "num_hidden_layers": n_layers,
    }
    (source_dir / "config.json").write_text(json.dumps(config))

    tensor_bytes = bytes(range(8))  # 2x2 BF16 tensor: 4 elements * 2 bytes each.
    header = {
        "model.embed_tokens.weight": {
            "dtype": "BF16",
            "shape": [2, 2],
            "data_offsets": [0, len(tensor_bytes)],
        }
    }
    header_bytes = json.dumps(header).encode("utf-8")
    header_bytes += b" " * ((8 - len(header_bytes) % 8) % 8)
    (source_dir / "model.safetensors").write_bytes(
        struct.pack("<Q", len(header_bytes)) + header_bytes + tensor_bytes
    )
    weight_map = {"model.embed_tokens.weight": "model.safetensors"}
    index = {"metadata": {"total_size": None}, "weight_map": weight_map}
    (source_dir / "model.safetensors.index.json").write_text(json.dumps(index))


class _InspectingBuilder:
    """Fake builder that reads the staged safetensors file while it is still alive.

    ``convert_for_rank`` deletes the staging dir in a ``finally`` right after
    the builder returns, so recording must happen from inside ``__call__``.
    """

    def __init__(self) -> None:
        self.staged_header: dict[str, Any] | None = None
        self.staged_tensor_bytes: bytes | None = None

    def __call__(
        self,
        model_name: str,
        input_path: str,
        output_dir: str,
        precision: str,
        execution_provider: str,
        cache_dir: str,
        **extra_options: bool | int,
    ) -> None:
        raw = (Path(input_path) / "model.safetensors").read_bytes()
        header_len = cast(int, struct.unpack("<Q", raw[:8])[0])
        header = cast("dict[str, Any]", json.loads(raw[8 : 8 + header_len]))
        self.staged_header = header
        entry = cast("dict[str, Any]", header["model.embed_tokens.weight"])
        begin, end = cast("tuple[int, int]", entry["data_offsets"])
        self.staged_tensor_bytes = raw[8 + header_len + begin : 8 + header_len + end]


def _make_shard(
    *, start_layer: int, end_layer: int, n_layers: int = N_LAYERS, device_rank: int = 0
) -> PipelineShardMetadata:
    return PipelineShardMetadata(
        model_card=ModelCard(
            model_id=MODEL_ID,
            storage_size=Memory.from_mb(1),
            n_layers=n_layers,
            hidden_size=8,
            supports_tensor=False,
            tasks=[ModelTask.TextGeneration],
            backends=[Backend.OnnxDirectMl],
        ),
        device_rank=device_rank,
        world_size=3,
        start_layer=start_layer,
        end_layer=end_layer,
        n_layers=n_layers,
    )


@pytest.fixture
def source_dir(tmp_path: Path):
    source_root = tmp_path / "source"
    model_dir = source_root / MODEL_ID.normalize()
    _write_synthetic_checkpoint(model_dir)
    with (
        patch("wexo.download.download_utils.EXO_MODELS_READ_ONLY_DIRS", ()),
        patch("wexo.download.download_utils.EXO_MODELS_DIRS", (source_root,)),
    ):
        yield model_dir


class TestPlanRankTensors:
    def test_first_shard_keeps_embeddings_drops_head_and_norm(self) -> None:
        shard = _make_shard(start_layer=0, end_layer=2)
        names = [
            "model.embed_tokens.weight",
            "model.norm.weight",
            "lm_head.weight",
            "model.layers.0.self_attn.q_proj.weight",
            "model.layers.1.self_attn.q_proj.weight",
        ]
        plan = plan_rank_tensors(names, shard)

        assert "model.embed_tokens.weight" in plan
        assert "model.norm.weight" not in plan
        assert "lm_head.weight" not in plan
        assert plan["model.layers.0.self_attn.q_proj.weight"] == (
            "model.layers.0.self_attn.q_proj.weight"
        )
        assert plan["model.layers.1.self_attn.q_proj.weight"] == (
            "model.layers.1.self_attn.q_proj.weight"
        )

    def test_middle_shard_drops_embeddings_and_head(self) -> None:
        shard = _make_shard(start_layer=2, end_layer=4)
        names = [
            "model.embed_tokens.weight",
            "model.norm.weight",
            "lm_head.weight",
            "model.layers.2.self_attn.q_proj.weight",
            "model.layers.3.self_attn.q_proj.weight",
        ]
        plan = plan_rank_tensors(names, shard)

        assert "model.embed_tokens.weight" not in plan
        assert "model.norm.weight" not in plan
        assert "lm_head.weight" not in plan
        assert plan["model.layers.2.self_attn.q_proj.weight"] == (
            "model.layers.0.self_attn.q_proj.weight"
        )
        assert plan["model.layers.3.self_attn.q_proj.weight"] == (
            "model.layers.1.self_attn.q_proj.weight"
        )

    def test_last_shard_keeps_head_and_norm_drops_embeddings(self) -> None:
        shard = _make_shard(start_layer=4, end_layer=6)
        names = [
            "model.embed_tokens.weight",
            "model.norm.weight",
            "lm_head.weight",
            "model.layers.4.self_attn.q_proj.weight",
            "model.layers.5.self_attn.q_proj.weight",
        ]
        plan = plan_rank_tensors(names, shard)

        assert "model.embed_tokens.weight" not in plan
        assert plan["model.norm.weight"] == "model.norm.weight"
        assert plan["lm_head.weight"] == "lm_head.weight"
        assert plan["model.layers.4.self_attn.q_proj.weight"] == (
            "model.layers.0.self_attn.q_proj.weight"
        )
        assert plan["model.layers.5.self_attn.q_proj.weight"] == (
            "model.layers.1.self_attn.q_proj.weight"
        )

    def test_half_open_interval_excludes_end_layer_includes_start_layer(self) -> None:
        shard = _make_shard(start_layer=2, end_layer=4)
        names = [
            "model.layers.1.self_attn.q_proj.weight",
            "model.layers.2.self_attn.q_proj.weight",
            "model.layers.3.self_attn.q_proj.weight",
            "model.layers.4.self_attn.q_proj.weight",
        ]
        plan = plan_rank_tensors(names, shard)

        assert "model.layers.1.self_attn.q_proj.weight" not in plan
        assert "model.layers.2.self_attn.q_proj.weight" in plan
        assert "model.layers.3.self_attn.q_proj.weight" in plan
        assert "model.layers.4.self_attn.q_proj.weight" not in plan


class TestConvertForRank:
    def test_num_hidden_layers_equals_shard_span_for_every_shard_case(
        self, source_dir: Path
    ) -> None:
        del source_dir  # fixture only needed for its patched EXO_MODELS_DIRS
        for rank, (start_layer, end_layer) in enumerate([(0, 2), (2, 4), (4, 6)]):
            shard = _make_shard(
                start_layer=start_layer, end_layer=end_layer, device_rank=rank
            )
            builder = _RecordingBuilder()
            convert_for_rank(MODEL_ID, shard, build_model=builder)
            assert builder.calls[0]["num_hidden_layers"] == end_layer - start_layer

    def test_first_shard_builder_flags(self, source_dir: Path) -> None:
        del source_dir
        shard = _make_shard(start_layer=0, end_layer=2)
        builder = _RecordingBuilder()
        convert_for_rank(MODEL_ID, shard, build_model=builder)
        call = builder.calls[0]
        assert call["exclude_embeds"] is False
        assert call["exclude_lm_head"] is True

    def test_middle_shard_builder_flags(self, source_dir: Path) -> None:
        del source_dir
        shard = _make_shard(start_layer=2, end_layer=4)
        builder = _RecordingBuilder()
        convert_for_rank(MODEL_ID, shard, build_model=builder)
        call = builder.calls[0]
        assert call["exclude_embeds"] is True
        assert call["exclude_lm_head"] is True

    def test_last_shard_builder_flags(self, source_dir: Path) -> None:
        del source_dir
        shard = _make_shard(start_layer=4, end_layer=6)
        builder = _RecordingBuilder()
        convert_for_rank(MODEL_ID, shard, build_model=builder)
        call = builder.calls[0]
        assert call["exclude_embeds"] is True
        assert call["exclude_lm_head"] is False

    def test_cache_hit_returns_same_path_without_rebuilding(
        self, source_dir: Path
    ) -> None:
        del source_dir
        shard = _make_shard(start_layer=0, end_layer=2)
        builder = _RecordingBuilder()
        first_path = convert_for_rank(MODEL_ID, shard, build_model=builder)
        second_path = convert_for_rank(MODEL_ID, shard, build_model=builder)

        assert first_path == second_path
        assert len(builder.calls) == 1

    def test_bf16_tensor_survives_conversion_byte_for_byte(
        self, tmp_path: Path
    ) -> None:
        """Regression test: numpy cannot represent BF16, so staging must copy
        raw bytes instead of materializing tensors through numpy. Fails
        against the old ``safe_open(..., framework="numpy")`` implementation
        with ``TypeError: data type 'bfloat16' not understood``.
        """
        source_root = tmp_path / "source"
        source_dir = source_root / MODEL_ID.normalize()
        _write_bf16_checkpoint(source_dir)
        shard = _make_shard(start_layer=0, end_layer=2)
        builder = _InspectingBuilder()

        with (
            patch("wexo.download.download_utils.EXO_MODELS_READ_ONLY_DIRS", ()),
            patch("wexo.download.download_utils.EXO_MODELS_DIRS", (source_root,)),
        ):
            convert_for_rank(MODEL_ID, shard, build_model=builder)

        assert builder.staged_header is not None
        entry = cast(
            "dict[str, Any]", builder.staged_header["model.embed_tokens.weight"]
        )
        assert entry["dtype"] == "BF16"
        assert entry["shape"] == [2, 2]
        assert builder.staged_tensor_bytes == bytes(range(8))

    def test_cache_hit_does_not_require_disk_space(self, source_dir: Path) -> None:
        """Regression test: a cache hit must not consult disk space at all.
        Fails against the old implementation, which recomputes source size
        and calls ``select_download_dir`` even when a cached entry exists.
        """
        del source_dir
        shard = _make_shard(start_layer=0, end_layer=2)
        builder = _RecordingBuilder()
        convert_for_rank(MODEL_ID, shard, build_model=builder)  # populate cache

        def _raise_insufficient(required_bytes: int) -> Path:
            raise InsufficientDiskSpaceError("disk is full")

        with patch(
            "wexo.worker.engines.onnx.convert.select_download_dir",
            side_effect=_raise_insufficient,
        ):
            second_path = convert_for_rank(MODEL_ID, shard, build_model=builder)

        assert len(builder.calls) == 1
        assert second_path is not None

    def test_unsupported_architecture_raises_before_build(self, tmp_path: Path) -> None:
        source_root = tmp_path / "source"
        cache_root = tmp_path / "cache"
        cache_root.mkdir()
        source_dir = source_root / MODEL_ID.normalize()
        _write_synthetic_checkpoint(source_dir, architectures=["DeepseekV3ForCausalLM"])
        shard = _make_shard(start_layer=0, end_layer=2)
        builder = _RecordingBuilder()

        with (
            patch("wexo.download.download_utils.EXO_MODELS_READ_ONLY_DIRS", ()),
            patch("wexo.download.download_utils.EXO_MODELS_DIRS", (source_root,)),
            pytest.raises(UnsupportedArchitectureError),
        ):
            convert_for_rank(MODEL_ID, shard, build_model=builder)

        assert builder.calls == []
