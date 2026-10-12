# Specification: 002-windows-system-telemetry

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-11 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-09-11 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 4 Must-Have features, 12 Gherkin ACs, all MoSCoW categories addressed, 0 `[NEEDS CLARIFICATION]` markers |
| solution.md | completed | Platform-dispatched telemetry provider design, 4 confirmed ADRs, EARS acceptance criteria, 0 `[NEEDS CLARIFICATION]` markers |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Incremental |
| **Status** | completed |

**Tier values**: `Direct` (no artifacts) | `Incremental` (plan/) | `Factory` (manifest.md + units/ + scenarios/) | `None` (not yet chosen)

For Incremental tier, see `plan/README.md`. Four phases are defined: Phase 1 (Shared Telemetry Data Contract), Phase 2 (Windows GPU Telemetry Provider), Phase 3 (Windows Node Identity & Packaging), Phase 4 (Integration & Validation).

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-11 | Classified as Incremental — single user-facing capability (accurate Windows node telemetry) with 2 components (platform-dispatched telemetry provider + extended resource model). No parallel work flagged. ACs alone do not justify Factory overhead. | Classifier rationale, verbatim per task instruction. |
| 2026-09-11 | Windows GPU telemetry source layering: NVML (`pynvml`) required-optional for NVIDIA VRAM (reuses the existing soft dependency already used for backend detection at `src/exo/utils/info_gatherer/info_gatherer.py:357-369`); DXGI (`IDXGIAdapter3::QueryVideoMemoryInfo` via stdlib `ctypes`) optional and vendor-neutral, directly covering the stated AMD Ryzen 7 + Radeon RX hardware; WMI/CIM (`Win32_Processor`, `Win32_VideoController`) used only for CPU/GPU identity strings, never for VRAM quantities (its `AdapterRAM` field is known-unreliable above 4GB on many drivers). LibreHardwareMonitor was explicitly considered per the epic's technical context and rejected — it requires spawning an external .NET process and commonly needs administrator rights, which conflicts with "telemetry must never take the node down" and mirrors the exact anti-pattern (a required external binary) that this spec is fixing for macmon. | Recorded as solution.md ADR-2, directly resolving the epic's named technology options (WMI, NVML, LibreHardwareMonitor) with explicit trade-offs. |
| 2026-09-11 | VRAM-modelling decision: `SystemPerformanceProfile` gains `vram_total: Memory \| None` and `vram_available: Memory \| None` fields and this data is published into `State.node_system` via a new `WindowsGpuMetrics` event/apply arm — but `src/exo/master/placement.py`'s `place_instance` and `src/exo/master/placement_utils.py`'s `filter_cycles_by_memory`/`_allocate_and_validate_layers` are explicitly NOT modified in this spec to consume VRAM for cycle eligibility or layer allocation. This phase publishes an accurate telemetry signal only; making placement VRAM-aware is deferred to a future spec because it requires a non-trivial policy decision (how RAM and VRAM combine for GPU-backed backends) that is out of scope for a telemetry-accuracy fix. | Recorded as solution.md ADR-3, directly answering the task's required "decide explicitly whether placement starts using VRAM in THIS spec" instruction. |
| 2026-09-11 | Multi-GPU-vendor tie-break: when a Windows node has both an NVIDIA and a non-NVIDIA GPU installed, NVML's `nvmlDeviceGetHandleByIndex(0)` (the same device `_has_nvml_cuda()` already selects for backend eligibility) is authoritative for telemetry; DXGI/WMI are not additionally queried for a second GPU in this phase. | Recorded as solution.md ADR-4, resolving requirements.md's Edge Case Scenario 2 with a deterministic, testable rule. |

## Context

Epic 2 (Topology-Aware Auto Parallel needs accurate Windows telemetry) exposed that exo's node telemetry pipeline is macOS-only in practice: `IS_DARWIN` (`src/exo/utils/info_gatherer/info_gatherer.py:43`) gates the only path (`macmon`) that reports GPU usage, temperature, power, and (implicitly) rich hardware identity; every other platform, including Windows, falls back to a 1-second `psutil` RAM-only poll (`info_gatherer.py:511-528`) and hardcodes `"Unknown Model"`/`"Unknown Chip"` identity (`system_info.py:122-127`). Critically, no VRAM field exists anywhere in `SystemPerformanceProfile` (`src/exo/shared/types/profiling.py:59-66`) today, so even a fixed Windows telemetry path would have nowhere to put GPU memory data without a model change.

This spec's solution extends the existing `IS_DARWIN`-style platform dispatch pattern with a third named path (`IS_WINDOWS`), adds VRAM fields to the shared `SystemPerformanceProfile` model, and layers three Windows telemetry sources (NVML for NVIDIA, DXGI for vendor-neutral incl. AMD, WMI for identity) with graceful degradation to RAM/disk-only telemetry at every failure point — directly targeting the requester's stated AMD Ryzen 7 + Radeon RX hardware as well as NVIDIA GPUs. Placement's consumption of the new VRAM signal is explicitly deferred (see Decisions Log) to keep this spec's blast radius limited to accurate telemetry publication, not placement policy changes.

Verified against the codebase directly (not assumed) by reading `src/exo/utils/info_gatherer/info_gatherer.py`, `src/exo/utils/info_gatherer/macmon.py`, `src/exo/utils/info_gatherer/system_info.py`, `src/exo/shared/types/profiling.py`, `src/exo/shared/types/backends.py`, `src/exo/shared/apply.py`, `src/exo/shared/types/state.py`, `src/exo/master/placement.py`, `src/exo/master/placement_utils.py`, `src/exo/api/main.py`, `src/exo/master/main.py`, `pyproject.toml`, `packaging/pyinstaller/exo.spec`, and `README.md`.

---
*This file is managed by the specify-meta skill.*
