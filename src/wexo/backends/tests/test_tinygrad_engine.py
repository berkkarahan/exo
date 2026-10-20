import sys
from io import BytesIO
from types import ModuleType

import pytest

from wexo.backends.registry import resolve_builder
from wexo.backends.tinygrad_engine import (
    TINYGRAD_DEVICE_NAME_BY_BACKEND,
    TinygradBuilder,
    TinygradDeviceName,
    TinygradDeviceSelectionError,
    TinygradEngine,
    assign_tinygrad_default_device,
    backends_from_declared_devices,
    tinygrad_device_name_for_backend,
    windows_join_backends,
)
from wexo.backends.tinygrad_weights import TinygradWeightError
from wexo.master.placement import INSTANCE_META_BACKENDS
from wexo.shared.models.model_cards import ModelCard, ModelId, ModelTask
from wexo.shared.types.backends import Backend
from wexo.shared.types.common import NodeId
from wexo.shared.types.events import Event
from wexo.shared.types.memory import Memory
from wexo.shared.types.tasks import TaskId
from wexo.shared.types.worker.instances import (
    BoundInstance,
    InstanceId,
    InstanceMeta,
    TinygradInstance,
)
from wexo.shared.types.worker.runners import RunnerId, ShardAssignments
from wexo.shared.types.worker.shards import PipelineShardMetadata
from wexo.utils.channels import MpReceiver, MpSender, MpState
from wexo.utils.info_gatherer.info_gatherer import NodeBackends
from wexo.worker.disaggregated.server import PrefillRequest
from wexo.worker.engines.base import Builder, Engine


def test_device_map_covers_the_placement_registry() -> None:
    assert set(TINYGRAD_DEVICE_NAME_BY_BACKEND) == set(
        INSTANCE_META_BACKENDS[InstanceMeta.Tinygrad]
    )
    assert tinygrad_device_name_for_backend(Backend.TinygradAmd) == "AMD"
    assert tinygrad_device_name_for_backend(Backend.TinygradMetal) == "METAL"
    assert tinygrad_device_name_for_backend(Backend.TinygradCuda) == "CUDA"
    assert tinygrad_device_name_for_backend(Backend.TinygradCpu) == "CPU"
    assert tinygrad_device_name_for_backend(Backend.WinAMD) == "CL"
    assert tinygrad_device_name_for_backend(Backend.WinCUDA) == "CUDA"
    assert tinygrad_device_name_for_backend(Backend.WinCPU) == "CPU"


def test_non_tinygrad_backend_is_rejected() -> None:
    with pytest.raises(TinygradDeviceSelectionError, match="Vllm"):
        tinygrad_device_name_for_backend(Backend.Vllm)


def test_declared_devices_ignore_the_operating_system() -> None:
    assert backends_from_declared_devices([" METAL ", "", "AMD"]) == [
        Backend.TinygradMetal,
        Backend.TinygradAmd,
    ]
    with pytest.raises(TinygradDeviceSelectionError, match="linux"):
        backends_from_declared_devices(["linux"])


def test_assign_default_device_uses_the_requested_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTinygradDevice:
        DEFAULT: str = "CPU"

    class FakeTinygradModule(ModuleType):
        Device: type[FakeTinygradDevice]

    fake_module = FakeTinygradModule("tinygrad")
    fake_module.Device = FakeTinygradDevice
    monkeypatch.setitem(sys.modules, "tinygrad", fake_module)
    monkeypatch.setattr(sys, "platform", "unrecognized-platform")

    assert assign_tinygrad_default_device("AMD") == "AMD"
    assert FakeTinygradDevice.DEFAULT == "AMD"


def test_assign_default_device_reports_a_missing_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "tinygrad", None)
    with pytest.raises(TinygradDeviceSelectionError, match="not installed"):
        assign_tinygrad_default_device("METAL")


def _keep_device_name(device_name: TinygradDeviceName) -> TinygradDeviceName:
    return device_name


