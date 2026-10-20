"""Pure OpenCL adapter selection, plus a live Windows probe when an ICD exists."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from wexo.backends.tinygrad_engine import assign_tinygrad_default_device
from wexo.backends.tinygrad_opencl import (
    OpenClAdapter,
    OpenClSelectionError,
    classify_opencl_free_sample,
    clear_opencl_resolution_cache,
    interpret_amd_free_memory_bytes,
    opencl_driver_versions,
    opencl_memory_bytes,
    probe_numerics_match,
    read_opencl_adapter_preference,
    remember_opencl_adapter,
    resolve_usable_opencl_adapter,
    select_opencl_adapter,
)

_DISCRETE_BYTES = 17_095_983_104
_INTEGRATED_BYTES = 38_431_784_960
_AMD_FREE_KILOBYTES = (16_671_616, 16_577_056, 0, 0)


def _adapter(
    *,
    platform_index: int,
    device_index: int,
    device_name: str,
    global_memory_bytes: int,
    host_unified_memory: bool,
) -> OpenClAdapter:
    return OpenClAdapter(
        platform_index=platform_index,
        device_index=device_index,
        platform_name="AMD Accelerated Parallel Processing",
        device_name=device_name,
        vendor="Advanced Micro Devices, Inc.",
        driver_version="3679.0",
        global_memory_bytes=global_memory_bytes,
        max_allocation_bytes=global_memory_bytes // 2,
        host_unified_memory=host_unified_memory,
        supports_fp16=True,
    )


def _mixed_adapters() -> list[OpenClAdapter]:
    return [
        _adapter(
            platform_index=0,
            device_index=0,
            device_name="gfx1201",
            global_memory_bytes=_DISCRETE_BYTES,
            host_unified_memory=False,
        ),
        _adapter(
            platform_index=0,
            device_index=1,
            device_name="gfx1036",
            global_memory_bytes=_INTEGRATED_BYTES,
            host_unified_memory=True,
        ),
        _adapter(
            platform_index=1,
            device_index=0,
            device_name="gfx1201",
            global_memory_bytes=_DISCRETE_BYTES,
            host_unified_memory=False,
        ),
        _adapter(
            platform_index=1,
            device_index=1,
            device_name="gfx1036",
            global_memory_bytes=_INTEGRATED_BYTES,
            host_unified_memory=True,
        ),
    ]


def test_default_selection_prefers_discrete_memory_over_a_larger_igpu() -> None:
    selected = select_opencl_adapter(_mixed_adapters(), None)
    assert selected is not None
    assert selected.device_name == "gfx1201"
    assert selected.platform_index == 0
    assert selected.device_index == 0
    assert selected.host_unified_memory is False


def test_named_preference_collapses_duplicate_platforms() -> None:
    selected = select_opencl_adapter(_mixed_adapters(), "gfx1201")
    assert selected is not None
    assert (selected.platform_index, selected.device_index) == (0, 0)


def test_ambiguous_name_does_not_guess() -> None:
    assert select_opencl_adapter(_mixed_adapters(), "gfx") is None


def test_platform_device_preference_can_select_the_integrated_gpu() -> None:
    selected = select_opencl_adapter(_mixed_adapters(), "0:1")
    assert selected is not None
    assert selected.device_name == "gfx1036"
    first = select_opencl_adapter(_mixed_adapters(), "CL:0")
    assert first is not None
    assert first.device_index == 0
    assert select_opencl_adapter(_mixed_adapters(), "9:9") is None


def test_environment_preference_wins_over_the_file() -> None:
    assert (
        read_opencl_adapter_preference(
            environment_value="gfx1036",
            file_text="gfx1201\n",
        )
        == "gfx1036"
    )
    assert (
        read_opencl_adapter_preference(
            environment_value="  ",
            file_text="gfx1201\n",
        )
        == "gfx1201"
    )
    assert (
        read_opencl_adapter_preference(environment_value=None, file_text=None) is None
    )


def test_remember_opencl_adapter_writes_one_line(tmp_path: Path) -> None:
    path = tmp_path / "config" / "opencl-adapter"
    remember_opencl_adapter("gfx1201", path)
    assert path.read_text(encoding="utf-8") == "gfx1201\n"
    with pytest.raises(OpenClSelectionError):
        remember_opencl_adapter("gfx\n1201", path)


def test_amd_free_memory_words_are_kilobytes() -> None:
    available = interpret_amd_free_memory_bytes(_AMD_FREE_KILOBYTES, _DISCRETE_BYTES)
    assert available == min(_AMD_FREE_KILOBYTES[0], _AMD_FREE_KILOBYTES[1]) * 1024
    assert available is not None
    assert available <= _DISCRETE_BYTES


def test_amd_free_memory_accepts_a_raw_byte_count() -> None:
    assert interpret_amd_free_memory_bytes((800,), 1000) == 800
    assert interpret_amd_free_memory_bytes((0, 0), 1000) is None
    assert interpret_amd_free_memory_bytes((10,), 0) is None


def test_missing_amd_reading_uses_the_global_size() -> None:
    free_bytes, source = classify_opencl_free_sample(1000, None)
    assert free_bytes == 1000
    assert source == "opencl-global"
    capped, amd_source = classify_opencl_free_sample(1000, 2500)
    assert capped == 1000
    assert amd_source == "opencl-amd-free"


def test_probe_numerics_require_fp16_when_the_device_advertises_it() -> None:
    assert probe_numerics_match(dot_product=10.0, fp16_sum=3.0, supports_fp16=True)
    assert not probe_numerics_match(dot_product=10.0, fp16_sum=None, supports_fp16=True)
    assert probe_numerics_match(dot_product=10.0, fp16_sum=None, supports_fp16=False)
    assert not probe_numerics_match(dot_product=9.0, fp16_sum=3.0, supports_fp16=True)


def test_live_opencl_probe_pins_the_discrete_gpu(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if sys.platform != "win32":
        pytest.skip("OpenCL.dll is the Windows ICD")
    pytest.importorskip("tinygrad")
    monkeypatch.delenv("EXO_OPENCL_ADAPTER", raising=False)
    monkeypatch.setattr(
        "wexo.backends.tinygrad_opencl.opencl_adapter_preference_path",
        lambda: tmp_path / "opencl-adapter",
    )
    clear_opencl_resolution_cache()
    from tinygrad.runtime.ops_cl import CLDevice

    CLDevice.device_ids = None
    adapter = resolve_usable_opencl_adapter()
    if adapter is None:
        pytest.skip("OpenCL probe did not accept a GPU")
    assert adapter.host_unified_memory is False
    assign_tinygrad_default_device("CL")
    opened = CLDevice("CL")
    assert opened.device_name == adapter.device_name
    measured = opencl_memory_bytes()
    assert measured is not None
    total_bytes, available_bytes = measured
    assert total_bytes == adapter.global_memory_bytes
    assert 0 < available_bytes <= total_bytes


def test_live_opencl_driver_versions_include_the_selected_adapter() -> None:
    if sys.platform != "win32":
        pytest.skip("OpenCL.dll is the Windows ICD")
    adapter = resolve_usable_opencl_adapter()
    if adapter is None:
        pytest.skip("OpenCL probe did not accept a GPU")
    versions = opencl_driver_versions()
    assert (adapter.device_name, adapter.driver_version) in versions
    assert adapter.driver_version != ""
