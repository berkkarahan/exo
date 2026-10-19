from pathlib import Path

from scripts.sync_gpu import (
    accelerator_install_command,
    amd_torch_device_extra,
    selected_extras,
)


def test_windows_selects_rocm_for_amd_and_cuda_for_nvidia() -> None:
    assert selected_extras("win32", ["AMD Radeon RX 9070 XT"]) == ["torch-amd"]
    assert selected_extras("win32", ["NVIDIA GeForce RTX 4090"]) == ["torch-cuda"]


def test_nvidia_takes_priority_on_a_mixed_windows_system() -> None:
    assert selected_extras("win32", ["AMD Radeon RX 9070 XT", "NVIDIA RTX 4090"]) == [
        "torch-cuda"
    ]


def test_linux_and_macos_select_their_accelerator_profiles() -> None:
    assert selected_extras("linux", ["NVIDIA RTX 5090"]) == ["mlx-cuda13"]
    assert selected_extras("linux", ["AMD Radeon RX 9070 XT"]) == ["torch-rocm"]
    assert selected_extras("darwin", []) == ["mlx"]


def test_unknown_or_cpu_adapters_use_the_platform_default() -> None:
    assert selected_extras("win32", ["Microsoft Basic Display Adapter"]) == []
    assert selected_extras("linux", []) == []


def test_amd_windows_install_uses_the_rocm_python_313_wheel_index() -> None:
    command = accelerator_install_command(
        "win32",
        ["torch-amd"],
        Path(".venv/Scripts/python.exe"),
        adapter_names=["AMD Radeon RX 9070 XT"],
    )
    assert command is not None
    assert "https://stable.repo.amd.com/rocm/whl-next/" in command
    assert "torch[device-gfx1201]==2.13.0+rocm10.0.0" in command
    assert "--python" in command
    assert Path(".venv/Scripts/python.exe") == Path(
        command[command.index("--python") + 1]
    )


def test_nvidia_windows_install_uses_cuda_wheels() -> None:
    command = accelerator_install_command(
        "win32", ["torch-cuda"], Path(".venv/Scripts/python.exe")
    )
    assert command is not None
    assert "https://download.pytorch.org/whl/cu130" in command
    assert "torch==2.10.0" in command


def test_amd_hardware_maps_to_its_specific_rocm_wheel() -> None:
    assert amd_torch_device_extra(["AMD Radeon RX 9070 XT"]) == "device-gfx1201"
    assert amd_torch_device_extra(["Radeon RX 7900 XTX"]) == "device-gfx1100"
    assert amd_torch_device_extra(["unknown AMD GPU"]) == "device-all"
