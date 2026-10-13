# Specification: 015-accelerator-memory-sample

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-12 |
| **Current Phase** | Completed |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Separate accelerator capacity from host RAM and name the estimate source. |
| solution.md | completed | Optional sample on `MemoryUsage`, filled by the device probe. |

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Direct |
| **Status** | completed |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-12 | Classified as Direct. One optional sample on the existing memory object. | Placement already reserves runner budgets. The gatherer still publishes only `ram_total` and `ram_available`, so capacity, the free sample, the allocation limit, and host RAM are not distinguishable. |
| 2026-10-12 | OpenCL capacity is `CL_DEVICE_GLOBAL_MEM_SIZE`. The free sample is the AMD reading when it fits, otherwise the global size. Max allocation is `CL_DEVICE_MAX_MEM_ALLOC_SIZE`. | Those queries are already on the probed adapter. |
| 2026-10-12 | A memory override replaces available bytes and marks the source `override`. Capacity and host RAM stay measured. | The limit is a placement ceiling, not a second copy of system RAM. |
| 2026-10-12 | Reservations update `ceiling` and `reserved` and leave `free_sample` unchanged. | An OpenCL free sample that ignores the runner must not be subtracted twice. |
