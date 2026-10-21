"""Tensor parallelism across separate OS processes over real TCP sockets.

The in-process test ``test_tinygrad_tensor.py`` proves the tensor-parallel
math with in-memory queues. This proves the same math holds when each rank is
a distinct OS process exchanging all-reduce collectives over TCP loopback
sockets -- the real "across different nodes" path a cluster uses. Every rank
loads its sliced weights from disk, opens a ``TcpPipelineTransport``, runs a
full-model forward with the real chain all-reduce, and rank 0's logits are
compared against a single-rank unsplit reference built from the same weights.
"""

from __future__ import annotations

import json
import multiprocessing
import socket
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast, final

import pytest

if TYPE_CHECKING:
    from tinygrad.tensor import Tensor


@final
@dataclass(frozen=True)
class _WorkerConfig:
    """Everything one rank process needs to load, connect, and forward."""

    rank: int
    world_size: int
    ports: tuple[int, ...]
    checkpoint_dir: str
    token: int
    dims: dict[str, int]
    out_path: str
    error_path: str


_DIMS = Literal[2, 3, 4]


def _dims_for(world_size: _DIMS) -> dict[str, int]:
    """Return a transformer shape every ``world_size`` divides cleanly."""
    if world_size == 2:
        return {
            "hidden": 16,
            "heads": 4,
            "kv": 2,
            "intermediate": 32,
            "head_dim": 4,
            "vocab": 20,
            "layers": 1,
        }
    if world_size == 3:
        return {
            "hidden": 18,
            "heads": 6,
            "kv": 3,
            "intermediate": 36,
            "head_dim": 3,
            "vocab": 24,
            "layers": 1,
        }
    return {
        "hidden": 16,
        "heads": 8,
        "kv": 4,
        "intermediate": 32,
        "head_dim": 2,
        "vocab": 20,
        "layers": 1,
    }


def _write_tensor_checkpoint(directory: Path, dims: dict[str, int]) -> None:
    from tinygrad import dtypes
    from tinygrad.nn.state import safe_save

    payload = {
        "model_type": "llama",
        "hidden_size": dims["hidden"],
        "num_attention_heads": dims["heads"],
        "num_key_value_heads": dims["kv"],
        "intermediate_size": dims["intermediate"],
        "rms_norm_eps": 1e-5,
        "rope_theta": 10000,
        "vocab_size": dims["vocab"],
        "num_hidden_layers": dims["layers"],
        "head_dim": dims["head_dim"],
        "tie_word_embeddings": False,
    }
    (directory / "config.json").write_text(json.dumps(payload))
    safe_save(
        {
            name: tensor.cast(dtypes.float32)
            for name, tensor in _tensor_parameters(dims).items()
        },
        str(directory / "model.safetensors"),
    )


def _tensor_parameters(dims: dict[str, int]) -> dict[str, Tensor]:
    from tinygrad import Tensor

    query = dims["heads"] * dims["head_dim"]
    key = dims["kv"] * dims["head_dim"]
    prefix = "model.layers.0"

    def matrix(rows: int, columns: int) -> Tensor:
        return Tensor.randn(rows, columns).realize()

    return {
        f"{prefix}.input_layernorm.weight": Tensor.randn(dims["hidden"]).realize(),
        f"{prefix}.self_attn.q_proj.weight": matrix(query, dims["hidden"]),
        f"{prefix}.self_attn.k_proj.weight": matrix(key, dims["hidden"]),
        f"{prefix}.self_attn.v_proj.weight": matrix(key, dims["hidden"]),
        f"{prefix}.self_attn.o_proj.weight": matrix(dims["hidden"], query),
        f"{prefix}.post_attention_layernorm.weight": Tensor.randn(
            dims["hidden"]
        ).realize(),
        f"{prefix}.mlp.gate_proj.weight": matrix(dims["intermediate"], dims["hidden"]),
        f"{prefix}.mlp.up_proj.weight": matrix(dims["intermediate"], dims["hidden"]),
        f"{prefix}.mlp.down_proj.weight": matrix(dims["hidden"], dims["intermediate"]),
        "model.embed_tokens.weight": matrix(dims["vocab"], dims["hidden"]),
        "model.norm.weight": Tensor.randn(dims["hidden"]).realize(),
        "lm_head.weight": matrix(dims["vocab"], dims["hidden"]),
    }


