# Solution: Accelerator Memory Sample

## Approach

`MemoryUsage` gains an optional `AcceleratorMemorySample`. The OpenCL, ROCm, and NVIDIA probes fill it. CPU and Metal leave it empty because their `ram_*` fields are already host memory.

`memory_after_reservations` copies the sample, writes the reserved bytes, and sets `ceiling` to capacity minus those bytes. `free_sample` stays the probe's reading. `ram_available` remains the smaller of that reading and the ceiling.

The topology tooltip appends driver and max-allocation lines when the sample includes them.

## Files

- `src/exo/shared/types/profiling.py` — the sample and `host_ram_bytes`.
- `src/exo/backends/tinygrad_opencl.py` — the OpenCL reading, including source and driver.
- `src/exo/backends/tinygrad_memory.py` — attach the sample on accelerator probes.
- `src/exo/master/placement_memory.py` — update ceiling and reserved.
- Dashboard node info and the topology tooltip.
- Tests beside the memory and placement modules.
