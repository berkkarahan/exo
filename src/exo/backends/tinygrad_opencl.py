"""Choose the OpenCL adapter tinygrad uses for a Windows AMD node.

Tinygrad 0.14 opens GPU devices from the first platform only. An integrated
GPU on that platform can report a larger ``CL_DEVICE_GLOBAL_MEM_SIZE`` than
the discrete GPU because the value includes shared system memory. Selection
prefers a non-unified adapter, the numeric probe runs before ``WinAMD`` is
advertised, and the runner pins that device into ``CLDevice.device_ids``.
"""

from __future__ import annotations

import ctypes
import math
import os
import struct
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, final

from loguru import logger

from exo.utils.pydantic_ext import FrozenModel

_PROBE_TIMEOUT_SECONDS = 10.0
_CL_SUCCESS = 0
_CL_DEVICE_TYPE_GPU = 4
_CL_PLATFORM_NAME = 0x0902
_CL_DEVICE_NAME = 0x102B
_CL_DEVICE_VENDOR = 0x102C
_CL_DRIVER_VERSION = 0x102D
_CL_DEVICE_GLOBAL_MEM_SIZE = 0x101F
_CL_DEVICE_MAX_MEM_ALLOC_SIZE = 0x1010
_CL_DEVICE_EXTENSIONS = 0x1030
_CL_DEVICE_HOST_UNIFIED_MEMORY = 0x1035
_CL_DEVICE_GLOBAL_FREE_MEMORY_AMD = 0x4039
_CL_CONTEXT_PLATFORM = 0x1084
_CL_PROGRAM_BUILD_LOG = 0x1183
_CL_MEM_READ_ONLY = 4
_CL_MEM_WRITE_ONLY = 2
_CL_MEM_COPY_HOST_PTR = 32
_DOT_KERNEL = """
__kernel void probe_dot(
    __global const float *left,
    __global const float *right,
    __global float *out
) {
    float accumulated = 0.0f;
    for (int index = 0; index < 4; index++) {
        accumulated += left[index] * right[index];
    }
    out[0] = accumulated;
}
"""
_HALF_KERNEL = """
#pragma OPENCL EXTENSION cl_khr_fp16 : enable
__kernel void probe_half(__global half *out) {
    out[0] = (half)1.0 + (half)2.0;
}
"""
_DOT_LEFT = (1.0, 2.0, 3.0, 4.0)
_DOT_RIGHT = (1.0, 1.0, 1.0, 1.0)
_DOT_EXPECTED = 10.0
_HALF_EXPECTED = 3.0


@final
class OpenClSelectionError(Exception):
    """Raised when the runner cannot pin a probed OpenCL adapter.

    ``assign_tinygrad_default_device`` transforms this into
    ``TinygradDeviceSelectionError``. The runner entrypoint handles that by
    publishing ``RunnerTerminationError``.
    """


@final
class OpenClProbeError(Exception):
    """Raised when enumeration or the numeric kernel cannot finish.

    ``OpenClRuntime.resolve`` handles this by logging and caching "no
    adapter". ``collect_windows_join_backends`` then drops ``WinAMD`` so
    startup still advertises ``WinCPU``.
    """


@final
class OpenClAdapter(FrozenModel):
    """One GPU device on one OpenCL platform."""

    platform_index: int
    device_index: int
    platform_name: str
    device_name: str
    vendor: str
    driver_version: str
    global_memory_bytes: int
    max_allocation_bytes: int
    host_unified_memory: bool
    supports_fp16: bool


def select_opencl_adapter(
    adapters: Sequence[OpenClAdapter],
    preference: str | None,
) -> OpenClAdapter | None:
    """Return the adapter ``preference`` names, or the discrete default.

    An empty preference uses the largest non-unified GPU. Equal sizes keep
    the lowest platform index, then the lowest device index. ``platform:device``
    and ``CL:device`` are exact indexes. Any other text must match one device
    name; duplicate platforms for that name collapse to the lowest index.
    """
    if len(adapters) == 0:
        return None
    if preference is None or preference.strip() == "":
        return _default_opencl_adapter(adapters)
    stripped = preference.strip()
    indexed = _parse_platform_device(stripped)
    if indexed is not None:
        platform_index, device_index = indexed
        for adapter in adapters:
            if (
                adapter.platform_index == platform_index
                and adapter.device_index == device_index
            ):
                return adapter
        return None
    lowered = stripped.casefold()
    exact = [
        adapter for adapter in adapters if adapter.device_name.casefold() == lowered
    ]
    if exact:
        return _earliest_adapter(exact)
    partial = [
        adapter for adapter in adapters if lowered in adapter.device_name.casefold()
    ]
    names = {adapter.device_name.casefold() for adapter in partial}
    if len(names) != 1:
        return None
    return _earliest_adapter(partial)