def _free_port() -> int:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    port: int = cast("int", listener.getsockname()[1])
    listener.close()
    return port


def _reference_logits(
    checkpoint_dir: Path,
    dims: dict[str, int],
    token: int,
    monkeypatch: pytest.MonkeyPatch,
) -> list[float]:
    """Run the unsplit single-rank model in this process for comparison."""
    from wexo.backends.tinygrad_engine import TinygradEngine
    from wexo.shared.models.model_cards import ModelCard, ModelId, ModelTask
    from wexo.shared.types.backends import Backend
    from wexo.shared.types.common import NodeId
    from wexo.shared.types.memory import Memory
    from wexo.shared.types.worker.instances import (
        BoundInstance,
        InstanceId,
        TinygradInstance,
    )
    from wexo.shared.types.worker.runners import RunnerId, ShardAssignments
    from wexo.shared.types.worker.shards import PipelineShardMetadata

    model_id = ModelId("tinygrad-tensor-tcp")

    def use_temporary_directory(model: ModelId, card: ModelCard | None = None) -> Path:
        return checkpoint_dir

    monkeypatch.setattr(
        "wexo.backends.tinygrad_weights.build_model_path", use_temporary_directory
    )
    card = ModelCard(
        model_id=model_id,
        storage_size=Memory.from_mb(16),
        n_layers=dims["layers"],
        hidden_size=dims["hidden"],
        supports_tensor=True,
        num_attention_heads=dims["heads"],
        num_key_value_heads=dims["kv"],
        tasks=[ModelTask.TextGeneration],
        backends=[Backend.TinygradCpu],
    )
    shard = PipelineShardMetadata(
        model_card=card,
        device_rank=0,
        world_size=1,
        start_layer=0,
        end_layer=dims["layers"],
        n_layers=dims["layers"],
    )
    node_id = NodeId("node-reference")
    runner_id = RunnerId("runner-reference")
    instance = TinygradInstance(
        instance_id=InstanceId("tinygrad-tensor-tcp"),
        shard_assignments=ShardAssignments(
            model_id=model_id,
            node_to_runner={node_id: runner_id},
            runner_to_shard={runner_id: shard},
        ),
        device_backend_by_node={node_id: Backend.TinygradCpu},
    )
    bound = BoundInstance(
        instance=instance, bound_runner_id=runner_id, bound_node_id=node_id
    )
    engine = TinygradEngine(device_name="CPU")
    list(engine.iter_load_model(bound))
    logits = engine._realize_logits((token,))  # pyright: ignore[reportPrivateUsage]
    engine.close()
    return logits


