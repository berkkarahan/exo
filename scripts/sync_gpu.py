"""Synchronize the project environment with the current platform's GPU backend."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def selected_extras(platform: str, adapter_names: Sequence[str]) -> list[str]:
    """Return the project extra matching this OS and its detected GPU adapters."""
    names = " ".join(adapter_names).casefold()
    if platform == "darwin":
        return ["mlx"]
    if platform == "win32":
        if any(token in names for token in ("nvidia", "geforce", "quadro")):
            return ["torch-cuda"]
        if any(token in names for token in ("amd", "radeon")):
            return ["torch-amd"]
    if platform == "linux":
        if any(token in names for token in ("nvidia", "geforce", "quadro")):
            return ["mlx-cuda13"]
        if any(token in names for token in ("amd", "radeon")):
            return ["torch-rocm"]
    return []


def _windows_adapters() -> list[str]:
    command = "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }"
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _linux_adapters() -> list[str]:
    adapters: list[str] = []
    for vendor_file in Path("/sys/class/drm").glob("card*/device/vendor"):
        try:
            vendor = vendor_file.read_text(encoding="ascii").strip().casefold()
        except OSError:
            continue
        if vendor == "0x1002":
            adapters.append("AMD Radeon")
        elif vendor == "0x10de":
            adapters.append("NVIDIA")
    if not adapters and shutil.which("nvidia-smi"):
        adapters.append("NVIDIA")
    if any("amd" in name.casefold() for name in adapters) and shutil.which("rocminfo"):
        result = subprocess.run(
            ["rocminfo"],
            capture_output=True,
            check=False,
            text=True,
            timeout=20,
        )
        adapters.extend(re.findall(r"\bName:\s*(gfx[0-9a-z-]+)", result.stdout))
    return adapters


def detected_adapters(platform: str) -> list[str]:
    if platform == "win32":
        adapters = _windows_adapters()
        if shutil.which("nvidia-smi") and not any(
            "nvidia" in name.casefold() for name in adapters
        ):
            adapters.append("NVIDIA")
        return adapters
    if platform == "linux":
        return _linux_adapters()
    return []


def amd_torch_device_extra(adapter_names: Sequence[str]) -> str:
    """Choose the ROCm wheel for a known AMD GPU architecture."""
    names = " ".join(adapter_names).casefold()
    if "gfx1201" in names or any(
        token in names for token in ("rx 9070", "ai pro r9700")
    ):
        return "device-gfx1201"
    if "gfx1200" in names or "rx 9060" in names:
        return "device-gfx1200"
    if "gfx1100" in names or "rx 7900" in names or "pro w7900" in names:
        return "device-gfx1100"
    if "gfx1101" in names or any(token in names for token in ("rx 7800", "rx 7700")):
        return "device-gfx1101"
    if "gfx1102" in names or "rx 7600" in names:
        return "device-gfx1102"
    if "gfx1032" in names or "rx 6600" in names:
        return "device-gfx1032"
    if "gfx1030" in names or "rx 6800" in names:
        return "device-gfx1030"
    return "device-all"


def accelerator_install_command(
    platform: str,
    profile: Sequence[str],
    python: Path,
    *,
    adapter_names: Sequence[str] = (),
    force_reinstall: bool = False,
    no_cache: bool = False,
) -> list[str] | None:
    """Build the pip command for GPU wheels that cannot be selected by OS markers."""
    if profile == ["torch-cuda"] and platform == "win32":
        index = "https://download.pytorch.org/whl/cu130"
        packages = ["torch==2.10.0"]
    elif (profile == ["torch-amd"] and platform == "win32") or (
        profile == ["torch-rocm"] and platform == "linux"
    ):
        index = "https://stable.repo.amd.com/rocm/whl-next/"
        device_extra = amd_torch_device_extra(adapter_names)
        packages = [f"torch[{device_extra}]==2.13.0+rocm10.0.0"]
    else:
        return None

    command = [
        "uv",
        "pip",
        "install",
        "--python",
        str(python),
        "--index-url",
        index,
    ]
    if force_reinstall:
        command.append("--reinstall")
    if no_cache:
        command.append("--no-cache")
    return [*command, *packages]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-reinstall", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    arguments = sys.argv[1:]
    if "-h" in arguments or "--help" in arguments:
        parser.print_help()
        return 0
    supported_arguments = {"--force-reinstall", "--no-cache", "--dry-run"}
    if unsupported := set(arguments) - supported_arguments:
        parser.error(f"unrecognized arguments: {' '.join(sorted(unsupported))}")
    force_reinstall = "--force-reinstall" in arguments
    no_cache = "--no-cache" in arguments
    dry_run = "--dry-run" in arguments

    adapters = detected_adapters(sys.platform)
    extras = selected_extras(sys.platform, adapters)
    command = ["uv", "sync", "--all-packages"]
    sync_extras = [extra for extra in extras if extra in ("mlx", "mlx-cuda13")]
    for extra in sync_extras:
        command.extend(["--extra", extra])
    if force_reinstall:
        command.append("--force-reinstall")
    if no_cache:
        command.append("--no-cache")
    print(f"GPU profile: {', '.join(extras) if extras else 'CPU / platform default'}")
    if dry_run:
        print(" ".join(command))
        python = Path(".venv") / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        install_command = accelerator_install_command(
            sys.platform,
            extras,
            python,
            adapter_names=adapters,
            force_reinstall=force_reinstall,
            no_cache=no_cache,
        )
        if install_command is not None:
            print(" ".join(install_command))
        return 0
    sync_result = subprocess.run(command, check=False)
    if sync_result.returncode != 0:
        return sync_result.returncode

    python = Path(".venv") / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    install_command = accelerator_install_command(
        sys.platform,
        extras,
        python,
        adapter_names=adapters,
        force_reinstall=force_reinstall,
        no_cache=no_cache,
    )
    if install_command is None:
        return 0
    return subprocess.run(install_command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