def read_opencl_adapter_preference(
    *,
    environment_value: str | None,
    file_text: str | None,
) -> str | None:
    """Return the explicit adapter choice.

    The environment value wins. A blank environment value and a missing or
    blank file both mean "use the discrete default".
    """
    if environment_value is not None and environment_value.strip() != "":
        return environment_value.strip()
    if file_text is None:
        return None
    stripped = file_text.strip()
    if stripped == "":
        return None
    return stripped


def interpret_amd_free_memory_bytes(
    words: Sequence[int],
    global_memory_bytes: int,
) -> int | None:
    """Return free bytes from ``CL_DEVICE_GLOBAL_FREE_MEMORY_AMD``.

    AMD publishes kilobytes. The smaller positive word is the tighter limit.
    Kilobytes are used when they fit in ``global_memory_bytes``; a raw byte
    count is used when the kilobyte scaling would exceed that size.
    """
    if global_memory_bytes <= 0:
        return None
    positive = [word for word in words if word > 0]
    if not positive:
        return None
    raw = min(positive)
    scaled = raw * 1024
    if scaled <= global_memory_bytes:
        return scaled
    if raw <= global_memory_bytes:
        return raw
    return None


def probe_numerics_match(
    *,
    dot_product: float,
    fp16_sum: float | None,
    supports_fp16: bool,
) -> bool:
    """Return whether the probe kernels produced the known results."""
    if dot_product != _DOT_EXPECTED:
        return False
    if not supports_fp16:
        return fp16_sum is None
    if fp16_sum is None:
        return False
    return abs(fp16_sum - _HALF_EXPECTED) < 1e-3


def remember_opencl_adapter(device_name: str, path: Path) -> None:
    """Write ``device_name`` as the sole line of ``path``.

    Raises:
        OpenClSelectionError: ``device_name`` is blank or contains a newline.
            Callers that persist a probed name only pass ``device_name`` from
            an ``OpenClAdapter``, which is a single line.
        OSError: The directory cannot be created or the file cannot be
            written. ``OpenClRuntime.resolve`` catches this so a read-only
            config home still leaves the probed adapter selected.
    """
    stripped = device_name.strip()
    if stripped == "" or "\n" in stripped or "\r" in stripped:
        raise OpenClSelectionError("OpenCL adapter name must be a single line")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stripped + "\n", encoding="utf-8")


def opencl_adapter_preference_path() -> Path:
    """Return the file that stores the last implicit adapter name."""
    from exo.shared.constants import EXO_CONFIG_HOME

    return EXO_CONFIG_HOME / "opencl-adapter"


def resolve_usable_opencl_adapter() -> OpenClAdapter | None:
    """Return the probed adapter, or None when OpenCL cannot run the kernel.

    The result is cached for the process. ``collect_windows_join_backends``
    treats None as "do not advertise WinAMD".
    """
    return _RUNTIME.resolve()


def clear_opencl_resolution_cache() -> None:
    """Forget the cached probe so the next resolve reads the machine again."""
    _RUNTIME.clear_resolution()


def windows_opencl_is_usable() -> bool:
    """Return whether join should advertise ``WinAMD``.

    ``OSError``, ``OpenClProbeError``, and any other failure are handled here
    and become False. A broken ICD must not stop node startup.
    ``collect_windows_join_backends`` then drops ``WinAMD``. The runner does
    not use this function; ``pin_selected_opencl_device`` raises instead.
    """
    try:
        return resolve_usable_opencl_adapter() is not None
    except Exception as error:
        logger.warning(f"OpenCL adapter probe failed: {error}")
        return False


@final
class OpenClMemoryReading(FrozenModel):
    """Capacity and free sample for the probed OpenCL adapter."""

    capacity_bytes: int
    free_sample_bytes: int
    max_allocation_bytes: int
    driver_version: str
    estimate_source: Literal["opencl-global", "opencl-amd-free"]


def classify_opencl_free_sample(
    global_memory_bytes: int, measured_bytes: int | None
) -> tuple[int, Literal["opencl-global", "opencl-amd-free"]]:
    """Return the free sample and the name of the reading that produced it.

    A missing AMD reading falls back to the global size.
    """
    if measured_bytes is None:
        return global_memory_bytes, "opencl-global"
    return min(measured_bytes, global_memory_bytes), "opencl-amd-free"