def _run_tensor_worker(config: _WorkerConfig) -> None:
    """Load one tensor rank and run a full-model forward over TCP loopback."""
    import traceback
    from pathlib import Path as _Path

    try:
        import wexo.backends.tinygrad_weights as weights
        from wexo.backends.tinygrad_engine import TinygradEngine
        from wexo.backends.tinygrad_pipeline import (
            PipelineHandshakeIdentity,
            TcpPipelineTransport,
        )
        from wexo.shared.models.model_cards import ModelCard, ModelId, ModelTask
        from wexo.shared.types.backends import Backend
        from wexo.shared.types.common import Host, NodeId
        from wexo.shared.types.memory import Memory
        from wexo.shared.types.worker.instances import (
            BoundInstance,
            InstanceId,
            TinygradInstance,
        )
        from wexo.shared.types.worker.runners import RunnerId, ShardAssignments
        from wexo.shared.types.worker.shards import TensorShardMetadata

        rank = config.rank
        world_size = config.world_size
        ports = config.ports
        dims = config.dims
        checkpoint_dir = _Path(config.checkpoint_dir)
        token = config.token

        def _noop_build_model_path(
            model: ModelId, card: ModelCard | None = None
        ) -> _Path:
            return checkpoint_dir

        weights.build_model_path = _noop_build_model_path

        model_id = ModelId("tinygrad-tensor-tcp")
        node_id = NodeId(f"node-{rank}")
        runner_id = RunnerId(f"runner-{rank}")
        card = ModelCard(
            model_id=model_id,
            storage_size=Memory.from_mb(16),
            n_layers=dims["layers"],
            hidden_size=dims["hidden"],
            supports_tensor=True,
            num_attention_heads=dims["heads"],
            num_key_value_heads=dims["kv"],
            tasks=[ModelTask.TextGeneration],
            backends=[Backend.TinygradCpu],
        )
        shard = TensorShardMetadata(
            model_card=card,
            device_rank=rank,
            world_size=world_size,
            start_layer=0,
            end_layer=dims["layers"],
            n_layers=dims["layers"],
        )
        hosts = [Host(ip="127.0.0.1", port=ports[i]) for i in range(world_size)]
        instance = TinygradInstance(
            instance_id=InstanceId("tinygrad-tensor-tcp"),
            shard_assignments=ShardAssignments(
                model_id=model_id,
                node_to_runner={node_id: runner_id},
                runner_to_shard={runner_id: shard},
            ),
            device_backend_by_node={node_id: Backend.TinygradCpu},
            hosts_by_node={node_id: hosts},
        )
        bound = BoundInstance(
            instance=instance, bound_runner_id=runner_id, bound_node_id=node_id
        )
        engine = TinygradEngine(device_name="CPU")
        list(engine.iter_load_model(bound))
        transport = TcpPipelineTransport(
            device_rank=rank,
            hosts=hosts,
            identity=PipelineHandshakeIdentity(
                instance_id="tinygrad-tensor-tcp",
                device_rank=rank,
                world_size=world_size,
                model_id=str(model_id),
                protocol="tinygrad-tensor",
            ),
        )
        transport.open()
        engine.pipeline_transport = transport
        logits = engine._realize_logits((token,))  # pyright: ignore[reportPrivateUsage]
        if rank == 0:
            _Path(config.out_path).write_text(json.dumps(logits))
        engine.close()
    except BaseException:  # noqa: BLE001 - surface the failure to the parent test
        _Path(config.error_path).write_text(traceback.format_exc())
        raise


def _spawn_and_join(world_size: int, config: _WorkerConfig, timeout: int = 180) -> None:
    ctx = multiprocessing.get_context("spawn")
    processes = [
        ctx.Process(target=_run_tensor_worker, args=(replace(config, rank=rank),))
        for rank in range(world_size)
    ]
    for process in processes:
        process.start()
    try:
        for process in processes:
            process.join(timeout)
            if process.is_alive():
                process.terminate()
                raise AssertionError(f"tensor rank worker {process.pid} did not stop")
            if process.exitcode != 0:
                error = Path(config.error_path)
                detail = (
                    error.read_text() if error.exists() else f"exit {process.exitcode}"
                )
                raise AssertionError(f"tensor rank worker failed: {detail}")
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()


def _assert_close(
    actual: list[float], expected: list[float], atol: float = 1e-3
) -> None:
    assert len(actual) == len(expected), (
        f"logit length {len(actual)} != {len(expected)}"
    )
    worst = max(abs(item - peer) for item, peer in zip(actual, expected, strict=True))
    assert worst <= atol, f"tensor-parallel logits differ from reference by {worst:.3e}"


def test_tensor_parallel_ranks_reduce_over_tcp_across_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("tinygrad")
    for world_size in (2, 4):
        _run_tensor_parallel_across_processes(tmp_path, monkeypatch, world_size)


def _run_tensor_parallel_across_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, world_size: _DIMS
) -> None:
    dims = _dims_for(world_size)
    checkpoint_dir = tmp_path / f"model-w{world_size}"
    checkpoint_dir.mkdir()
    _write_tensor_checkpoint(checkpoint_dir, dims)

    token = 3
    reference = _reference_logits(checkpoint_dir, dims, token, monkeypatch)

    ports = [_free_port() for _ in range(world_size)]
    config = _WorkerConfig(
        rank=0,
        world_size=world_size,
        ports=tuple(ports),
        checkpoint_dir=str(checkpoint_dir),
        token=token,
        dims=dims,
        out_path=str(tmp_path / f"rank0-w{world_size}.json"),
        error_path=str(tmp_path / f"worker-error-w{world_size}.txt"),
    )
    _spawn_and_join(world_size, config)

    produced: list[float] = cast(
        "list[float]",
        json.loads((tmp_path / f"rank0-w{world_size}.json").read_text()),
    )
    _assert_close(produced, reference)
