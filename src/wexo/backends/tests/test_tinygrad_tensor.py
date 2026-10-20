"""Tensor-parallel slices match one unsplit Llama block, and the chain sums."""

from __future__ import annotations

import array
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

from wexo.backends.tinygrad_hidden_state import HiddenStateBuffer
from wexo.backends.tinygrad_pipeline import connect_memory_pipeline, sum_hidden_states
from wexo.backends.tinygrad_tensor import (
    architecture_for_tensor_rank,
    slice_tensor_parallel_parameters,
)
from wexo.backends.tinygrad_weights import TinygradWeightError, TransformerArchitecture
from wexo.shared.models.model_cards import ModelCard, ModelId, ModelTask
from wexo.shared.types.backends import Backend
from wexo.shared.types.memory import Memory
from wexo.shared.types.worker.shards import PipelineShardMetadata

if TYPE_CHECKING:
    from tinygrad.tensor import Tensor


def test_tensor_ranks_share_a_seed_when_the_request_has_none() -> None:
    from wexo.backends.tinygrad_generate import agreed_tensor_seed

    assert agreed_tensor_seed("task") == agreed_tensor_seed("task")
    assert agreed_tensor_seed("task") != agreed_tensor_seed("other")
    assert 0 <= agreed_tensor_seed("task") < 2**32


def test_tensor_rank_rejects_a_width_that_does_not_divide() -> None:
    architecture = _architecture()
    with pytest.raises(TinygradWeightError, match="intermediate_size"):
        architecture_for_tensor_rank(
            architecture.model_copy(update={"intermediate_size": 31}),
            0,
            2,
        )


def test_two_ranks_match_an_unsplit_llama_block() -> None:
    _require_discrete_opencl()
    from dataclasses import replace

    from tinygrad import Tensor

    from wexo.backends.tinygrad_engine import assign_tinygrad_default_device
    from wexo.backends.tinygrad_llama import (
        LoadedShard,
        _attention,  # pyright: ignore[reportPrivateUsage]
        _swiglu,  # pyright: ignore[reportPrivateUsage]
        assemble_loaded_shard,
        forward_llama_decoder_layer,
        root_mean_square_normalize,
    )

    assign_tinygrad_default_device("CL")
    architecture = _architecture()
    parameters = _parameters()
    shard = _shard()
    full = assemble_loaded_shard(parameters, architecture, shard)
    rank_shards: list[LoadedShard] = []
    for rank in (0, 1):
        local_architecture = architecture_for_tensor_rank(architecture, rank, 2)
        sliced = slice_tensor_parallel_parameters(dict(parameters), rank, 2)
        rank_shards.append(assemble_loaded_shard(sliced, local_architecture, shard))
    hidden = Tensor.randn(1, 2, 16).realize()
    full_layer = full.layers[0]
    full_output, full_keys, full_values = forward_llama_decoder_layer(
        hidden, full_layer, architecture, None, None
    )
    normalized = root_mean_square_normalize(
        hidden, full_layer.input_norm_weight, architecture.rms_norm_eps
    )
    partials: list[Tensor] = []
    keys: list[Tensor] = []
    values: list[Tensor] = []
    for rank, loaded in enumerate(rank_shards):
        layer = replace(
            loaded.layers[0],
            attention=replace(loaded.layers[0].attention, output_bias=None),
        )
        attention, key, value = _attention(
            normalized,
            layer,
            architecture_for_tensor_rank(architecture, rank, 2),
            None,
            None,
        )
        partials.append(attention)
        keys.append(key)
        values.append(value)
    output_bias = full_layer.attention.output_bias
    assert output_bias is not None
    attention = partials[0] + partials[1] + output_bias
    residual = hidden.float() + attention.float()
    multilayer_input = root_mean_square_normalize(
        residual.cast(hidden.dtype),
        full_layer.post_attention_norm_weight,
        architecture.rms_norm_eps,
    )
    multilayer_partials = [
        _swiglu(multilayer_input, loaded.layers[0].multilayer_perceptron)
        for loaded in rank_shards
    ]
    multilayer = multilayer_partials[0] + multilayer_partials[1]
    reconstructed = (residual + multilayer.float()).cast(hidden.dtype).realize()
    assert _max_difference(reconstructed, full_output) < 1e-4
    for rank, loaded in enumerate(rank_shards):
        reduced, _keys, _values = forward_llama_decoder_layer(
            hidden,
            loaded.layers[0],
            architecture_for_tensor_rank(architecture, rank, 2),
            None,
            None,
            _sum_with_peer(rank, partials, multilayer_partials),
        )
        assert _max_difference(reduced, full_output) < 1e-4
    assert _max_difference(keys[0].cat(keys[1], dim=1), full_keys) < 1e-4
    assert _max_difference(values[0].cat(values[1], dim=1), full_values) < 1e-4


