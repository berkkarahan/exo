---
title: "Phase 2: Windows GPU Telemetry Provider"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Windows GPU Telemetry Provider

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: solution/Implementation Examples; Example: Windows GPU telemetry source layering with graceful degradation]`
- `[ref: solution/Runtime View; Primary Flow: Windows node telemetry tick]`
- `[ref: solution/Error Handling]`
- `[ref: solution/Architecture Decisions; ADR-1, ADR-2, ADR-4]`

**Key Decisions**:
- ADR-2: Source priority is NVML → DXGI → `None`; WMI is identity-only and is handled in Phase 3, not here.
- ADR-4: NVML device index 0 is authoritative when multiple GPU vendors are present, matching `_has_nvml_cuda()`'s existing device selection.
- Every source function (`_try_nvml`, `_try_dxgi`) returns `SystemPerformanceProfile | None` and must never raise past its own boundary — this is the load-bearing contract of Feature 4 (telemetry never takes the node down).

**Dependencies**:
- Phase 1 — requires `SystemPerformanceProfile.vram_total`/`vram_available` and `WindowsGpuMetrics` to exist.

---

## Tasks

Implements the actual Windows GPU telemetry gathering: the NVML and DXGI source functions, the priority-order combinator, and the `InfoGatherer` task that polls it and degrades gracefully. This is the component that directly answers "does the Windows node report accurate VRAM."

- [ ] **T2.1 NVML and DXGI GPU telemetry sources with priority combinator** `[activity: backend-api]`

  1. Prime: Read the traced walkthrough `[ref: solution/Implementation Examples; Traced walkthrough table (Node A/B/C)]` and the existing NVML soft-import pattern at `src/exo/utils/info_gatherer/info_gatherer.py:357-369` (`_has_nvml_cuda`).
  2. Test: `_try_nvml()` returns a `SystemPerformanceProfile` with correct `vram_total`/`vram_available`/`gpu_usage` when `pynvml` is mocked to succeed; returns `None` when `pynvml` import raises `ImportError` (mirrors Node C/no-library case); returns `None` when `nvmlInit`/`nvmlDeviceGetHandleByIndex`/`nvmlDeviceGetMemoryInfo` raise any `Exception` (mirrors the "elevated privileges silently produce zero" risk — must return `None`, never a zeroed profile). `_try_dxgi()` returns a `SystemPerformanceProfile` when the DXGI call succeeds (mocked) and `None` on any failure. `gather_windows_gpu_profile()` returns NVML's result when NVML succeeds (Node A), DXGI's result when only DXGI succeeds (Node B — the stated AMD Radeon RX case), and `None` when both fail (Node C).
  3. Implement: Add `_try_nvml`, `_try_dxgi`, and `gather_windows_gpu_profile` to `src/exo/utils/info_gatherer/windows_telemetry.py` per the reference implementation `[ref: solution/Implementation Examples]`; each `_try_*` function wraps its entire body in `try/except Exception: return None` so no exception escapes.
  4. Validate: Unit tests pass covering all three Node A/B/C scenarios plus the NVML-exception-mid-call case; `uv run basedpyright` clean; `uv run ruff check` clean.
  5. Success: VRAM figures are sourced from NVML for NVIDIA GPUs and DXGI for AMD/other GPUs `[ref: requirements/Feature 2; criterion 2, criterion 3]`; no source failure raises past `gather_windows_gpu_profile` `[ref: requirements/Feature 4; criterion 1]`.

- [ ] **T2.2 InfoGatherer Windows dispatch and polling task** `[activity: backend-api]`

  1. Prime: Read `InfoGatherer.run()`'s `IS_DARWIN` dispatch `[ref: solution/Runtime View; Primary Flow steps 1-2]` (`info_gatherer.py:444-456`) and the `to_thread.run_sync` offloading pattern used by `_has_nvml_cuda` (`info_gatherer.py:380`).
  2. Test: With `IS_WINDOWS` monkeypatched `True`, `InfoGatherer.run()` starts a `_monitor_windows_gpu` task (assert via task-group introspection or a spy on `tg.start_soon`); `_monitor_windows_gpu`, given a `gather_windows_gpu_profile` that returns a profile, sends exactly one `WindowsGpuMetrics` via `info_sender` per tick; given a `gather_windows_gpu_profile` that returns `None`, sends nothing for that tick and does not raise; given a `gather_windows_gpu_profile` that itself raises, the task logs a warning (via `logger.opt(exception=e).warning`, matching `info_gatherer.py:472-473`'s pattern) and continues its loop rather than propagating.
  3. Implement: Add `IS_WINDOWS = sys.platform == "win32"` beside `IS_DARWIN` in `info_gatherer.py:43`; add `_monitor_windows_gpu(self, gpu_poll_interval: float)` as a method on `InfoGatherer` that loops `await to_thread.run_sync(gather_windows_gpu_profile)`, sends a `WindowsGpuMetrics` on success, and follows the `try/except Exception: logger.opt(exception=e).warning(...)` + `anyio.sleep` shape used by every other monitor task (`info_gatherer.py:565-644`); wire `if IS_WINDOWS: tg.start_soon(self._monitor_windows_gpu, 1)` into `InfoGatherer.run()` (`info_gatherer.py:444-456`), alongside the existing unconditional `_monitor_memory_usage` start for non-Darwin.
  4. Validate: Unit tests pass; `uv run basedpyright` clean; `uv run ruff check` clean.
  5. Success: A Windows node's GPU telemetry polls on a 1s cadence matching macmon `[ref: solution/Quality Requirements; Performance]`; a raising/failing GPU source never stops `_monitor_memory_usage` or any other concurrently running task `[ref: requirements/Feature 4; criterion 2]`.

- [ ] **T2.3 Phase Validation** `[activity: validate]`

  Run all Phase 2 tests covering `windows_telemetry.py` and the new `InfoGatherer` dispatch/task. Verify against `solution.md`'s Runtime View sequence diagram and Error Handling section, and `requirements.md` Feature 2 and Feature 4 acceptance criteria. `uv run basedpyright && uv run ruff check` both pass with zero errors.
