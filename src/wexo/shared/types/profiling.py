import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Self

import psutil

from wexo.shared.types.memory import Memory
from wexo.shared.types.thunderbolt import ThunderboltIdentifier
from wexo.utils.pydantic_ext import FrozenModel

type MemoryEstimateSource = Literal[
    "psutil",
    "opencl-global",
    "opencl-amd-free",
    "override",
    "rocm-smi",
    "nvidia-smi",
    "unavailable",
]


class AcceleratorMemorySample(FrozenModel):
    """Device capacity kept apart from the host RAM reading.

    ``free_sample`` is the probe's number. ``ceiling`` is capacity minus
    placements this process has reserved. ``estimate_source`` names which
    reading produced the available bytes placement uses.
    """

    capacity: Memory
    free_sample: Memory
    max_allocation: Memory | None = None
    host_ram_total: Memory
    host_ram_available: Memory
    reserved: Memory
    ceiling: Memory
    estimate_source: MemoryEstimateSource
    driver_version: str = ""


def accelerator_sample_from_bytes(
    *,
    capacity_bytes: int,
    free_sample_bytes: int,
    max_allocation_bytes: int | None,
    host_ram_total_bytes: int,
    host_ram_available_bytes: int,
    reserved_bytes: int,
    estimate_source: MemoryEstimateSource,
    driver_version: str,
) -> AcceleratorMemorySample:
    """Build a sample. ``ceiling`` is capacity minus ``reserved_bytes``."""
    return AcceleratorMemorySample(
        capacity=Memory.from_bytes(capacity_bytes),
        free_sample=Memory.from_bytes(free_sample_bytes),
        max_allocation=(
            None
            if max_allocation_bytes is None
            else Memory.from_bytes(max_allocation_bytes)
        ),
        host_ram_total=Memory.from_bytes(host_ram_total_bytes),
        host_ram_available=Memory.from_bytes(host_ram_available_bytes),
        reserved=Memory.from_bytes(reserved_bytes),
        ceiling=Memory.from_bytes(max(capacity_bytes - reserved_bytes, 0)),
        estimate_source=estimate_source,
        driver_version=driver_version,
    )


def host_ram_bytes() -> tuple[int, int]:
    """Return ``(total, available)`` host RAM from psutil."""
    virtual = psutil.virtual_memory()
    return virtual.total, virtual.available


class MemoryUsage(FrozenModel):
    ram_total: Memory
    ram_available: Memory
    swap_total: Memory
    swap_available: Memory
    accelerator: AcceleratorMemorySample | None = None

    @classmethod
    def from_bytes(
        cls,
        *,
        ram_total: int,
        ram_available: int,
        swap_total: int,
        swap_available: int,
        accelerator: AcceleratorMemorySample | None = None,
    ) -> Self:
        return cls(
            ram_total=Memory.from_bytes(ram_total),
            ram_available=Memory.from_bytes(ram_available),
            swap_total=Memory.from_bytes(swap_total),
            swap_available=Memory.from_bytes(swap_available),
            accelerator=accelerator,
        )

    @classmethod
    def from_psutil(cls, *, override_memory: int | None) -> Self:
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()

        return cls.from_bytes(
            ram_total=vm.total,
            ram_available=vm.available if override_memory is None else override_memory,
            swap_total=sm.total,
            swap_available=sm.free,
        )


class DiskUsage(FrozenModel):
    """Disk space usage for the models directory."""

    total: Memory
    available: Memory

    @classmethod
    def from_path(cls, path: Path) -> Self:
        """Get disk usage stats for the partition containing path."""
        total, _used, free = shutil.disk_usage(path)
        return cls(
            total=Memory.from_bytes(total),
            available=Memory.from_bytes(free),
        )


class SystemPerformanceProfile(FrozenModel):
    # TODO: flops_fp16: float

    gpu_usage: float = 0.0
    temp: float = 0.0
    sys_power: float = 0.0
    pcpu_usage: float = 0.0
    ecpu_usage: float = 0.0


InterfaceType = Literal["wifi", "ethernet", "maybe_ethernet", "thunderbolt", "unknown"]


class NetworkInterfaceInfo(FrozenModel):
    name: str
    ip_address: str
    interface_type: InterfaceType = "unknown"


class NodeIdentity(FrozenModel):
    """Static and slow-changing node identification data."""

    model_id: str = "Unknown"
    chip_id: str = "Unknown"
    friendly_name: str = "Unknown"
    os_version: str = "Unknown"
    os_build_version: str = "Unknown"


class NodeNetworkInfo(FrozenModel):
    """Network interface information for a node."""

    interfaces: Sequence[NetworkInterfaceInfo] = []


class NodeThunderboltInfo(FrozenModel):
    """Thunderbolt interface identifiers for a node."""

    interfaces: Sequence[ThunderboltIdentifier] = []


class NodeRdmaCtlStatus(FrozenModel):
    """Whether RDMA is enabled on this node (via rdma_ctl)."""

    enabled: bool


class ThunderboltBridgeStatus(FrozenModel):
    """Whether the Thunderbolt Bridge network service is enabled on this node."""

    enabled: bool
    exists: bool
    service_name: str | None = None
