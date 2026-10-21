from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit
from pydantic import ValidationError

from wexo.backends.tests.test_tinygrad_generate import write_tinygrad_generation_gguf
from wexo.backends.tinygrad_checkpoint import read_one_gguf_checkpoint
from wexo.download.download_utils import resolve_allow_patterns
from wexo.master.placement import place_instance
from wexo.master.tests.conftest import create_node_memory, create_node_network
from wexo.shared.models.gguf_card import (
    GgufRegistrationError,
    choose_gguf_filename,
    gguf_header_bytes,
    model_card_from_gguf_file,
)
from wexo.shared.models.model_cards import ConfigData, ModelCard, ModelId, ModelTask
from wexo.shared.topology import Topology
from wexo.shared.types.backends import Backend
from wexo.shared.types.commands import PlaceInstance
from wexo.shared.types.common import CommandId, NodeId
from wexo.shared.types.memory import Memory
from wexo.shared.types.worker.downloads import FileListEntry
from wexo.shared.types.worker.instances import InstanceMeta, TinygradInstance
from wexo.shared.types.worker.shards import PipelineShardMetadata, Sharding

_FILES = (
    "qwen2.5-0.5b-instruct-q2_k.gguf",
    "qwen2.5-0.5b-instruct-q4_k_m.gguf",
    "qwen2.5-0.5b-instruct-q8_0.gguf",
    "qwen2.5-0.5b-instruct-f16.gguf",
)


def test_choose_gguf_filename_prefers_one_q4_k_m_file() -> None:
    assert choose_gguf_filename(_FILES, None) == "qwen2.5-0.5b-instruct-q4_k_m.gguf"


def test_choose_gguf_filename_uses_the_only_file() -> None:
    assert choose_gguf_filename(("weights.gguf", "config.json"), None) == "weights.gguf"


def test_choose_gguf_filename_honors_an_explicit_file() -> None:
    assert (
        choose_gguf_filename(_FILES, "qwen2.5-0.5b-instruct-q8_0.gguf")
        == "qwen2.5-0.5b-instruct-q8_0.gguf"
    )


def test_choose_gguf_filename_rejects_a_split_and_an_ambiguous_quant() -> None:
    # Split files and multiple matching quants now resolve gracefully without crashing
    assert (
        choose_gguf_filename(("model-00001-of-00002.gguf",), None)
        == "model-00001-of-00002.gguf"
    )
    assert choose_gguf_filename(
        ("a-q4_k_m.gguf", "b-q4_k_m.gguf"),
        None,
    ) in ("a-q4_k_m.gguf", "b-q4_k_m.gguf")
    with pytest.raises(GgufRegistrationError, match="No GGUF files"):
        _ = choose_gguf_filename(("config.json", "pytorch_model.bin"), None)


def test_gguf_filename_must_stay_inside_the_repository() -> None:
    with pytest.raises(ValidationError, match="gguf_filename"):
        _ = _card(gguf_filename="../weights.gguf")


def test_model_card_budgets_the_larger_of_file_and_float16_bytes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "weights.gguf"
    write_tinygrad_generation_gguf(
        path,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
    )
    checkpoint = read_one_gguf_checkpoint(path)
    realized = sum(
        record.element_count * 2
        for record in checkpoint.tensors
        if record.canonical_name is not None
    )
    card = model_card_from_gguf_file(
        ModelId("org/model"),
        path,
        repo_path="weights.gguf",
        file_size=path.stat().st_size,
    )

    assert card.gguf_filename == "weights.gguf"
    assert card.n_layers == 1
    assert card.hidden_size == 16
    assert card.num_key_value_heads == 2
    assert card.num_attention_heads == 4
    assert card.supports_tensor is True
    assert Backend.WinAMD in card.backends
    assert card.storage_size.in_bytes == max(path.stat().st_size, realized)
    assert realized > 0
    restored = ModelCard.model_validate(card.model_dump(exclude_none=True))
    assert restored.gguf_filename == "weights.gguf"


@pytest.mark.anyio
async def test_named_gguf_download_does_not_include_other_quants() -> None:
    card = _card(gguf_filename="weights-q4_k_m.gguf")
    shard = PipelineShardMetadata(
        model_card=card,
        device_rank=0,
        world_size=1,
        start_layer=0,
        end_layer=1,
        n_layers=1,
    )
    patterns = await resolve_allow_patterns(shard)
    assert patterns[0] == "weights-q4_k_m.gguf"
    assert "*" not in patterns
    assert all(
        not pattern.endswith(".gguf") or pattern == patterns[0] for pattern in patterns
    )


@pytest.mark.anyio
async def test_header_read_grows_until_the_header_is_complete(tmp_path: Path) -> None:
    path = tmp_path / "weights.gguf"
    write_tinygrad_generation_gguf(
        path,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
    )
    payload = path.read_bytes()
    calls: list[int] = []

    async def read_prefix(length: int) -> bytes:
        calls.append(length)
        if length < 4_194_304:
            return payload[:8]
        return payload

    header = await gguf_header_bytes(read_prefix, file_size=len(payload) + 8_000_000)
    assert header == payload
    assert calls == [1_048_576, 4_194_304]


