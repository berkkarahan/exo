# Specification: 012-opencl-runner-diagnostics

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-12 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | OpenCL compile, allocation, and device-loss lines are classified. |
| solution.md | completed | Direct-tier matchers for the strings tinygrad's OpenCL runtime raises. |

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Direct |
| **Status** | completed |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-12 | Classified as Direct. Three diagnostic variants and matchers. | The collector already forwards known diagnostics when a runner stops. Tinygrad lines were falling through to `RunnerUnknown`. |
| 2026-10-12 | Match the strings in tinygrad 0.14 `ops_cl.py`: `OpenCL Compile Error` and `OpenCL Error <status>: CL_...`. | Those are the exceptions the Windows runner prints. Allocation is `CL_MEM_OBJECT_ALLOCATION_FAILURE`, `CL_OUT_OF_RESOURCES`, and `CL_OUT_OF_HOST_MEMORY`. Device loss is `CL_DEVICE_NOT_FOUND`, `CL_DEVICE_NOT_AVAILABLE`, or a line that says device lost. |
| 2026-10-12 | Other `OpenCL Error` names stay `RunnerUnknown`. | `CL_INVALID_KERNEL` is not an out-of-memory or device-loss failure. |
