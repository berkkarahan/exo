"""Tinygrad placement reserves weights, KV cache, and workspace."""

from __future__ import annotations

import pytest

from exo.master.placement import place_instance
from exo.master.placement_memory import (
    memory_after_reservations,
    model_placement_bytes,
    shard_placement_bytes,
)
from exo.master.tests.conftest import create_node_memory, create_node_network
from exo.shared.models.model_cards import ModelCard, ModelId, ModelTask
from exo.shared.topology import Topology
from exo.shared.types.backends import Backend
from exo.shared.types.commands import PlaceInstance
from exo.shared.types.common import CommandId, NodeId
from exo.shared.types.memory import Memory
from exo.shared.types.profiling import (
    MemoryUsage,
    accelerator_sample_from_bytes,
)
from exo.shared.types.worker.instances import InstanceMeta
from exo.shared.types.worker.shards import Sharding

_QWEN_WEIGHT_BYTES = 1_260_334_848
_QWEN_CONTEXT = 32_768
_QWEN_LAYERS = 24
_QWEN_KEY_VALUE_HEADS = 2
_QWEN_HEAD_DIMENSION = 64


def _qwen_card() -> ModelCard:
    return ModelCard(
        model_id=ModelId("Qwen/Qwen2.5-0.5B-Instruct-GGUF"),
        storage_size=Memory.from_bytes(_QWEN_WEIGHT_BYTES),
        n_layers=_QWEN_LAYERS,
        hidden_size=896,
        supports_tensor=False,
        num_key_value_heads=_QWEN_KEY_VALUE_HEADS,
        num_attention_heads=14,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.WinAMD],
        context_length=_QWEN_CONTEXT,
    )


def _weight_only_card() -> ModelCard:
    return ModelCard(
        model_id=ModelId("mlx-community/example"),
        storage_size=Memory.from_bytes(4096),
        n_layers=4,
        hidden_size=16,
        supports_tensor=False,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.MlxMetal],
    )


def test_qwen_budget_adds_float16_kv_cache_and_workspace() -> None:
    card = _qwen_card()
    cache_bytes = (
        2
        * _QWEN_KEY_VALUE_HEADS
        * _QWEN_HEAD_DIMENSION
        * _QWEN_CONTEXT
        * _QWEN_LAYERS
        * 2
    )
    temporary_bytes = _QWEN_WEIGHT_BYTES // 8
    assert model_placement_bytes(card) == (
        _QWEN_WEIGHT_BYTES + cache_bytes + temporary_bytes
    )
    assert shard_placement_bytes(card, _QWEN_LAYERS // 2) < model_placement_bytes(card)


def test_card_without_attention_heads_budgets_weight_bytes_only() -> None:
    card = _weight_only_card()
    assert model_placement_bytes(card) == card.storage_size.in_bytes


def test_second_tinygrad_instance_is_refused_until_the_first_is_gone() -> None:
    card = _qwen_card()
    budget = model_placement_bytes(card)
    topology = Topology()
    node_id = NodeId("windows-amd")
    topology.add_node(node_id)
    node_memory = {node_id: create_node_memory(budget)}
    node_network = {node_id: create_node_network()}
    node_backends = {node_id: [Backend.WinAMD]}
    command = PlaceInstance(
        command_id=CommandId("place-qwen"),
        model_card=card,
        sharding=Sharding.Pipeline,
        instance_meta=InstanceMeta.Tinygrad,
        min_nodes=1,
    )

    placed = place_instance(
        command, topology, {}, node_memory, node_network, node_backends
    )
    assert len(placed) == 1

    with pytest.raises(ValueError, match="sufficient memory"):
        place_instance(
            command, topology, placed, node_memory, node_network, node_backends
        )

    placed_again = place_instance(
        command, topology, {}, node_memory, node_network, node_backends
    )
    assert len(placed_again) == 1


def test_a_free_sample_that_already_excludes_the_runner_is_not_counted_twice() -> None:
    card = _qwen_card()
    budget = model_placement_bytes(card)
    capacity = budget * 3
    topology = Topology()
    node_id = NodeId("windows-amd")
    topology.add_node(node_id)
    full = {
        node_id: MemoryUsage.from_bytes(
            ram_total=capacity,
            ram_available=capacity,
            swap_total=0,
            swap_available=0,
        )
    }
    command = PlaceInstance(
        command_id=CommandId("place-qwen"),
        model_card=card,
        sharding=Sharding.Pipeline,
        instance_meta=InstanceMeta.Tinygrad,
        min_nodes=1,
    )
    placed = place_instance(
        command,
        topology,
        {},
        full,
        {node_id: create_node_network()},
        {node_id: [Backend.WinAMD]},
    )
    already_reduced = {
        node_id: MemoryUsage.from_bytes(
            ram_total=capacity,
            ram_available=capacity - budget,
            swap_total=0,
            swap_available=0,
        )
    }
    adjusted = memory_after_reservations(already_reduced, placed)
    assert adjusted[node_id].ram_available.in_bytes == capacity - budget


def test_reservation_lowers_the_ceiling_and_keeps_the_free_sample() -> None:
    card = _qwen_card()
    budget = model_placement_bytes(card)
    capacity = budget * 3
    free_sample = capacity
    topology = Topology()
    node_id = NodeId("windows-amd")
    topology.add_node(node_id)
    sample = accelerator_sample_from_bytes(
        capacity_bytes=capacity,
        free_sample_bytes=free_sample,
        max_allocation_bytes=capacity // 2,
        host_ram_total_bytes=64 * 1024 * 1024 * 1024,
        host_ram_available_bytes=32 * 1024 * 1024 * 1024,
        reserved_bytes=0,
        estimate_source="opencl-amd-free",
        driver_version="3679.0",
    )
    node_memory = {
        node_id: MemoryUsage.from_bytes(
            ram_total=capacity,
            ram_available=free_sample,
            swap_total=0,
            swap_available=0,
            accelerator=sample,
        )
    }
    command = PlaceInstance(
        command_id=CommandId("place-qwen-sample"),
        model_card=card,
        sharding=Sharding.Pipeline,
        instance_meta=InstanceMeta.Tinygrad,
        min_nodes=1,
    )
    placed = place_instance(
        command,
        topology,
        {},
        node_memory,
        {node_id: create_node_network()},
        {node_id: [Backend.WinAMD]},
    )
    adjusted = memory_after_reservations(node_memory, placed)
    accelerator = adjusted[node_id].accelerator
    assert accelerator is not None
    assert accelerator.free_sample.in_bytes == free_sample
    assert accelerator.reserved.in_bytes == budget
    assert accelerator.ceiling.in_bytes == capacity - budget
    assert adjusted[node_id].ram_available.in_bytes == capacity - budget
    assert accelerator.driver_version == "3679.0"


def test_mlx_placement_does_not_subtract_a_resident_instance() -> None:
    card = _weight_only_card()
    topology = Topology()
    node_id = NodeId("mac")
    topology.add_node(node_id)
    node_memory = {node_id: create_node_memory(card.storage_size.in_bytes)}
    node_network = {node_id: create_node_network()}
    node_backends = {node_id: [Backend.MlxMetal]}
    command = PlaceInstance(
        command_id=CommandId("place-mlx"),
        model_card=card,
        sharding=Sharding.Pipeline,
        instance_meta=InstanceMeta.MlxRing,
        min_nodes=1,
    )

    placed = place_instance(
        command, topology, {}, node_memory, node_network, node_backends
    )
    placed_again = place_instance(
        command, topology, placed, node_memory, node_network, node_backends
    )
    assert len(placed_again) == 2
