# Specification: 008-windows-opencl-adapter

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-12 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Windows AMD nodes must join through a probed OpenCL adapter, not ROCm. |
| solution.md | completed | Direct-tier design: enumerate every platform, prefer discrete memory, pin tinygrad `CL`. |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Direct |
| **Status** | completed |

**Tier values**: `Direct` (no artifacts) | `Incremental` (plan/) | `Factory` (manifest.md + units/ + scenarios/) | `None` (not yet chosen)

Direct tier: no `plan/` or factory manifest. Implementation follows `requirements.md` and `solution.md`.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-12 | Classified as Direct. One user-facing capability (a Windows AMD node advertises `WinAMD` only for a probed OpenCL adapter) with one new module and call-site changes in device selection, memory, and join. | The parked plan's runtime-feasibility item is a single vertical slice. Factory units would split the probe from the pin that makes the probe meaningful. |
| 2026-10-12 | `WinAMD` maps to tinygrad device `CL`, while `TinygradAmd` stays `AMD`. | Tinygrad's AMD runtime asserts on `win32`. OpenCL is the Windows path recorded in `docs/plans/tinygrad-windows-cluster-support.md`. |
| 2026-10-12 | Default adapter is the largest non-unified GPU, not the largest `CL_DEVICE_GLOBAL_MEM_SIZE`. | On the development machine the RX 9070 XT (`gfx1201`, ~16 GiB, unified=0) shares a platform with an iGPU (`gfx1036`, ~36 GiB shared, unified=1). Largest-global-memory would select the iGPU. |
| 2026-10-12 | Tinygrad's `CLDevice.device_ids` cache is replaced with the chosen device before the first `CLDevice` exists. | Tinygrad 0.14 reads devices from platform 0 only (`ops_cl.py`). A one-element cache makes `CL` open any platform. |

## Context

exo already advertises `WinAMD` from the Windows display-adapter name and then asks tinygrad for device `AMD`. That device is ROCm. The parked Windows plan's first remaining item is to enumerate every OpenCL platform, persist an explicit adapter choice, run a bounded numeric probe, and advertise the accelerator only after the probe succeeds. This spec is that slice, plus the OpenCL memory numbers placement needs so a probed GPU is not published as zero bytes.

---
*This file follows the specify-meta README shape. `spec.py` is not present in the local specify-meta skill cache, so the directory was created directly.*
