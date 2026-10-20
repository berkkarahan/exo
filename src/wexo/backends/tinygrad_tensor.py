"""Column- and row-parallel slices for a Llama, Qwen2, or Qwen3 block.

Each rank keeps every layer. Query, key, value, gate, and up projections are
split on their output rows. Output and down projections are split on their
input columns, and the caller sums those partial results. Norms, token
embeddings, and the language-model head stay replicated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wexo.backends.tinygrad_weights import TinygradWeightError, TransformerArchitecture

if TYPE_CHECKING:
    from tinygrad.tensor import Tensor

_COLUMN_PARALLEL_SUFFIXES = (
    "self_attn.q_proj.weight",
    "self_attn.k_proj.weight",
    "self_attn.v_proj.weight",
    "self_attn.q_proj.bias",
    "self_attn.k_proj.bias",
    "self_attn.v_proj.bias",
    "mlp.gate_proj.weight",
    "mlp.up_proj.weight",
)
_ROW_PARALLEL_SUFFIXES = (
    "self_attn.o_proj.weight",
    "mlp.down_proj.weight",
)


def architecture_for_tensor_rank(
    architecture: TransformerArchitecture, rank: int, world_size: int
) -> TransformerArchitecture:
    """Return the head counts this rank owns.

    Raises:
        TinygradWeightError: The runner entrypoint handles a world size that
            does not divide the attention heads or the MLP width.
    """
    if world_size == 1:
        return architecture
    _require_rank(rank, world_size)
    query_heads = architecture.num_attention_heads
    key_value_heads = architecture.resolved_key_value_heads()
    if query_heads % world_size != 0 or key_value_heads % world_size != 0:
        raise TinygradWeightError(
            f"Attention heads {query_heads} and key-value heads {key_value_heads} "
            f"are not divisible by tensor parallel world size {world_size}"
        )
    if architecture.intermediate_size % world_size != 0:
        raise TinygradWeightError(
            f"intermediate_size {architecture.intermediate_size} is not divisible "
            f"by tensor parallel world size {world_size}"
        )
    return architecture.model_copy(
        update={
            "num_attention_heads": query_heads // world_size,
            "num_key_value_heads": key_value_heads // world_size,
            "head_dim": architecture.resolved_head_dimension(),
            "intermediate_size": architecture.intermediate_size // world_size,
        }
    )


def slice_tensor_parallel_parameters(
    parameters: dict[str, Tensor], rank: int, world_size: int
) -> dict[str, Tensor]:
    """Return ``parameters`` with this rank's projection rows and columns.

    Replicated tensors are the same objects. Sliced tensors are realized so
    the full projection can be dropped by the caller.

    Raises:
        TinygradWeightError: The runner entrypoint handles a projection whose
            split axis is not divisible by ``world_size``.
    """
    if world_size == 1:
        return parameters
    _require_rank(rank, world_size)
    sliced: dict[str, Tensor] = {}
    for name, weight in parameters.items():
        if _ends_with(name, _COLUMN_PARALLEL_SUFFIXES):
            sliced[name] = _slice_axis(weight, 0, rank, world_size, name)
        elif _ends_with(name, _ROW_PARALLEL_SUFFIXES):
            sliced[name] = _slice_axis(weight, 1, rank, world_size, name)
        else:
            sliced[name] = weight
    return sliced


def _require_rank(rank: int, world_size: int) -> None:
    if world_size < 1 or rank < 0 or rank >= world_size:
        raise TinygradWeightError(
            f"Tensor parallel rank {rank} is outside world size {world_size}"
        )


def _ends_with(name: str, suffixes: tuple[str, ...]) -> bool:
    return any(name.endswith(suffix) for suffix in suffixes)


def _slice_axis(
    weight: Tensor, axis: int, rank: int, world_size: int, name: str
) -> Tensor:
    length = int(weight.shape[axis])
    if length % world_size != 0:
        raise TinygradWeightError(
            f"{name} length {length} is not divisible by tensor parallel "
            f"world size {world_size}"
        )
    local = length // world_size
    start = rank * local
    end = start + local
    if axis == 0:
        sliced = weight[start:end]
    elif axis == 1:
        sliced = weight[:, start:end]
    else:
        raise TinygradWeightError(f"{name} cannot be sliced on axis {axis}")
    return sliced.contiguous().realize()