def test_chain_all_reduce_returns_the_same_sum_on_every_rank() -> None:
    transports = connect_memory_pipeline(3)
    for transport in transports:
        transport.open()
    payloads = [
        _float_buffer((1.0, 2.0)),
        _float_buffer((3.0, 4.0)),
        _float_buffer((5.0, 6.0)),
    ]
    results: list[HiddenStateBuffer | None] = [None, None, None]

    def reduce_rank(rank: int) -> None:
        results[rank] = transports[rank].all_reduce_sum("task", payloads[rank])

    threads = [threading.Thread(target=reduce_rank, args=(rank,)) for rank in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    expected = sum_hidden_states(
        sum_hidden_states(payloads[0], payloads[1]), payloads[2]
    )
    assert results[0] == expected
    assert results[1] == expected
    assert results[2] == expected


def _sum_with_peer(
    rank: int,
    attention_partials: list[Tensor],
    multilayer_partials: list[Tensor],
) -> Callable[[Tensor], Tensor]:
    """Add the other rank's pre-bias attention output, then its MLP output."""
    peers = iter((attention_partials, multilayer_partials))

    def all_reduce(tensor: Tensor) -> Tensor:
        stage = next(peers)
        return (tensor + stage[1 - rank]).contiguous().realize()

    return all_reduce


def _require_discrete_opencl() -> None:
    pytest.importorskip("tinygrad")
    from wexo.backends.tinygrad_opencl import (
        clear_opencl_resolution_cache,
        resolve_usable_opencl_adapter,
    )

    clear_opencl_resolution_cache()
    adapter = resolve_usable_opencl_adapter()
    if adapter is None or adapter.host_unified_memory:
        pytest.skip("no discrete OpenCL GPU")


def _float_buffer(values: tuple[float, ...]) -> HiddenStateBuffer:
    payload: array.array[float] = array.array("f", values)
    return HiddenStateBuffer(
        dtype="float32", shape=(len(values),), data=payload.tobytes()
    )


def _max_difference(left: Tensor, right: Tensor) -> float:
    left_values: array.array[float] = array.array("f")
    right_values: array.array[float] = array.array("f")
    left_values.frombytes(left.float().contiguous().realize().numpy().tobytes())
    right_values.frombytes(right.float().contiguous().realize().numpy().tobytes())
    return max(
        abs(item - peer) for item, peer in zip(left_values, right_values, strict=True)
    )


def _architecture() -> TransformerArchitecture:
    return TransformerArchitecture(
        model_type="llama",
        hidden_size=16,
        num_attention_heads=4,
        num_key_value_heads=2,
        intermediate_size=32,
        rms_norm_eps=1e-5,
        rope_theta=10000.0,
        vocab_size=20,
        num_hidden_layers=1,
        head_dim=4,
        attention_bias=True,
    )


def _shard() -> PipelineShardMetadata:
    card = ModelCard(
        model_id=ModelId("tinygrad-tensor"),
        storage_size=Memory.from_mb(1),
        n_layers=1,
        hidden_size=16,
        supports_tensor=True,
        num_attention_heads=4,
        num_key_value_heads=2,
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.TinygradCpu],
    )
    return PipelineShardMetadata(
        model_card=card,
        device_rank=0,
        world_size=1,
        start_layer=0,
        end_layer=1,
        n_layers=1,
    )


def _parameters() -> dict[str, Tensor]:
    from tinygrad import Tensor

    def matrix(rows: int, columns: int) -> Tensor:
        return Tensor.randn(rows, columns).realize()

    prefix = "model.layers.0"
    return {
        f"{prefix}.input_layernorm.weight": Tensor.randn(16).realize(),
        f"{prefix}.self_attn.q_proj.weight": matrix(16, 16),
        f"{prefix}.self_attn.k_proj.weight": matrix(8, 16),
        f"{prefix}.self_attn.v_proj.weight": matrix(8, 16),
        f"{prefix}.self_attn.o_proj.weight": matrix(16, 16),
        f"{prefix}.self_attn.q_proj.bias": Tensor.randn(16).realize(),
        f"{prefix}.self_attn.k_proj.bias": Tensor.randn(8).realize(),
        f"{prefix}.self_attn.v_proj.bias": Tensor.randn(8).realize(),
        f"{prefix}.self_attn.o_proj.bias": Tensor.randn(16).realize(),
        f"{prefix}.post_attention_layernorm.weight": Tensor.randn(16).realize(),
        f"{prefix}.mlp.gate_proj.weight": matrix(32, 16),
        f"{prefix}.mlp.up_proj.weight": matrix(32, 16),
        f"{prefix}.mlp.down_proj.weight": matrix(16, 32),
        "model.embed_tokens.weight": matrix(20, 16),
        "model.norm.weight": Tensor.randn(16).realize(),
        "lm_head.weight": matrix(20, 16),
    }
