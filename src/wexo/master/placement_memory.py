"""Memory budgets for Tinygrad placement.

The gatherer samples device memory from its own process. A runner's weights
and cache live in another process, and the OpenCL free-memory sample does not
shrink when that runner allocates. Placement therefore reserves each instance
already in state before it accepts another.
"""

from collections.abc import Mapping

from wexo.shared.models.model_cards import ModelCard
from wexo.shared.types.common import NodeId
from wexo.shared.types.memory import Memory
from wexo.shared.types.profiling import MemoryUsage
from wexo.shared.types.worker.instances import Instance, InstanceId

_FLOAT16_BYTES = 2
_TEMPORARY_DENOMINATOR = 8


def attention_head_dimension(model_card: ModelCard) -> int | None:
    """Return the float16 head width, or None when the card does not state it."""
    attention_heads = model_card.num_attention_heads
    if attention_heads is None:
        return None
    if model_card.hidden_size % attention_heads != 0:
        return None
    return model_card.hidden_size // attention_heads


def shard_placement_bytes(model_card: ModelCard, layer_count: int) -> int:
    """Return the bytes a Tinygrad shard of ``layer_count`` layers must reserve.

    The weight term is the card's storage budget scaled by layer share. The
    cache term is float16 keys and values for ``context_length`` positions.
    A temporary allowance of one eighth of the weight bytes is included only
    when that cache term is known, because dequantization and the forward
    pass allocate workspace beyond the weights.
    """
    if layer_count <= 0:
        return 0
    weight_bytes = (
        model_card.storage_size.in_bytes * layer_count
    ) // model_card.n_layers
    cache_bytes = _kv_cache_bytes(model_card, layer_count)
    temporary_bytes = weight_bytes // _TEMPORARY_DENOMINATOR if cache_bytes > 0 else 0
    return weight_bytes + cache_bytes + temporary_bytes


def model_placement_bytes(model_card: ModelCard) -> int:
    """Return the reservation for every layer of ``model_card``."""
    return shard_placement_bytes(model_card, model_card.n_layers)


def memory_after_reservations(
    node_memory: Mapping[NodeId, MemoryUsage],
    instances: Mapping[InstanceId, Instance],
) -> dict[NodeId, MemoryUsage]:
    """Reserve resident instances without counting a runner twice.

    ``ram_total`` is left unchanged so the device capacity stays visible.
    Available bytes are the smaller of the reported free sample and capacity
    minus the budgets of instances already on the node.
    """
    reserved = _reserved_bytes_by_node(instances)
    adjusted: dict[NodeId, MemoryUsage] = {}
    for node_id, usage in node_memory.items():
        reported = usage.ram_available.in_bytes
        # Some samples already exclude other processes. Some, including the
        # OpenCL free-memory query on this driver, stay near the device total
        # while a runner is resident. The ceiling is capacity minus our
        # reservations; the sample supplies any extra usage we did not reserve.
        capacity = max(usage.ram_total.in_bytes, reported)
        reserved_bytes = reserved.get(node_id, 0)
        ceiling = max(capacity - reserved_bytes, 0)
        accelerator = usage.accelerator
        if accelerator is not None:
            accelerator = accelerator.model_copy(
                update={
                    "reserved": Memory.from_bytes(reserved_bytes),
                    "ceiling": Memory.from_bytes(ceiling),
                }
            )
        adjusted[node_id] = MemoryUsage.from_bytes(
            ram_total=usage.ram_total.in_bytes,
            ram_available=min(reported, ceiling),
            swap_total=usage.swap_total.in_bytes,
            swap_available=usage.swap_available.in_bytes,
            accelerator=accelerator,
        )
    return adjusted


def _kv_cache_bytes(model_card: ModelCard, layer_count: int) -> int:
    head_dimension = attention_head_dimension(model_card)
    key_value_heads = model_card.num_key_value_heads
    if (
        head_dimension is None
        or key_value_heads is None
        or model_card.context_length <= 0
    ):
        return 0
    return (
        2
        * key_value_heads
        * head_dimension
        * model_card.context_length
        * layer_count
        * _FLOAT16_BYTES
    )


def _reserved_bytes_by_node(
    instances: Mapping[InstanceId, Instance],
) -> dict[NodeId, int]:
    reserved: dict[NodeId, int] = {}
    for instance in instances.values():
        assignments = instance.shard_assignments
        for node_id, runner_id in assignments.node_to_runner.items():
            shard = assignments.runner_to_shard.get(runner_id)
            if shard is None:
                continue
            layer_count = shard.end_layer - shard.start_layer
            amount = shard_placement_bytes(shard.model_card, layer_count)
            reserved[node_id] = reserved.get(node_id, 0) + amount
    return reserved