def test_engine_generation_requires_a_loaded_shard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("tinygrad")
    monkeypatch.setattr(
        "wexo.backends.tinygrad_engine.assign_tinygrad_default_device",
        _keep_device_name,
    )
    engine = TinygradEngine(device_name="CUDA")
    assert isinstance(engine, Engine)
    with pytest.raises(TinygradWeightError):
        engine.allocate_weights(_bound_instance())
    with pytest.raises(TinygradWeightError):
        engine.load_model(_bound_instance())
    with pytest.raises(TinygradWeightError):
        engine.warmup()
    with pytest.raises(TinygradWeightError):
        engine.step()
    with pytest.raises(NotImplementedError):
        engine.serve_prefill(PrefillRequest(), BytesIO())
    engine.close()
    assert engine.loaded_shard is None


def test_registry_rejects_tinygrad_image_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "wexo.backends.tinygrad_engine.assign_tinygrad_default_device",
        _keep_device_name,
    )
    bound_instance = _bound_instance(image_model=True)
    event_state: MpState[Event] = MpState(1)
    cancel_state: MpState[TaskId] = MpState(1)
    event_sender = MpSender(event_state)
    cancel_receiver = MpReceiver(cancel_state)
    try:
        with pytest.raises(ValueError, match="no image runtime"):
            resolve_builder(bound_instance, event_sender, cancel_receiver)
    finally:
        event_sender.close()
        cancel_receiver.close()


def test_registry_routes_tinygrad_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "wexo.backends.tinygrad_engine.assign_tinygrad_default_device",
        _keep_device_name,
    )
    bound_instance = _bound_instance()
    event_state: MpState[Event] = MpState(1)
    cancel_state: MpState[TaskId] = MpState(1)
    event_sender = MpSender(event_state)
    cancel_receiver = MpReceiver(cancel_state)
    try:
        builder = resolve_builder(bound_instance, event_sender, cancel_receiver)
    finally:
        event_sender.close()
        cancel_receiver.close()

    assert isinstance(builder, TinygradBuilder)
    assert isinstance(builder, Builder)
    assert builder.device_name == "AMD"
    builder.connect(bound_instance)
    with pytest.raises(TinygradWeightError):
        builder.build()


def test_windows_join_backends_never_advertise_non_windows_backends() -> None:
    assert windows_join_backends(
        declared_device_names=["AMD"],
        adapter_names=["NVIDIA GeForce"],
        has_nvidia_gpu=True,
    ) == [Backend.WinAMD]
    assert windows_join_backends(
        declared_device_names=[],
        adapter_names=["AMD Radeon RX 9700 XT", "NVIDIA GeForce RTX 4090"],
        has_nvidia_gpu=False,
    ) == [Backend.WinAMD, Backend.WinCUDA]
    assert windows_join_backends(
        declared_device_names=[],
        adapter_names=["Microsoft Basic Display Adapter"],
        has_nvidia_gpu=True,
    ) == [Backend.WinCUDA]
    assert windows_join_backends(
        declared_device_names=[" CPU "],
        adapter_names=[],
        has_nvidia_gpu=False,
    ) == [Backend.WinCPU]
    assert windows_join_backends(
        declared_device_names=[],
        adapter_names=[],
        has_nvidia_gpu=False,
    ) == [Backend.WinCPU]
    with pytest.raises(TinygradDeviceSelectionError, match="METAL"):
        windows_join_backends(
            declared_device_names=["METAL"],
            adapter_names=[],
            has_nvidia_gpu=False,
        )


async def test_windows_node_joins_as_win_amd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("EXO_TINYGRAD_DEVICES", raising=False)
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._windows_adapter_names",
        lambda: ["AMD Radeon RX 9700 XT"],
    )
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_nvml_cuda",
        lambda: False,
    )
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_directml_adapter",
        lambda: False,
    )
    monkeypatch.setattr(
        "wexo.backends.tinygrad_opencl.windows_opencl_is_usable",
        lambda: True,
    )
    gathered = await NodeBackends.gather()
    assert gathered.backends == [Backend.WinAMD, Backend.OnnxCpu]
    assert Backend.TinygradCpu not in gathered.backends


