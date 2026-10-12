---
title: "Phase 1: Shared Telemetry Data Contract"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Shared Telemetry Data Contract

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: solution/Application Data Models; lines: SystemPerformanceProfile, WindowsGpuMetrics, GatheredInfo entries]`
- `[ref: solution/Architecture Decisions; ADR-1, ADR-3]`
- `[ref: solution/Implementation Boundaries]` — `src/exo/shared/types/profiling.py`, `src/exo/utils/info_gatherer/info_gatherer.py`, `src/exo/shared/apply.py` are all listed as "Can Modify"

**Key Decisions**:
- ADR-1: `WindowsGpuMetrics` is a new `GatheredInfo` union member, following the exact `TaggedModel` shape of `MacmonMetrics` (`macmon.py:46-69`), not a bespoke event type.
- ADR-3: VRAM is a plain data field (`vram_total`/`vram_available: Memory | None`) on the existing `SystemPerformanceProfile` — no new placement-facing type, no change to `place_instance`/`filter_cycles_by_memory`.

**Dependencies**:
- None — this phase establishes the shared contract that Phase 2 and Phase 3 build on.

---

## Tasks

Establishes the typed data contract (extended `SystemPerformanceProfile`, new `WindowsGpuMetrics` event type, and the `apply.py` state-projection arm) that every later phase's Windows telemetry code writes into. No Windows-specific gathering logic lives in this phase — it is pure type/plumbing work, independently testable without a Windows machine.

- [ ] **T1.1 SystemPerformanceProfile VRAM fields** `[activity: domain-modeling]`

  1. Prime: Read `SystemPerformanceProfile` `[ref: solution/Application Data Models; lines: SystemPerformanceProfile (MODIFIED)]` and the existing model at `src/exo/shared/types/profiling.py:59-66`.
  2. Test: A `SystemPerformanceProfile` constructed with no VRAM args defaults `vram_total`/`vram_available` to `None` (Darwin/no-GPU case unaffected); a `SystemPerformanceProfile` constructed with explicit `Memory` values round-trips through Pydantic serialization/deserialization (camelCase alias, `frozen=True`, `strict=True` per `src/exo/utils/pydantic_ext.py:11-18`) without error.
  3. Implement: Add `vram_total: Memory | None = None` and `vram_available: Memory | None = None` fields to `SystemPerformanceProfile` in `src/exo/shared/types/profiling.py`.
  4. Validate: Unit tests pass; `uv run basedpyright` clean (strict mode — `Memory` is already imported in this file); `uv run ruff check` clean.
  5. Success: `SystemPerformanceProfile` carries VRAM data without breaking any existing Darwin consumer `[ref: requirements/Feature 2; criterion 1]`; `None` is the explicit "no discrete GPU / telemetry unavailable" representation, never a fabricated `0` `[ref: solution/Key Decisions, item 1]`.

- [ ] **T1.2 WindowsGpuMetrics event type and apply.py state projection** `[activity: domain-modeling]`

  1. Prime: Review `MacmonMetrics`'s raw-to-normalized pattern `[ref: solution/Pattern Documentation; TaggedModel raw-to-normalized gather]` (`macmon.py:46-69`) and the exhaustive `match` in `apply_node_gathered_info` `[ref: solution/Implementation Context/Code Context; apply.py]` (`src/exo/shared/apply.py:364-468`).
  2. Test: A `WindowsGpuMetrics(system_profile=...)` round-trips through `TaggedModel` serialization (wrapped as `{"WindowsGpuMetrics": {...}}` per `pydantic_ext.py:21-25`); `apply_node_gathered_info` given a `NodeGatheredInfo(info=WindowsGpuMetrics(system_profile=SystemPerformanceProfile(vram_total=Memory.from_gb(8), ...)))` updates `State.node_system[node_id]` to that profile, matching the existing `MacmonMetrics` case's `state.node_system` update shape (`apply.py:365-369`) but without touching `state.node_memory` (Windows RAM comes from the existing `MemoryUsage` variant, not this one).
  3. Implement: Add `class WindowsGpuMetrics(TaggedModel): system_profile: SystemPerformanceProfile` to a new `src/exo/utils/info_gatherer/windows_telemetry.py` module; append `WindowsGpuMetrics` to the `GatheredInfo` union in `src/exo/utils/info_gatherer/info_gatherer.py:386-399`; add a `case WindowsGpuMetrics():` arm to the `match info:` block in `src/exo/shared/apply.py:364-468` that updates `state.node_system` identically to the `MacmonMetrics` arm's `node_system` line (`apply.py:366-369`) minus the `node_memory` update.
  4. Validate: Unit tests pass; `uv run basedpyright` clean — a missing `case` arm here is a compile-time error in strict mode, confirming exhaustiveness; `uv run ruff check` clean.
  5. Success: `apply_node_gathered_info` handles the new variant exhaustively with no `basedpyright` `reportMatchNotExhaustive`-class error `[ref: solution/Constraints; CON-2]`; state projection matches the `MacmonMetrics` precedent exactly `[ref: solution/Pattern Documentation]`.

- [ ] **T1.3 Phase Validation** `[activity: validate]`

  Run all Phase 1 tests (`uv run pytest src/exo/shared/tests src/exo/utils/info_gatherer/tests` or equivalent paths covering `profiling.py`/`apply.py`/the new `windows_telemetry.py` module). Verify against `solution.md`'s Application Data Models and Architecture Decisions sections and `requirements.md` Feature 2/Feature 3 acceptance criteria that reference VRAM/identity data shape. `uv run basedpyright && uv run ruff check` both pass with zero errors.
