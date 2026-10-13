"""Decide whether a node may join a cluster that already has a runtime.

A Mac joins a Windows cluster only when the Mac was started with tinygrad.
A Windows node joins a Mac cluster only when that Mac was started with
tinygrad. Two MLX Macs still join each other. ``apply_node_gathered_info``
uses ``node_may_join_cluster`` and leaves a refused node out of the topology.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final, Literal

from exo.shared.models.catalogue import MLX_CATALOGUE_BACKENDS
from exo.shared.models.gguf_card import TINYGRAD_GGUF_BACKENDS
from exo.shared.types.backends import Backend

ClusterInferenceRuntime = Literal["mlx", "tinygrad"]

_TINYGRAD_JOIN_BACKENDS: Final[frozenset[Backend]] = frozenset(TINYGRAD_GGUF_BACKENDS)


def selected_inference_runtime(value: str) -> ClusterInferenceRuntime | None:
    """Return ``mlx`` or ``tinygrad`` when ``value`` names one of them.

    Any other text, including a blank string, means the process did not
    choose a runtime. ``NodeBackends.gather`` then keeps the platform default.
    """
    normalized = value.strip().lower()
    if normalized == "mlx" or normalized == "tinygrad":
        return normalized
    return None


def inference_runtime_for_backends(
    backends: Iterable[Backend],
) -> ClusterInferenceRuntime | None:
    """Return the single runtime ``backends`` can share with a peer.

    Tinygrad identities, including the Windows join identities, are
    ``tinygrad``. MLX identities are ``mlx``. A node that advertises both,
    or neither, has not chosen a runtime the other side can match.
    """
    available = frozenset(backends)
    has_mlx = bool(available & MLX_CATALOGUE_BACKENDS)
    has_tinygrad = bool(available & _TINYGRAD_JOIN_BACKENDS)
    if has_tinygrad and not has_mlx:
        return "tinygrad"
    if has_mlx and not has_tinygrad:
        return "mlx"
    return None


def node_may_join_cluster(
    joining_backends: Iterable[Backend],
    member_backends: Iterable[Iterable[Backend]],
) -> bool:
    """Return whether ``joining_backends`` can enter a cluster of ``member_backends``.

    An empty cluster accepts the first node. After that, the joiner and every
    current member must share one runtime. A Mac advertising only MLX cannot
    join Windows members, and a Windows node cannot join MLX members.
    """
    members = list(member_backends)
    if len(members) == 0:
        return True
    joining_runtime = inference_runtime_for_backends(joining_backends)
    if joining_runtime is None:
        return False
    for backends in members:
        if inference_runtime_for_backends(backends) != joining_runtime:
            return False
    return True
