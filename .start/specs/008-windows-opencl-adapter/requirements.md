---
title: "Windows OpenCL Adapter"
status: complete
version: "1.0"
---

# Product Requirements Document

## Product Overview

### Vision

A Windows machine with an AMD GPU joins an exo cluster on the adapter the operator intends, and placement sees that adapter's memory.

### Problem Statement

`WinAMD` currently selects tinygrad's `AMD` device. That runtime does not run on Windows. Tinygrad 0.14's OpenCL device also opens only the first platform's device list, and an integrated GPU on the same platform can report a larger global-memory size than the discrete GPU because the value includes shared system memory. Advertising `WinAMD` from the display name alone therefore either fails at runner start or can target the wrong GPU, and the memory probe still asks `rocm-smi`, which is absent, so the node publishes zero accelerator bytes.

### Value Proposition

The same Windows node can start exo, advertise `WinAMD` only after a real OpenCL kernel returns the expected numbers, and report the discrete GPU's capacity to placement.

## User Personas

### Primary Persona: Windows AMD Operator

- Owns a Windows PC with one or more AMD GPUs, including a mix of integrated and discrete adapters.
- Wants exo to start and contribute the discrete GPU without editing tinygrad internals.

## User Journey

1. The operator starts exo on Windows.
2. exo enumerates OpenCL adapters, probes the discrete GPU, and joins as `WinAMD`.
3. Placement reads that GPU's total and free memory.
4. A tinygrad runner opens the same adapter.

## Feature Requirements

### Must Have

#### Feature 1: Discrete OpenCL adapter

- **User Story:** As a Windows AMD operator, I want exo to choose my discrete GPU when an integrated GPU reports more shared memory.
- **Acceptance Criteria:**

  Criteria:
  - [x] Given adapters where one GPU has `host_unified_memory` false and another has it true with a larger global size, When no explicit preference is set, Then the non-unified GPU is selected.
  - [x] Given the same device name on two platforms, When the name is selected, Then the lowest platform index is used.
  - [x] Given an explicit `platform:device` preference, When that pair exists, Then that adapter is selected even if it is unified.

#### Feature 2: Numeric probe before advertising

- **User Story:** As a Windows AMD operator, I want `WinAMD` hidden when OpenCL cannot execute a kernel.
- **Acceptance Criteria:**

  Criteria:
  - [x] Given a Windows node whose display adapter is AMD and whose OpenCL probe fails, When backends are gathered, Then `WinAMD` is absent and `WinCPU` is present.
  - [x] Given a probe that succeeds, When backends are gathered, Then `WinAMD` is present.
  - [x] Given a GPU that advertises `cl_khr_fp16`, When the probe runs, Then an fp16 addition and an fp32 dot product must match their expected values.

#### Feature 3: Memory and tinygrad pin

- **User Story:** As a Windows AMD operator, I want placement and the runner to use the probed adapter.
- **Acceptance Criteria:**

  Criteria:
  - [x] Given a probed adapter, When memory is sampled, Then total bytes are `CL_DEVICE_GLOBAL_MEM_SIZE` and available bytes are the AMD free-memory reading when that reading fits in the total.
  - [x] Given a probed adapter, When the tinygrad engine selects `CL`, Then the opened device name is the probed adapter's name.
  - [x] Given no explicit preference, When the probe succeeds outside tests, Then the device name is written to the config home so the next start selects the same name.

### Won't Have

- A full GGUF model download and distributed generation.
- Dashboard runtime controls.
- ROCm on Windows.
- Changing `TinygradAmd` away from device `AMD`.

## Success Metrics

- On the development machine, the selected adapter is `gfx1201` (RX 9070 XT), not `gfx1036`.
- `uv run exo` serves the API and the node backend list includes `WinAMD`.
- A tinygrad `CL` device opened through the pin reports `gfx1201`.

## Constraints

- Tinygrad 0.14.0 as locked in `uv.lock`.
- No new third-party dependency. OpenCL is called through `OpenCL.dll`.
- Probe failures must not prevent the process from starting; the node falls back to `WinCPU`.

## Open Questions

None.