async def test_windows_node_falls_back_to_win_cpu_when_the_opencl_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("EXO_TINYGRAD_DEVICES", raising=False)
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._windows_adapter_names",
        lambda: ["AMD Radeon RX 9070 XT"],
    )
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_nvml_cuda",
        lambda: False,
    )
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_directml_adapter",
        lambda: False,
    )
    monkeypatch.setattr(
        "wexo.backends.tinygrad_opencl.windows_opencl_is_usable",
        lambda: False,
    )
    gathered = await NodeBackends.gather()
    assert gathered.backends == [Backend.WinCPU, Backend.OnnxCpu]


async def test_windows_node_drops_win_amd_when_the_opencl_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("EXO_TINYGRAD_DEVICES", raising=False)
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._windows_adapter_names",
        lambda: ["AMD Radeon RX 9070 XT", "NVIDIA GeForce RTX 4090"],
    )
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_nvml_cuda",
        lambda: False,
    )
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_directml_adapter",
        lambda: False,
    )
    monkeypatch.setattr(
        "wexo.backends.tinygrad_opencl.windows_opencl_is_usable",
        lambda: False,
    )
    gathered = await NodeBackends.gather()
    assert gathered.backends == [Backend.WinCUDA, Backend.OnnxCpu]
    assert Backend.WinAMD not in gathered.backends


async def test_windows_node_joins_as_win_cuda_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("EXO_TINYGRAD_DEVICES", "CUDA")
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_directml_adapter",
        lambda: False,
    )
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_nvml_cuda",
        lambda: False,
    )
    gathered = await NodeBackends.gather()
    assert gathered.backends == [Backend.WinCUDA, Backend.OnnxCpu]


async def test_windows_node_without_an_accelerator_joins_as_win_cpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("EXO_TINYGRAD_DEVICES", raising=False)
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._windows_adapter_names",
        lambda: ["Microsoft Basic Display Adapter"],
    )
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_nvml_cuda",
        lambda: False,
    )
    monkeypatch.setattr(
        "wexo.utils.info_gatherer.info_gatherer._has_directml_adapter",
        lambda: False,
    )
    gathered = await NodeBackends.gather()
    assert gathered.backends == [Backend.WinCPU, Backend.OnnxCpu]


async def test_node_backends_include_declared_tinygrad_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("EXO_TINYGRAD_DEVICES", "AMD,CUDA")
    gathered = await NodeBackends.gather()
    assert Backend.TinygradAmd in gathered.backends
    assert Backend.TinygradCuda in gathered.backends
    assert Backend.TinygradMetal not in gathered.backends


def _bound_instance(*, image_model: bool = False) -> BoundInstance:
    model_id = ModelId("tinygrad-model")
    node_id = NodeId("node-amd")
    runner_id = RunnerId("runner-amd")
    model_card = ModelCard(
        model_id=model_id,
        storage_size=Memory.from_mb(16),
        n_layers=4,
        hidden_size=32,
        supports_tensor=False,
        tasks=[ModelTask.TextToImage if image_model else ModelTask.TextGeneration],
        backends=[Backend.TinygradAmd],
    )
    shard = PipelineShardMetadata(
        model_card=model_card,
        device_rank=0,
        world_size=1,
        start_layer=0,
        end_layer=4,
        n_layers=4,
    )
    instance = TinygradInstance(
        instance_id=InstanceId("tinygrad-instance"),
        shard_assignments=ShardAssignments(
            model_id=model_id,
            node_to_runner={node_id: runner_id},
            runner_to_shard={runner_id: shard},
        ),
        device_backend_by_node={node_id: Backend.TinygradAmd},
    )
    return BoundInstance(
        instance=instance,
        bound_runner_id=runner_id,
        bound_node_id=node_id,
    )
