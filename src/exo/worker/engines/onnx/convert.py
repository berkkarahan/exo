"""Rank-scoped ONNX checkpoint conversion for pipeline-sharded models.

``onnxruntime_genai.models.builder.create_model`` can only export a
*prefix* of a model's layers (``num_hidden_layers=N`` exports layers
``0..N-1``); it cannot express an arbitrary half-open ``[start, end)``
interval. To export an arbitrary shard, this module performs checkpoint
surgery first: it slices and renumbers the source safetensors weights so
the retained layers start at index 0, then hands the renumbered
prefix-shaped checkpoint to the builder.
"""

import json
import shutil
import struct
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypedDict, cast, final

from exo.download import download_utils
from exo.download.download_utils import (
    build_model_path,
    resolve_existing_model,
    select_download_dir,
)
from exo.shared.models.model_cards import ConfigData
from exo.shared.types.common import ModelId
from exo.shared.types.worker.shards import PipelineShardMetadata

SUPPORTED_ARCHITECTURES: frozenset[str] = frozenset({"LlamaForCausalLM"})

_COMPLETION_MARKER = ".exo-conversion-complete"
_CACHE_SUBDIR = "onnx_conversions"
_OUTPUT_SAFETENSORS_FILENAME = "model.safetensors"
_SAFETENSORS_HEADER_LEN_SIZE = 8
_SAFETENSORS_ALIGNMENT = 8
_COPY_CHUNK_BYTES = 8 * 1024 * 1024
_LAYER_COUNT_KEYS = (
    "num_hidden_layers",
    "num_layers",
    "n_layer",
    "n_layers",
    "num_decoder_layers",
    "decoder_layers",
)
_NON_WEIGHT_FILENAMES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "tokenizer.model",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
    "generation_config.json",
)


@final
class UnsupportedArchitectureError(Exception):
    """Raised when a model's architecture has no ONNX conversion support."""


@final
class SourceCheckpointNotFoundError(Exception):
    """Raised when the source HuggingFace checkpoint cannot be located on disk."""


class BuildModel(Protocol):
    """Matches the shape of ``onnxruntime_genai.models.builder.create_model``."""

    def __call__(
        self,
        model_name: str,
        input_path: str,
        output_dir: str,
        precision: str,
        execution_provider: str,
        cache_dir: str,
        **extra_options: bool | int,
    ) -> None: ...


def _build_with_onnxruntime_genai(
    model_name: str,
    input_path: str,
    output_dir: str,
    precision: str,
    execution_provider: str,
    cache_dir: str,
    **extra_options: bool | int,
) -> None:
    from onnxruntime_genai.models.builder import (  # pyright: ignore[reportMissingTypeStubs]
        create_model,  # pyright: ignore[reportUnknownVariableType]
    )

    create_model(
        model_name,
        input_path,
        output_dir,
        precision,
        execution_provider,
        cache_dir,
        **extra_options,
    )


def plan_rank_tensors(
    names: Iterable[str], shard: PipelineShardMetadata
) -> Mapping[str, str]:
    """Decide which tensors a rank keeps and what to rename them to.

    Returns a mapping of source tensor name -> destination tensor name.
    Tensors omitted from the mapping are dropped for this rank. Retained
    ``model.layers.{i}.*`` tensors are renumbered so the shard's layers
    start at index 0. ``start_layer`` is inclusive, ``end_layer`` is
    exclusive.
    """
    plan: dict[str, str] = {}
    for name in names:
        if name.startswith("model.layers."):
            layer_index = int(name.split(".")[2])
            if shard.start_layer <= layer_index < shard.end_layer:
                rest = name.split(".", 3)[3]
                new_index = layer_index - shard.start_layer
                plan[name] = f"model.layers.{new_index}.{rest}"
        elif name.startswith("model.embed_tokens."):
            if shard.is_first_layer:
                plan[name] = name
        elif name.startswith(("lm_head.", "model.norm.")):
            if shard.is_last_layer:
                plan[name] = name
        else:
            plan[name] = name
    return plan


