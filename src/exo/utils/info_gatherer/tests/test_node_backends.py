from unittest import mock

from exo.shared.types.backends import Backend
from exo.utils.info_gatherer import info_gatherer, windows_gpu


async def test_windows_backends_when_directml_present_and_no_nvidia():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "win32"),
        mock.patch.object(
            info_gatherer, "collect_windows_join_backends", lambda: [Backend.WinCPU]
        ),
        mock.patch.object(info_gatherer, "_has_directml_adapter", lambda: True),
        mock.patch.object(info_gatherer, "_has_nvml_cuda", lambda: False),
    ):
        result = await info_gatherer.NodeBackends.gather()
    assert result.backends == [
        Backend.WinCPU,
        Backend.OnnxCpu,
        Backend.OnnxDirectMl,
    ]


async def test_windows_backends_when_directml_and_nvidia_both_present():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "win32"),
        mock.patch.object(
            info_gatherer,
            "collect_windows_join_backends",
            lambda: [Backend.WinCUDA],
        ),
        mock.patch.object(info_gatherer, "_has_directml_adapter", lambda: True),
        mock.patch.object(info_gatherer, "_has_nvml_cuda", lambda: True),
    ):
        result = await info_gatherer.NodeBackends.gather()
    assert result.backends == [
        Backend.WinCUDA,
        Backend.OnnxCpu,
        Backend.OnnxDirectMl,
        Backend.OnnxCuda,
    ]


async def test_windows_backends_when_no_gpu_falls_back_to_cpu_only():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "win32"),
        mock.patch.object(
            info_gatherer, "collect_windows_join_backends", lambda: [Backend.WinCPU]
        ),
        mock.patch.object(info_gatherer, "_has_directml_adapter", lambda: False),
        mock.patch.object(info_gatherer, "_has_nvml_cuda", lambda: False),
    ):
        result = await info_gatherer.NodeBackends.gather()
    assert result.backends == [Backend.WinCPU, Backend.OnnxCpu]


async def test_windows_backends_when_directml_probe_raises_does_not_propagate():
    def _raising_probe() -> bool:
        raise RuntimeError("dxgi probe blew up")

    with (
        mock.patch.object(info_gatherer.sys, "platform", "win32"),
        mock.patch.object(
            info_gatherer, "collect_windows_join_backends", lambda: [Backend.WinCPU]
        ),
        mock.patch.object(windows_gpu, "_probe_directml_adapter", _raising_probe),
        mock.patch.object(info_gatherer, "_has_nvml_cuda", lambda: False),
    ):
        result = await info_gatherer.NodeBackends.gather()
    assert Backend.OnnxCpu in result.backends
    assert Backend.OnnxDirectMl not in result.backends


async def test_windows_backends_contain_no_mlx_or_vllm_members():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "win32"),
        mock.patch.object(
            info_gatherer, "collect_windows_join_backends", lambda: [Backend.WinCUDA]
        ),
        mock.patch.object(info_gatherer, "_has_directml_adapter", lambda: True),
        mock.patch.object(info_gatherer, "_has_nvml_cuda", lambda: True),
    ):
        result = await info_gatherer.NodeBackends.gather()
    assert Backend.TinygradCpu not in result.backends
    assert Backend.TinygradMetal not in result.backends
    assert Backend.TinygradCuda not in result.backends
    assert Backend.Vllm not in result.backends


async def test_darwin_defaults_to_tinygrad_metal():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "darwin"),
        mock.patch.object(info_gatherer, "IS_DARWIN", True),
        mock.patch.object(info_gatherer, "_has_nvml_cuda", lambda: False),
        mock.patch.dict(info_gatherer.os.environ, {}, clear=False),
    ):
        info_gatherer.os.environ.pop("EXO_INFERENCE_RUNTIME", None)
        info_gatherer.os.environ.pop("EXO_TINYGRAD_DEVICES", None)
        result = await info_gatherer.NodeBackends.gather()
    assert result.backends == [Backend.TinygradMetal]


async def test_darwin_tinygrad_runtime_advertises_only_metal():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "darwin"),
        mock.patch.object(info_gatherer, "IS_DARWIN", True),
        mock.patch.dict(
            info_gatherer.os.environ,
            {"EXO_INFERENCE_RUNTIME": "tinygrad"},
            clear=False,
        ),
    ):
        info_gatherer.os.environ.pop("EXO_TINYGRAD_DEVICES", None)
        result = await info_gatherer.NodeBackends.gather()
    assert result.backends == [Backend.TinygradMetal]
    assert Backend.TinygradCpu not in result.backends


async def test_unknown_inference_runtime_value_uses_tinygrad_path():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "darwin"),
        mock.patch.object(info_gatherer, "IS_DARWIN", True),
        mock.patch.object(info_gatherer, "_has_nvml_cuda", lambda: False),
        mock.patch.dict(
            info_gatherer.os.environ,
            {"EXO_INFERENCE_RUNTIME": "unknown"},
            clear=False,
        ),
    ):
        info_gatherer.os.environ.pop("EXO_TINYGRAD_DEVICES", None)
        result = await info_gatherer.NodeBackends.gather()
    assert result.backends == [Backend.TinygradMetal]


async def test_linux_defaults_to_tinygrad_cpu():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "linux"),
        mock.patch.object(info_gatherer, "IS_DARWIN", False),
        mock.patch.object(info_gatherer, "_has_nvml_cuda", lambda: False),
        mock.patch.dict(info_gatherer.os.environ, {}, clear=False),
    ):
        info_gatherer.os.environ.pop("EXO_INFERENCE_RUNTIME", None)
        info_gatherer.os.environ.pop("EXO_TINYGRAD_DEVICES", None)
        result = await info_gatherer.NodeBackends.gather()
    assert result.backends == [Backend.TinygradCpu]


async def test_declared_tinygrad_devices_override_platform_default():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "linux"),
        mock.patch.object(info_gatherer, "IS_DARWIN", False),
        mock.patch.dict(
            info_gatherer.os.environ,
            {"EXO_TINYGRAD_DEVICES": " CUDA, CPU "},
            clear=False,
        ),
    ):
        info_gatherer.os.environ.pop("EXO_INFERENCE_RUNTIME", None)
        result = await info_gatherer.NodeBackends.gather()
    assert result.backends == [Backend.TinygradCuda, Backend.TinygradCpu]


async def test_whitespace_only_device_override_uses_platform_default():
    with (
        mock.patch.object(info_gatherer.sys, "platform", "linux"),
        mock.patch.object(info_gatherer, "IS_DARWIN", False),
        mock.patch.dict(
            info_gatherer.os.environ,
            {"EXO_TINYGRAD_DEVICES": " ,  "},
            clear=False,
        ),
    ):
        info_gatherer.os.environ.pop("EXO_INFERENCE_RUNTIME", None)
        result = await info_gatherer.NodeBackends.gather()
    assert result.backends == [Backend.TinygradCpu]