def opencl_memory_reading() -> OpenClMemoryReading | None:
    """Return the probed adapter's capacity, free sample, and driver.

    The source is ``opencl-amd-free`` when the AMD reading fits in the global
    size, and ``opencl-global`` when that reading is missing. None means the
    probe did not accept an adapter.
    """
    adapter = resolve_usable_opencl_adapter()
    if adapter is None:
        return None
    library = _RUNTIME.library()
    measured: int | None = None
    if library is not None:
        try:
            measured = _free_memory_bytes(library, adapter)
        except OpenClProbeError as error:
            logger.warning(f"OpenCL free-memory query failed: {error}")
            measured = None
    free_bytes, source = classify_opencl_free_sample(
        adapter.global_memory_bytes, measured
    )
    return OpenClMemoryReading(
        capacity_bytes=adapter.global_memory_bytes,
        free_sample_bytes=free_bytes,
        max_allocation_bytes=adapter.max_allocation_bytes,
        driver_version=adapter.driver_version,
        estimate_source=source,
    )


def opencl_memory_bytes() -> tuple[int, int] | None:
    """Return ``(total, available)`` for the probed adapter.

    Available bytes are the AMD free-memory reading when it fits, otherwise
    the global size. None means the probe did not accept an adapter.
    """
    reading = opencl_memory_reading()
    if reading is None:
        return None
    return reading.capacity_bytes, reading.free_sample_bytes


def opencl_driver_versions() -> tuple[tuple[str, str], ...]:
    """Return ``(device name, driver version)`` for each enumerated GPU.

    ``OSError`` and ``OpenClProbeError`` are handled here and become an empty
    tuple. The launcher then shows the adapter name without a driver version.
    This does not run the numeric probe.
    """
    if sys.platform != "win32":
        return ()
    library = _RUNTIME.library()
    if library is None:
        return ()
    try:
        adapters = _enumerate(library)
    except OpenClProbeError as error:
        logger.warning(str(error))
        return ()
    return tuple((adapter.device_name, adapter.driver_version) for adapter in adapters)


def pin_selected_opencl_device() -> None:
    """Make tinygrad's next ``CL`` device the probed adapter.

    Raises:
        OpenClSelectionError: The probe accepted nothing, tinygrad is not
            installed, or the platform no longer contains the device.
            ``assign_tinygrad_default_device`` handles this for the runner
            entrypoint.
    """
    adapter = resolve_usable_opencl_adapter()
    if adapter is None:
        raise OpenClSelectionError("No OpenCL adapter passed the numeric probe")
    _pin_tinygrad_cache(adapter.platform_index, adapter.device_index)


def _default_opencl_adapter(adapters: Sequence[OpenClAdapter]) -> OpenClAdapter:
    discrete = [adapter for adapter in adapters if not adapter.host_unified_memory]
    pool = discrete if discrete else list(adapters)
    return min(
        pool,
        key=lambda adapter: (
            -adapter.global_memory_bytes,
            adapter.platform_index,
            adapter.device_index,
        ),
    )


def _earliest_adapter(adapters: Sequence[OpenClAdapter]) -> OpenClAdapter:
    return min(
        adapters,
        key=lambda adapter: (adapter.platform_index, adapter.device_index),
    )


def _parse_platform_device(text: str) -> tuple[int, int] | None:
    if text.casefold().startswith("cl:"):
        device_text = text.split(":", 1)[1]
        if device_text.isdecimal():
            return 0, int(device_text)
        return None
    if text.count(":") != 1:
        return None
    platform_text, device_text = text.split(":")
    if platform_text.isdecimal() and device_text.isdecimal():
        return int(platform_text), int(device_text)
    return None


def _decode_c_string(buffer: ctypes.Array[ctypes.c_char]) -> str:
    raw = ctypes.string_at(ctypes.addressof(buffer), ctypes.sizeof(buffer))
    return raw.split(b"\x00", 1)[0].decode(errors="replace")


def _float16_to_float(bits: int) -> float:
    """Decode an IEEE-754 binary16 value.

    ``struct`` format ``e`` is not in the type stub's overload list, so the
    probe reads the two bytes as an integer and expands them here. The fp16
    kernel adds 1 and 2, which is exact.
    """
    sign = (bits >> 15) & 1
    exponent = (bits >> 10) & 0x1F
    fraction = bits & 0x3FF
    if exponent == 0:
        magnitude = (fraction / 1024.0) * (2.0**-14)
    elif exponent == 31:
        magnitude = math.inf if fraction == 0 else math.nan
    else:
        magnitude = (1.0 + fraction / 1024.0) * (2.0 ** (exponent - 15))
    if sign == 1:
        return -magnitude
    return magnitude


def _address(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, ctypes.c_void_p) and value.value is not None:
        return value.value
    raise OpenClProbeError("OpenCL returned a null pointer")


def _status(result: object, action: str) -> int:
    if not isinstance(result, int):
        raise OpenClProbeError(f"OpenCL {action} returned {result!r}")
    if result != _CL_SUCCESS:
        raise OpenClProbeError(f"OpenCL {action} failed with status {result}")
    return result