def _rewrite_layer_count(raw_config: dict[str, object], new_count: int) -> dict[str, object]:
    """Pure config-dict transform: point the layer-count field(s) at ``new_count``."""
    updated = dict(raw_config)
    matched_keys = [key for key in _LAYER_COUNT_KEYS if key in updated]
    for key in matched_keys or ["num_hidden_layers"]:
        updated[key] = new_count
    return updated


def _resolve_source_checkpoint(model_id: ModelId) -> Path:
    source_dir = resolve_existing_model(model_id) or build_model_path(model_id)
    if not source_dir.is_dir():
        raise SourceCheckpointNotFoundError(
            f"No local checkpoint found for {model_id!r} (looked in {source_dir})"
        )
    return source_dir


def _validate_architecture(config_path: Path) -> None:
    config = ConfigData.model_validate_json(config_path.read_text())
    if config.architectures is None or any(
        arch not in SUPPORTED_ARCHITECTURES for arch in config.architectures
    ):
        raise UnsupportedArchitectureError(
            f"Unsupported architecture(s) {config.architectures!r}; "
            f"ONNX conversion supports only: {sorted(SUPPORTED_ARCHITECTURES)}"
        )


def _cache_key(model_id: ModelId, shard: PipelineShardMetadata) -> str:
    return f"{model_id.normalize()}-rank{shard.device_rank}-of-{shard.world_size}"


def _find_cached_rank_checkpoint(cache_key: str) -> Path | None:
    """Search for an already-converted, complete rank checkpoint.

    Mirrors ``resolve_existing_model``'s search order: read-only dirs
    (for pre-baked conversions shipped alongside the source checkpoint)
    before writable dirs. Presence of the completion marker is the only
    check performed -- no size computation, no disk-space check.
    """
    all_dirs = (*download_utils.EXO_MODELS_READ_ONLY_DIRS, *download_utils.EXO_MODELS_DIRS)
    for search_dir in all_dirs:
        candidate = search_dir / _CACHE_SUBDIR / cache_key
        if (candidate / _COMPLETION_MARKER).is_file():
            return candidate
    return None


def _select_cache_write_dir(source_dir: Path) -> Path:
    """Pick a writable root with enough free space for a converted copy."""
    source_size = sum(f.stat().st_size for f in source_dir.rglob("*") if f.is_file())
    return select_download_dir(source_size)


class _SafetensorsHeaderEntry(TypedDict):
    dtype: str
    shape: list[int]
    data_offsets: list[int]


@dataclass(frozen=True, slots=True)
class _TensorLocation:
    """Where a tensor's raw bytes live, without materializing its dtype."""

    dtype: str
    shape: list[int]
    source_file: Path
    byte_range: tuple[int, int]  # absolute [begin, end) offsets in source_file


def _read_safetensors_header(path: Path) -> dict[str, _TensorLocation]:
    """Parse a safetensors container's header without loading tensor data.

    Layout: ``<u64 le header_length><header JSON><raw tensor data block>``.
    ``data_offsets`` in the header are relative to the start of the data
    block, i.e. absolute offset = ``8 + header_length + begin``.
    """
    with path.open("rb") as source_handle:
        header_len = cast(int, struct.unpack("<Q", source_handle.read(8))[0])
        header_json = source_handle.read(header_len)
    header_obj = cast("dict[str, object]", json.loads(header_json))
    data_start = _SAFETENSORS_HEADER_LEN_SIZE + header_len

    locations: dict[str, _TensorLocation] = {}
    for name, raw_entry in header_obj.items():
        if name == "__metadata__":
            continue
        entry = cast(_SafetensorsHeaderEntry, raw_entry)
        begin, end = entry["data_offsets"]
        locations[name] = _TensorLocation(
            dtype=entry["dtype"],
            shape=entry["shape"],
            source_file=path,
            byte_range=(data_start + begin, data_start + end),
        )
    return locations


