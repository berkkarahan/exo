# Requirements: Accelerator Memory Sample

## User Stories

### Story: See GPU capacity apart from the machine's RAM

When a Windows node publishes memory, the sample names the device capacity, the free-memory reading, the largest single allocation, the driver version, and the host RAM. Host RAM is not substituted for the accelerator.

### Story: See why the available number changed

When placement reserves a resident Tinygrad instance, the ceiling and reserved bytes change. The original free sample stays the device reading. An override is labeled as an override.

## Acceptance Criteria

1. [x] An OpenCL sample records capacity, free sample, max allocation, driver version, host RAM total, and host RAM available.
2. [x] The free sample's source is `opencl-amd-free` when the AMD reading fits, and `opencl-global` when it does not.
3. [x] A missing accelerator still publishes zero device bytes, with host RAM on the sample and source `unavailable`.
4. [x] `OVERRIDE_MEMORY_MB` changes available bytes and sets the source to `override` without replacing capacity or host RAM.
5. [x] Reserving an instance lowers `ceiling` and sets `reserved`, and leaves `free_sample` at the device reading.
6. [x] CPU and Metal memory stay the psutil reading and carry no accelerator sample.
7. [x] The dashboard node tooltip includes the driver version and max allocation when the sample has them.

## Out of Scope

- DXGI `QueryVideoMemoryInfo`.
- Sleep, resume, disconnect, and rejoin.
- Firewall rules and peer-discovery probes.