@final
@dataclass(frozen=True)
class _OpenClLibrary:
    get_platform_ids: Callable[..., object]
    get_platform_info: Callable[..., object]
    get_device_ids: Callable[..., object]
    get_device_info: Callable[..., object]
    create_context: Callable[..., object]
    create_command_queue: Callable[..., object]
    create_buffer: Callable[..., object]
    create_program_with_source: Callable[..., object]
    build_program: Callable[..., object]
    get_program_build_info: Callable[..., object]
    create_kernel: Callable[..., object]
    set_kernel_arg: Callable[..., object]
    enqueue_ndrange: Callable[..., object]
    enqueue_read_buffer: Callable[..., object]
    finish: Callable[..., object]
    release_mem: Callable[..., object]
    release_kernel: Callable[..., object]
    release_program: Callable[..., object]
    release_queue: Callable[..., object]
    release_context: Callable[..., object]


def _export(
    library: object,
    name: str,
    restype: object,
    argtypes: list[object] | None,
) -> Callable[..., object]:
    # getattr on the ICD is Any until the entry point is bound. The ignore is
    # confined to that lookup; restype assignment is what the runner calls.
    exported = getattr(library, name)  # pyright: ignore[reportAny]
    exported.restype = restype
    if argtypes is not None:
        exported.argtypes = argtypes
    return cast(Callable[..., object], exported)