def _write_safetensors(
    output_path: Path, tensors: Iterable[tuple[str, _TensorLocation]]
) -> None:
    """Stream tensor bytes into a fresh safetensors file, dtype-agnostic.

    Recomputes contiguous ``data_offsets`` starting at 0, in the same
    order the tensors are given, then streams the raw bytes in that same
    order so header declaration order and data order agree.
    """
    ordered = list(tensors)

    header: dict[str, object] = {}
    offset = 0
    for dest_name, location in ordered:
        size = location.byte_range[1] - location.byte_range[0]
        header[dest_name] = {
            "dtype": location.dtype,
            "shape": location.shape,
            "data_offsets": [offset, offset + size],
        }
        offset += size

    header_bytes = json.dumps(header).encode("utf-8")
    padding = (-len(header_bytes)) % _SAFETENSORS_ALIGNMENT
    header_bytes += b" " * padding

    with output_path.open("wb") as out_handle:
        out_handle.write(struct.pack("<Q", len(header_bytes)))
        out_handle.write(header_bytes)
        for _, location in ordered:
            begin, end = location.byte_range
            with location.source_file.open("rb") as in_handle:
                in_handle.seek(begin)
                remaining = end - begin
                while remaining > 0:
                    chunk = in_handle.read(min(_COPY_CHUNK_BYTES, remaining))
                    if not chunk:
                        break
                    out_handle.write(chunk)
                    remaining -= len(chunk)


def _stage_rank_checkpoint(
    source_dir: Path, staging_dir: Path, shard: PipelineShardMetadata
) -> None:
    """Write a renumbered, rank-sliced HF checkpoint into ``staging_dir``."""
    staging_dir.mkdir(parents=True, exist_ok=True)

    for filename in ("config.json", *_NON_WEIGHT_FILENAMES):
        source_file = source_dir / filename
        if source_file.is_file():
            shutil.copy2(source_file, staging_dir / filename)

    raw_config = cast(
        "dict[str, object]", json.loads((source_dir / "config.json").read_text())
    )
    new_layer_count = shard.end_layer - shard.start_layer
    (staging_dir / "config.json").write_text(
        json.dumps(_rewrite_layer_count(raw_config, new_layer_count))
    )

    safetensors_files = sorted(source_dir.glob("*.safetensors"))
    tensor_locations: dict[str, _TensorLocation] = {}
    for source_file in safetensors_files:
        tensor_locations.update(_read_safetensors_header(source_file))

    plan = plan_rank_tensors(tensor_locations.keys(), shard)

    _write_safetensors(
        staging_dir / _OUTPUT_SAFETENSORS_FILENAME,
        (
            (dest_name, tensor_locations[source_name])
            for source_name, dest_name in plan.items()
        ),
    )

    if (source_dir / "model.safetensors.index.json").is_file():
        weight_map = {name: _OUTPUT_SAFETENSORS_FILENAME for name in plan.values()}
        (staging_dir / "model.safetensors.index.json").write_text(
            json.dumps({"metadata": {"total_size": 0}, "weight_map": weight_map})
        )


def convert_for_rank(
    model_id: ModelId,
    shard: PipelineShardMetadata,
    *,
    build_model: BuildModel = _build_with_onnxruntime_genai,
) -> Path:
    """Convert a rank's slice of ``model_id`` to ONNX, with on-disk caching.

    Returns the directory containing the converted ONNX model for this
    rank. Cache hits (a directory with a completion marker from a prior
    successful run) are returned immediately without reconversion.
    """
    source_dir = _resolve_source_checkpoint(model_id)
    _validate_architecture(source_dir / "config.json")

    cache_key = _cache_key(model_id, shard)
    cached = _find_cached_rank_checkpoint(cache_key)
    if cached is not None:
        return cached

    cache_dir = _select_cache_write_dir(source_dir) / _CACHE_SUBDIR / cache_key
    marker = cache_dir / _COMPLETION_MARKER

    staging_dir = cache_dir.with_name(f"{cache_dir.name}-staging")
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    _stage_rank_checkpoint(source_dir, staging_dir, shard)

    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        build_model(
            str(model_id),
            str(staging_dir),
            str(cache_dir),
            "fp16",
            "cpu",
            str(staging_dir / ".genai_cache"),
            num_hidden_layers=shard.end_layer - shard.start_layer,
            exclude_embeds=not shard.is_first_layer,
            exclude_lm_head=not shard.is_last_layer,
        )
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    marker.write_text("")
    return cache_dir