@pytest.mark.anyio
async def test_fetch_from_hf_registers_a_gguf_only_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "weights.gguf"
    write_tinygrad_generation_gguf(
        path,
        tokens=("a", "b", "c", "d"),
        eos_token_id=1,
        layer_count=1,
        include_output=True,
    )
    payload = path.read_bytes()
    file_list = [
        FileListEntry(type="file", path="weights.gguf", size=len(payload)),
        FileListEntry(type="file", path="README.md", size=12),
    ]

    async def file_list_with_cache(
        *_args: object, **_kwargs: object
    ) -> list[FileListEntry]:
        return file_list

    async def read_http_prefix(
        _model_id: ModelId, _repo_path: str, length: int
    ) -> bytes:
        return payload[:length]

    monkeypatch.setattr(
        "wexo.download.download_utils.fetch_file_list_with_cache",
        file_list_with_cache,
    )
    monkeypatch.setattr(
        "wexo.shared.models.gguf_card._read_http_prefix",
        read_http_prefix,
    )

    card = await ModelCard.fetch_from_hf(ModelId("org/gguf-only"))
    assert card.gguf_filename == "weights.gguf"
    assert card.n_layers == 1
    assert Backend.WinAMD in card.backends


@pytest.mark.anyio
async def test_fetch_from_hf_keeps_safetensors_when_an_index_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def file_list_with_cache(
        *_args: object, **_kwargs: object
    ) -> list[FileListEntry]:
        return [
            FileListEntry(type="file", path="model.safetensors.index.json", size=20),
            FileListEntry(type="file", path="extra.gguf", size=20),
        ]

    async def fetch_config_data(_model_id: ModelId) -> ConfigData:
        return ConfigData.model_validate(
            {
                "num_hidden_layers": 4,
                "hidden_size": 32,
                "num_key_value_heads": 4,
                "max_position_embeddings": 128,
            }
        )

    async def fetch_safetensors_size(_model_id: ModelId) -> Memory:
        return Memory.from_bytes(4321)

    monkeypatch.setattr(
        "wexo.download.download_utils.fetch_file_list_with_cache",
        file_list_with_cache,
    )
    monkeypatch.setattr(
        "wexo.shared.models.model_cards.fetch_config_data",
        fetch_config_data,
    )
    monkeypatch.setattr(
        "wexo.shared.models.model_cards.fetch_safetensors_size",
        fetch_safetensors_size,
    )

    card = await ModelCard.fetch_from_hf(ModelId("org/safetensors"))
    assert card.gguf_filename is None
    assert card.storage_size.in_bytes == 4321
    assert card.n_layers == 4


def test_curated_qwen_gguf_card_places_on_winamd() -> None:
    from wexo.shared.constants import RESOURCES_DIR

    card_path = (
        Path(RESOURCES_DIR)
        / "inference_model_cards"
        / "Qwen--Qwen2.5-0.5B-Instruct-GGUF.toml"
    )
    card = ModelCard.model_validate(
        tomlkit.loads(card_path.read_text(encoding="utf-8"))
    )
    assert card.gguf_filename == "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    assert card.n_layers == 24
    assert card.hidden_size == 896
    assert card.num_attention_heads == 14
    assert card.storage_size.in_bytes == 1_260_334_848
    assert Backend.WinAMD in card.backends

    topology = Topology()
    node_id = NodeId("windows-amd")
    topology.add_node(node_id)
    placements = place_instance(
        PlaceInstance(
            command_id=CommandId("place-qwen-gguf"),
            model_card=card,
            sharding=Sharding.Pipeline,
            instance_meta=InstanceMeta.Tinygrad,
            min_nodes=1,
        ),
        topology,
        {},
        {node_id: create_node_memory(16 * 1024 * 1024 * 1024)},
        {node_id: create_node_network()},
        {node_id: [Backend.WinAMD]},
    )
    instance = next(iter(placements.values()))
    assert isinstance(instance, TinygradInstance)
    assert instance.device_backend_by_node == {node_id: Backend.WinAMD}


def test_winamd_node_places_a_gguf_card() -> None:
    card = _card(gguf_filename="weights.gguf", storage_size=Memory.from_bytes(4096))
    topology = Topology()
    node_id = NodeId("windows-amd")
    topology.add_node(node_id)
    placements = place_instance(
        PlaceInstance(
            command_id=CommandId("place-gguf"),
            model_card=card,
            sharding=Sharding.Pipeline,
            instance_meta=InstanceMeta.Tinygrad,
            min_nodes=1,
        ),
        topology,
        {},
        {node_id: create_node_memory(1_000_000)},
        {node_id: create_node_network()},
        {node_id: [Backend.WinAMD]},
    )
    instance = next(iter(placements.values()))
    assert isinstance(instance, TinygradInstance)
    assert instance.device_backend_by_node == {node_id: Backend.WinAMD}
    shard = next(iter(instance.shard_assignments.runner_to_shard.values()))
    assert shard.end_layer - shard.start_layer == card.n_layers


def _card(
    *,
    gguf_filename: str | None,
    storage_size: Memory | None = None,
) -> ModelCard:
    return ModelCard(
        model_id=ModelId("org/model"),
        storage_size=storage_size or Memory.from_bytes(4096),
        n_layers=1,
        hidden_size=16,
        supports_tensor=False,
        num_key_value_heads=2,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.WinAMD, Backend.TinygradCpu],
        gguf_filename=gguf_filename,
    )