def _load_opencl_library() -> _OpenClLibrary:
    if sys.platform != "win32":
        raise OSError("OpenCL enumeration runs on Windows")
    library = ctypes.WinDLL("OpenCL")
    pointer = ctypes.c_void_p
    info_argtypes: list[object] = [
        pointer,
        ctypes.c_uint32,
        ctypes.c_size_t,
        pointer,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    return _OpenClLibrary(
        get_platform_ids=_export(
            library,
            "clGetPlatformIDs",
            ctypes.c_int32,
            [ctypes.c_uint32, pointer, ctypes.POINTER(ctypes.c_uint32)],
        ),
        get_platform_info=_export(
            library, "clGetPlatformInfo", ctypes.c_int32, info_argtypes
        ),
        get_device_ids=_export(
            library,
            "clGetDeviceIDs",
            ctypes.c_int32,
            [
                pointer,
                ctypes.c_uint64,
                ctypes.c_uint32,
                pointer,
                ctypes.POINTER(ctypes.c_uint32),
            ],
        ),
        get_device_info=_export(
            library, "clGetDeviceInfo", ctypes.c_int32, info_argtypes
        ),
        create_context=_export(library, "clCreateContext", pointer, None),
        create_command_queue=_export(library, "clCreateCommandQueue", pointer, None),
        create_buffer=_export(library, "clCreateBuffer", pointer, None),
        create_program_with_source=_export(
            library, "clCreateProgramWithSource", pointer, None
        ),
        build_program=_export(library, "clBuildProgram", ctypes.c_int32, None),
        get_program_build_info=_export(
            library, "clGetProgramBuildInfo", ctypes.c_int32, info_argtypes
        ),
        create_kernel=_export(library, "clCreateKernel", pointer, None),
        set_kernel_arg=_export(library, "clSetKernelArg", ctypes.c_int32, None),
        enqueue_ndrange=_export(
            library, "clEnqueueNDRangeKernel", ctypes.c_int32, None
        ),
        enqueue_read_buffer=_export(
            library, "clEnqueueReadBuffer", ctypes.c_int32, None
        ),
        finish=_export(library, "clFinish", ctypes.c_int32, None),
        release_mem=_export(library, "clReleaseMemObject", ctypes.c_int32, None),
        release_kernel=_export(library, "clReleaseKernel", ctypes.c_int32, None),
        release_program=_export(library, "clReleaseProgram", ctypes.c_int32, None),
        release_queue=_export(library, "clReleaseCommandQueue", ctypes.c_int32, None),
        release_context=_export(library, "clReleaseContext", ctypes.c_int32, None),
    )


def _platforms(library: _OpenClLibrary) -> list[int]:
    count = ctypes.c_uint32()
    _status(
        library.get_platform_ids(0, None, ctypes.byref(count)),
        "clGetPlatformIDs",
    )
    if count.value == 0:
        return []
    found = (ctypes.c_void_p * count.value)()
    _status(
        library.get_platform_ids(count.value, found, None),
        "clGetPlatformIDs",
    )
    return [_address(cast(object, found[index])) for index in range(count.value)]


def _devices(library: _OpenClLibrary, platform_address: int) -> list[int]:
    count = ctypes.c_uint32()
    status = library.get_device_ids(
        ctypes.c_void_p(platform_address),
        _CL_DEVICE_TYPE_GPU,
        0,
        None,
        ctypes.byref(count),
    )
    if not isinstance(status, int) or status != _CL_SUCCESS or count.value == 0:
        return []
    found = (ctypes.c_void_p * count.value)()
    _status(
        library.get_device_ids(
            ctypes.c_void_p(platform_address),
            _CL_DEVICE_TYPE_GPU,
            count.value,
            found,
            None,
        ),
        "clGetDeviceIDs",
    )
    return [_address(cast(object, found[index])) for index in range(count.value)]


def _info_string(
    query: Callable[..., object], target: int, param: int, action: str
) -> str:
    size = ctypes.c_size_t()
    _status(
        query(ctypes.c_void_p(target), param, 0, None, ctypes.byref(size)),
        action,
    )
    if size.value == 0:
        return ""
    buffer = ctypes.create_string_buffer(size.value)
    _status(
        query(
            ctypes.c_void_p(target),
            param,
            size.value,
            buffer,
            None,
        ),
        action,
    )
    return _decode_c_string(buffer)


def _info_u64(library: _OpenClLibrary, device: int, param: int, action: str) -> int:
    value = ctypes.c_uint64()
    _status(
        library.get_device_info(
            ctypes.c_void_p(device),
            param,
            ctypes.sizeof(value),
            ctypes.byref(value),
            None,
        ),
        action,
    )
    return int(value.value)


def _info_u32(library: _OpenClLibrary, device: int, param: int, action: str) -> int:
    value = ctypes.c_uint32()
    _status(
        library.get_device_info(
            ctypes.c_void_p(device),
            param,
            ctypes.sizeof(value),
            ctypes.byref(value),
            None,
        ),
        action,
    )
    return int(value.value)


def _enumerate(library: _OpenClLibrary) -> tuple[OpenClAdapter, ...]:
    adapters: list[OpenClAdapter] = []
    for platform_index, platform_address in enumerate(_platforms(library)):
        platform_name = _info_string(
            library.get_platform_info,
            platform_address,
            _CL_PLATFORM_NAME,
            "clGetPlatformInfo",
        )
        for device_index, device_address in enumerate(
            _devices(library, platform_address)
        ):
            extensions = _info_string(
                library.get_device_info,
                device_address,
                _CL_DEVICE_EXTENSIONS,
                "clGetDeviceInfo",
            )
            adapters.append(
                OpenClAdapter(
                    platform_index=platform_index,
                    device_index=device_index,
                    platform_name=platform_name,
                    device_name=_info_string(
                        library.get_device_info,
                        device_address,
                        _CL_DEVICE_NAME,
                        "clGetDeviceInfo",
                    ),
                    vendor=_info_string(
                        library.get_device_info,
                        device_address,
                        _CL_DEVICE_VENDOR,
                        "clGetDeviceInfo",
                    ),
                    driver_version=_info_string(
                        library.get_device_info,
                        device_address,
                        _CL_DRIVER_VERSION,
                        "clGetDeviceInfo",
                    ),
                    global_memory_bytes=_info_u64(
                        library,
                        device_address,
                        _CL_DEVICE_GLOBAL_MEM_SIZE,
                        "clGetDeviceInfo",
                    ),
                    max_allocation_bytes=_info_u64(
                        library,
                        device_address,
                        _CL_DEVICE_MAX_MEM_ALLOC_SIZE,
                        "clGetDeviceInfo",
                    ),
                    host_unified_memory=bool(
                        _info_u32(
                            library,
                            device_address,
                            _CL_DEVICE_HOST_UNIFIED_MEMORY,
                            "clGetDeviceInfo",
                        )
                    ),
                    supports_fp16="cl_khr_fp16" in extensions.split(),
                )
            )
    return tuple(adapters)


def _device_address(library: _OpenClLibrary, adapter: OpenClAdapter) -> tuple[int, int]:
    platforms = _platforms(library)
    if adapter.platform_index < 0 or adapter.platform_index >= len(platforms):
        raise OpenClProbeError(
            f"OpenCL platform {adapter.platform_index} is no longer present"
        )
    platform_address = platforms[adapter.platform_index]
    devices = _devices(library, platform_address)
    if adapter.device_index < 0 or adapter.device_index >= len(devices):
        raise OpenClProbeError(
            f"OpenCL device {adapter.device_index} is no longer present"
        )
    return platform_address, devices[adapter.device_index]


def _pointer(result: object, action: str) -> int:
    if isinstance(result, ctypes.c_void_p) and result.value is not None:
        return result.value
    if isinstance(result, int) and result != 0:
        return result
    raise OpenClProbeError(f"OpenCL {action} returned a null pointer")


def _release(query: Callable[..., object], handle: int | None) -> None:
    if handle is None:
        return
    result = query(ctypes.c_void_p(handle))
    if isinstance(result, int) and result != _CL_SUCCESS:
        logger.warning(f"OpenCL release failed with status {result}")


def _build_log(library: _OpenClLibrary, program: int, device: int) -> str:
    size = ctypes.c_size_t()
    status = library.get_program_build_info(
        ctypes.c_void_p(program),
        ctypes.c_void_p(device),
        _CL_PROGRAM_BUILD_LOG,
        0,
        None,
        ctypes.byref(size),
    )
    if not isinstance(status, int) or status != _CL_SUCCESS or size.value == 0:
        return ""
    buffer = ctypes.create_string_buffer(size.value)
    library.get_program_build_info(
        ctypes.c_void_p(program),
        ctypes.c_void_p(device),
        _CL_PROGRAM_BUILD_LOG,
        size.value,
        buffer,
        None,
    )
    return _decode_c_string(buffer).strip()


def _build_kernel(
    library: _OpenClLibrary,
    context: int,
    device: int,
    source: str,
    kernel_name: str,
) -> tuple[int, int]:
    encoded = source.encode()
    source_pointer = ctypes.c_char_p(encoded)
    sources = (ctypes.c_char_p * 1)(source_pointer)
    error = ctypes.c_int32()
    program = _pointer(
        library.create_program_with_source(
            ctypes.c_void_p(context),
            1,
            sources,
            None,
            ctypes.byref(error),
        ),
        "clCreateProgramWithSource",
    )
    if error.value != _CL_SUCCESS:
        raise OpenClProbeError(
            f"clCreateProgramWithSource failed with status {error.value}"
        )
    device_pointer = ctypes.c_void_p(device)
    built = library.build_program(
        ctypes.c_void_p(program),
        1,
        ctypes.byref(device_pointer),
        None,
        None,
        None,
    )
    if not isinstance(built, int) or built != _CL_SUCCESS:
        log = _build_log(library, program, device)
        _release(library.release_program, program)
        detail = f": {log}" if log else ""
        raise OpenClProbeError(f"clBuildProgram failed with status {built}{detail}")
    kernel = _pointer(
        library.create_kernel(
            ctypes.c_void_p(program),
            kernel_name.encode(),
            ctypes.byref(error),
        ),
        "clCreateKernel",
    )
    if error.value != _CL_SUCCESS:
        _release(library.release_program, program)
        raise OpenClProbeError(f"clCreateKernel failed with status {error.value}")
    return program, kernel


def _set_mem_arg(library: _OpenClLibrary, kernel: int, index: int, memory: int) -> None:
    argument = ctypes.c_void_p(memory)
    _status(
        library.set_kernel_arg(
            ctypes.c_void_p(kernel),
            index,
            ctypes.sizeof(argument),
            ctypes.byref(argument),
        ),
        "clSetKernelArg",
    )


def _create_buffer(
    library: _OpenClLibrary,
    context: int,
    flags: int,
    size: int,
    host: ctypes.Array[ctypes.c_float] | None,
) -> int:
    error = ctypes.c_int32()
    memory = _pointer(
        library.create_buffer(
            ctypes.c_void_p(context),
            flags,
            size,
            host,
            ctypes.byref(error),
        ),
        "clCreateBuffer",
    )
    if error.value != _CL_SUCCESS:
        raise OpenClProbeError(f"clCreateBuffer failed with status {error.value}")
    return memory


def _run_dot_product(
    library: _OpenClLibrary, context: int, queue: int, device: int
) -> float:
    program, kernel = _build_kernel(library, context, device, _DOT_KERNEL, "probe_dot")
    left = (ctypes.c_float * 4)(*_DOT_LEFT)
    right = (ctypes.c_float * 4)(*_DOT_RIGHT)
    left_buffer: int | None = None
    right_buffer: int | None = None
    out_buffer: int | None = None
    try:
        left_buffer = _create_buffer(
            library,
            context,
            _CL_MEM_READ_ONLY | _CL_MEM_COPY_HOST_PTR,
            ctypes.sizeof(left),
            left,
        )
        right_buffer = _create_buffer(
            library,
            context,
            _CL_MEM_READ_ONLY | _CL_MEM_COPY_HOST_PTR,
            ctypes.sizeof(right),
            right,
        )
        out_buffer = _create_buffer(
            library,
            context,
            _CL_MEM_WRITE_ONLY,
            ctypes.sizeof(ctypes.c_float),
            None,
        )
        _set_mem_arg(library, kernel, 0, left_buffer)
        _set_mem_arg(library, kernel, 1, right_buffer)
        _set_mem_arg(library, kernel, 2, out_buffer)
        global_size = (ctypes.c_size_t * 1)(1)
        _status(
            library.enqueue_ndrange(
                ctypes.c_void_p(queue),
                ctypes.c_void_p(kernel),
                1,
                None,
                global_size,
                None,
                0,
                None,
                None,
            ),
            "clEnqueueNDRangeKernel",
        )
        out = ctypes.c_float()
        _status(
            library.enqueue_read_buffer(
                ctypes.c_void_p(queue),
                ctypes.c_void_p(out_buffer),
                1,
                0,
                ctypes.sizeof(out),
                ctypes.byref(out),
                0,
                None,
                None,
            ),
            "clEnqueueReadBuffer",
        )
        _status(library.finish(ctypes.c_void_p(queue)), "clFinish")
        return float(out.value)
    finally:
        _release(library.release_mem, left_buffer)
        _release(library.release_mem, right_buffer)
        _release(library.release_mem, out_buffer)
        _release(library.release_kernel, kernel)
        _release(library.release_program, program)


def _run_fp16_sum(
    library: _OpenClLibrary, context: int, queue: int, device: int
) -> float:
    program, kernel = _build_kernel(
        library, context, device, _HALF_KERNEL, "probe_half"
    )
    out_buffer: int | None = None
    try:
        out_buffer = _create_buffer(
            library,
            context,
            _CL_MEM_WRITE_ONLY,
            2,
            None,
        )
        _set_mem_arg(library, kernel, 0, out_buffer)
        global_size = (ctypes.c_size_t * 1)(1)
        _status(
            library.enqueue_ndrange(
                ctypes.c_void_p(queue),
                ctypes.c_void_p(kernel),
                1,
                None,
                global_size,
                None,
                0,
                None,
                None,
            ),
            "clEnqueueNDRangeKernel",
        )
        slot = ctypes.c_uint16()
        _status(
            library.enqueue_read_buffer(
                ctypes.c_void_p(queue),
                ctypes.c_void_p(out_buffer),
                1,
                0,
                ctypes.sizeof(slot),
                ctypes.byref(slot),
                0,
                None,
                None,
            ),
            "clEnqueueReadBuffer",
        )
        _status(library.finish(ctypes.c_void_p(queue)), "clFinish")
        return _float16_to_float(int(slot.value))
    finally:
        _release(library.release_mem, out_buffer)
        _release(library.release_kernel, kernel)
        _release(library.release_program, program)


def _execute_probe(
    library: _OpenClLibrary, adapter: OpenClAdapter
) -> tuple[float, float | None]:
    platform_address, device_address = _device_address(library, adapter)
    properties = (ctypes.c_int64 * 3)(
        _CL_CONTEXT_PLATFORM,
        platform_address,
        0,
    )
    error = ctypes.c_int32()
    device_pointer = ctypes.c_void_p(device_address)
    context = _pointer(
        library.create_context(
            properties,
            1,
            ctypes.byref(device_pointer),
            None,
            None,
            ctypes.byref(error),
        ),
        "clCreateContext",
    )
    if error.value != _CL_SUCCESS:
        raise OpenClProbeError(f"clCreateContext failed with status {error.value}")
    queue: int | None = None
    try:
        queue = _pointer(
            library.create_command_queue(
                ctypes.c_void_p(context),
                ctypes.c_void_p(device_address),
                0,
                ctypes.byref(error),
            ),
            "clCreateCommandQueue",
        )
        if error.value != _CL_SUCCESS:
            raise OpenClProbeError(
                f"clCreateCommandQueue failed with status {error.value}"
            )
        dot_product = _run_dot_product(library, context, queue, device_address)
        if not adapter.supports_fp16:
            return dot_product, None
        return dot_product, _run_fp16_sum(library, context, queue, device_address)
    finally:
        _release(library.release_queue, queue)
        _release(library.release_context, context)


def _free_memory_bytes(library: _OpenClLibrary, adapter: OpenClAdapter) -> int | None:
    _platform_address, device_address = _device_address(library, adapter)
    words = (ctypes.c_uint64 * 4)()
    size = ctypes.c_size_t()
    status = library.get_device_info(
        ctypes.c_void_p(device_address),
        _CL_DEVICE_GLOBAL_FREE_MEMORY_AMD,
        ctypes.sizeof(words),
        words,
        ctypes.byref(size),
    )
    if not isinstance(status, int) or status != _CL_SUCCESS or size.value < 8:
        return None
    count = min(size.value // 8, 4)
    payload = ctypes.string_at(ctypes.addressof(words), 32)
    reading = struct.unpack("<QQQQ", payload)
    return interpret_amd_free_memory_bytes(
        reading[:count],
        adapter.global_memory_bytes,
    )


def _current_preference() -> str | None:
    file_text: str | None = None
    path = opencl_adapter_preference_path()
    try:
        if path.is_file():
            file_text = path.read_text(encoding="utf-8")
    except OSError:
        file_text = None
    return read_opencl_adapter_preference(
        environment_value=os.environ.get("EXO_OPENCL_ADAPTER"),
        file_text=file_text,
    )


def _pin_tinygrad_cache(platform_index: int, device_index: int) -> None:
    try:
        from tinygrad.runtime.autogen import opencl as opencl_bindings
        from tinygrad.runtime.ops_cl import CLDevice
    except ImportError as error:
        raise OpenClSelectionError(
            "tinygrad is not installed, so the OpenCL device cannot be pinned"
        ) from error
    if CLDevice.device_ids is not None:
        return
    platform_count = ctypes.c_uint32()
    platform_status = _tinygrad_status(
        opencl_bindings.clGetPlatformIDs(0, None, ctypes.byref(platform_count))
    )
    if platform_status != _CL_SUCCESS:
        raise OpenClSelectionError(
            f"clGetPlatformIDs failed with status {platform_status}"
        )
    platforms = (opencl_bindings.cl_platform_id * platform_count.value)()
    platform_status = _tinygrad_status(
        opencl_bindings.clGetPlatformIDs(platform_count.value, platforms, None)
    )
    if platform_status != _CL_SUCCESS:
        raise OpenClSelectionError(
            f"clGetPlatformIDs failed with status {platform_status}"
        )
    if platform_index < 0 or platform_index >= platform_count.value:
        raise OpenClSelectionError(
            f"OpenCL platform {platform_index} is no longer present"
        )
    device_count = ctypes.c_uint32()
    device_status = _tinygrad_status(
        opencl_bindings.clGetDeviceIDs(
            platforms[platform_index],
            opencl_bindings.CL_DEVICE_TYPE_GPU,
            0,
            None,
            ctypes.byref(device_count),
        )
    )
    if device_status != _CL_SUCCESS:
        raise OpenClSelectionError(f"clGetDeviceIDs failed with status {device_status}")
    devices = (opencl_bindings.cl_device_id * device_count.value)()
    device_status = _tinygrad_status(
        opencl_bindings.clGetDeviceIDs(
            platforms[platform_index],
            opencl_bindings.CL_DEVICE_TYPE_GPU,
            device_count.value,
            devices,
            None,
        )
    )
    if device_status != _CL_SUCCESS:
        raise OpenClSelectionError(f"clGetDeviceIDs failed with status {device_status}")
    if device_index < 0 or device_index >= device_count.value:
        raise OpenClSelectionError(f"OpenCL device {device_index} is no longer present")
    CLDevice.device_ids = (opencl_bindings.cl_device_id * 1)(devices[device_index])


def _tinygrad_status(result: object) -> int:
    if isinstance(result, int):
        return result
    raise OpenClSelectionError(f"Unexpected OpenCL status {result!r}")


@final
class OpenClRuntime:
    """Process-wide OpenCL ICD handle and probe cache."""

    def __init__(self) -> None:
        self._library: _OpenClLibrary | None = None
        self._load_failed = False
        self._resolution_known = False
        self._adapter: OpenClAdapter | None = None

    def library(self) -> _OpenClLibrary | None:
        if self._load_failed:
            return None
        if self._library is not None:
            return self._library
        if sys.platform != "win32":
            self._load_failed = True
            return None
        try:
            self._library = _load_opencl_library()
        except OSError as error:
            logger.warning(f"OpenCL ICD is unavailable: {error}")
            self._load_failed = True
            return None
        return self._library

    def clear_resolution(self) -> None:
        self._resolution_known = False
        self._adapter = None

    def resolve(self) -> OpenClAdapter | None:
        if self._resolution_known:
            return self._adapter
        self._adapter = self._resolve_bounded()
        self._resolution_known = True
        return self._adapter

    def _resolve_bounded(self) -> OpenClAdapter | None:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="opencl-probe")
        future = executor.submit(self._resolve_once)
        try:
            return future.result(timeout=_PROBE_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning("OpenCL adapter probe timed out")
            return None
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _resolve_once(self) -> OpenClAdapter | None:
        library = self.library()
        if library is None:
            return None
        try:
            adapters = _enumerate(library)
            preference = _current_preference()
            selected = select_opencl_adapter(adapters, preference)
            if selected is None:
                logger.warning("OpenCL adapter preference did not match a GPU")
                return None
            dot_product, fp16_sum = _execute_probe(library, selected)
        except OpenClProbeError as error:
            logger.warning(str(error))
            return None
        if not probe_numerics_match(
            dot_product=dot_product,
            fp16_sum=fp16_sum,
            supports_fp16=selected.supports_fp16,
        ):
            logger.warning(
                f"OpenCL probe numerics were dot={dot_product} fp16={fp16_sum}"
            )
            return None
        logger.info(
            f"OpenCL adapter {selected.device_name} "
            f"platform {selected.platform_index} device {selected.device_index} "
            f"memory {selected.global_memory_bytes} bytes"
        )
        if preference is None and os.environ.get("EXO_TESTS") != "1":
            try:
                remember_opencl_adapter(
                    selected.device_name, opencl_adapter_preference_path()
                )
            except OSError as error:
                logger.warning(f"Could not store the OpenCL adapter choice: {error}")
        return selected


_RUNTIME = OpenClRuntime()
