from exo.shared.apply import apply_node_gathered_info
from exo.shared.cluster_runtime import (
    node_may_join_cluster,
    selected_inference_runtime,
)
from exo.shared.types.backends import Backend
from exo.shared.types.common import NodeId
from exo.shared.types.events import NodeGatheredInfo
from exo.shared.types.state import State
from exo.utils.info_gatherer.info_gatherer import MiscData, NodeBackends


def test_selected_inference_runtime_accepts_tinygrad_only() -> None:
    assert selected_inference_runtime("tinygrad") == "tinygrad"
    assert selected_inference_runtime("not-a-runtime") is None
    assert selected_inference_runtime("") is None
    assert selected_inference_runtime("onnx") is None


def test_tinygrad_mac_can_join_a_windows_cluster() -> None:
    assert node_may_join_cluster(
        [Backend.TinygradMetal],
        [[Backend.WinAMD, Backend.OnnxCpu]],
    )


def test_windows_can_join_a_tinygrad_cluster() -> None:
    assert node_may_join_cluster(
        [Backend.WinCPU],
        [[Backend.TinygradMetal]],
    )


def test_node_without_join_backends_cannot_enter() -> None:
    assert not node_may_join_cluster(
        [Backend.Vllm],
        [[Backend.WinAMD]],
    )


def test_empty_cluster_accepts_the_first_node() -> None:
    assert node_may_join_cluster([Backend.TinygradMetal], [])


def test_two_tinygrad_macs_can_join() -> None:
    assert node_may_join_cluster(
        [Backend.TinygradMetal],
        [[Backend.TinygradCpu, Backend.TinygradMetal]],
    )


def _gathered(node_id: str, info: NodeBackends | MiscData) -> NodeGatheredInfo:
    return NodeGatheredInfo(
        node_id=NodeId(node_id),
        when="2026-10-13T00:00:00+00:00",
        info=info,
    )


def test_apply_keeps_a_tinygrad_mac_in_a_windows_cluster() -> None:
    state = apply_node_gathered_info(
        _gathered("windows", NodeBackends(backends=[Backend.WinAMD])),
        State(),
    )
    state = apply_node_gathered_info(
        _gathered("mac", NodeBackends(backends=[Backend.TinygradMetal])),
        state,
    )
    assert NodeId("mac") in state.node_backends
    assert NodeId("mac") in state.topology.list_nodes()
    assert NodeId("mac") not in state.refused_node_backends


def test_apply_accepts_a_windows_node_on_a_tinygrad_mac_cluster() -> None:
    state = apply_node_gathered_info(
        _gathered("mac", NodeBackends(backends=[Backend.TinygradMetal, Backend.TinygradCpu])),
        State(),
    )
    state = apply_node_gathered_info(
        _gathered("windows", NodeBackends(backends=[Backend.WinAMD])),
        state,
    )
    assert NodeId("windows") in state.node_backends
    assert NodeId("windows") in list(state.topology.list_nodes())
    assert NodeId("windows") not in state.refused_node_backends


def test_apply_refuses_a_node_that_advertises_no_join_backends() -> None:
    state = apply_node_gathered_info(
        _gathered("mac", NodeBackends(backends=[Backend.TinygradMetal])),
        State(),
    )
    state = apply_node_gathered_info(
        _gathered("other", NodeBackends(backends=[Backend.Vllm])),
        state,
    )
    assert NodeId("other") not in state.node_backends
    assert NodeId("other") not in list(state.topology.list_nodes())
    assert state.refused_node_backends[NodeId("other")] == [Backend.Vllm]


def test_node_that_arrived_before_its_backends_joins_once_advertised() -> None:
    state = apply_node_gathered_info(
        _gathered("mac", NodeBackends(backends=[Backend.TinygradMetal])),
        State(),
    )
    state = apply_node_gathered_info(
        _gathered("windows", MiscData(friendly_name="desktop")),
        state,
    )
    assert NodeId("windows") in list(state.topology.list_nodes())
    state = apply_node_gathered_info(
        _gathered("windows", NodeBackends(backends=[Backend.WinAMD])),
        state,
    )
    assert NodeId("windows") in list(state.topology.list_nodes())
    assert NodeId("windows") in state.node_backends


def test_refused_node_rejoins_when_it_advertises_join_backends() -> None:
    state = apply_node_gathered_info(
        _gathered("mac", NodeBackends(backends=[Backend.TinygradMetal])),
        State(),
    )
    state = apply_node_gathered_info(
        _gathered("windows", NodeBackends(backends=[Backend.Vllm])),
        state,
    )
    assert NodeId("windows") not in list(state.topology.list_nodes())
    state = apply_node_gathered_info(
        _gathered("windows", MiscData(friendly_name="desktop")),
        state,
    )
    assert "desktop" not in [
        identity.friendly_name for identity in state.node_identities.values()
    ]
    state = apply_node_gathered_info(
        _gathered("windows", NodeBackends(backends=[Backend.WinAMD])),
        state,
    )
    assert NodeId("windows") in state.node_backends
    assert NodeId("windows") not in state.refused_node_backends
