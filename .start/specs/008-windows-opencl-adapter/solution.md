---
title: "Windows OpenCL Adapter"
status: complete
version: "1.0"
---

# Solution Design

## Summary

Add `src/exo/backends/tinygrad_opencl.py`. `WinAMD` maps to tinygrad device `CL`. Join advertising calls a numeric probe. Memory for `CL` comes from OpenCL. The runner pins `CLDevice.device_ids` to the chosen device before assigning `Device.DEFAULT`.

## Components

### Pure selection

`OpenClAdapter` is a frozen model: platform index, device index, names, driver version, global memory, max allocation, unified-memory flag, fp16 flag.

`select_opencl_adapter(adapters, preference)`:

- Empty preference: among adapters with `host_unified_memory` false, pick the largest global memory, then the lowest platform index, then the lowest device index. If every adapter is unified, use the same ordering on the full list.
- Preference `platform:device` or `CL:device` (platform 0): exact index match.
- Other text: case-insensitive device-name match. A unique name across duplicate platforms collapses to the lowest platform index. Two different names is no match.

`read_opencl_adapter_preference` prefers `EXO_OPENCL_ADAPTER`, then the text of the preference file.

`interpret_amd_free_memory_bytes` reads `CL_DEVICE_GLOBAL_FREE_MEMORY_AMD`. AMD reports kilobytes. Use kilobytes when `min(positive) * 1024` fits in the global size; otherwise use the raw value when that fits. Otherwise return none.

`probe_numerics_match` requires the fp32 dot product of `[1, 2, 3, 4]` with `[1, 1, 1, 1]` to be 10, and the fp16 sum of 1 and 2 to be 3 when the adapter advertises `cl_khr_fp16`.

### Effects

`OpenClRuntime` owns the DLL, the one-shot resolution cache, and the preference file `EXO_CONFIG_HOME / "opencl-adapter"`.

Enumeration uses `OpenCL.dll` and `CL_DEVICE_TYPE_GPU` on every platform. The probe creates a context, builds the dot-product kernel, and builds the fp16 kernel when advertised. The whole resolution runs on a worker thread with a 10 second timeout. Timeout, `OSError`, and probe errors become "no adapter" and are cached so the gatherer does not compile again on the memory poll.

Outside `EXO_TESTS=1`, a successful resolution with no explicit preference writes the device name. `OSError` on that write is logged and ignored.

`collect_windows_join_backends` drops `WinAMD` when the probe does not succeed. If that was the only identity, the result is `WinCPU`.

`memory_usage_for_device("CL")` uses the cached adapter's global size and a fresh free-memory query. A missing adapter publishes zero accelerator bytes, same as a missing `rocm-smi`.

`assign_tinygrad_default_device("CL")` pins before importing `tinygrad.Device`. The pin copies the chosen `cl_device_id` into `CLDevice.device_ids` as a one-element array so device string `CL` opens it, including adapters that are not on platform 0. An already-set cache is left in place so a second call in the process does not retarget a live device. Failure raises `OpenClSelectionError`, which `assign_tinygrad_default_device` transforms into `TinygradDeviceSelectionError` for the runner entrypoint.

## ADRs

### ADR-1: OpenCL for `WinAMD`, ROCm for `TinygradAmd`

`WinAMD` is the Windows join identity. Tinygrad's `AMD` device is ROCm and is the Linux/HIP path for `TinygradAmd`. Windows runners set `Device.DEFAULT` to `CL`.

### ADR-2: Unified-memory flag beats global size

`CL_DEVICE_HOST_UNIFIED_MEMORY` distinguishes the discrete GPU from an iGPU whose global size includes system RAM. A stored device name overrides that default.

### ADR-3: Replace tinygrad's platform-0 cache

Tinygrad 0.14 has no platform index in the device string. Setting `CLDevice.device_ids` before the first `CLDevice` is constructed is the smallest change that still opens a non-zero platform. The cache is process-global, so the runner process pins once.

### ADR-4: Probe in the gatherer, raise in the runner

A failed probe must not stop `uv run exo`. The gatherer drops `WinAMD`. The runner raises if it is asked to start `CL` without a probed adapter, and the existing entrypoint publishes `RunnerTerminationError`.

## Testing

Pure selection, preference parsing, and free-memory interpretation run without a GPU. A Windows test with `OpenCL.dll` resolves the live adapter, checks the unified-memory rule, and opens tinygrad `CLDevice("CL")` after the pin. Join tests monkeypatch `windows_opencl_is_usable` so CI without an ICD still covers both advertise and fallback.
