---
title: "Windows System Telemetry for Topology-Aware Placement"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION: ...]` markers have been addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section is complete
- [x] All implementation phases are defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant solution.md sections
- [x] Every test references requirements.md acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Output Schema

### Plan Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| phases | PhaseStatus[] | Yes | Status of each implementation phase |
| totalTasks | number | Yes | Total tasks across all phases |
| parallelTasks | number | Yes | Tasks marked `[parallel: true]` |
| specReferences | number | Yes | Count of `[ref: ...]` specification links |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |

specId: `002-windows-system-telemetry`. status: `COMPLETE`. totalTasks: `11`. parallelTasks: `2`. specReferences: `33`. clarificationsRemaining: `0`.

### PhaseStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phase | number | Yes | Phase number |
| name | string | Yes | Phase name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| tasks | number | Yes | Task count in this phase |
| file | string | Yes | Path to phase file (phase-N.md) |
| detail | string | No | What needs clarification or what's in progress |

| phase | name | status | tasks | file |
|---|---|---|---|---|
| 1 | Shared Telemetry Data Contract | COMPLETE | 3 | phase-1.md |
| 2 | Windows GPU Telemetry Provider | COMPLETE | 3 | phase-2.md |
| 3 | Windows Node Identity & Packaging | COMPLETE | 2 | phase-3.md |
| 4 | Integration & Validation | COMPLETE | 3 | phase-4.md |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate
2. **During Implementation**: Reference specific solution.md sections in each task
3. **After Each Task**: Run Specification Compliance checks
4. **Phase Completion**: Verify all specification requirements are met

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale
2. Obtain approval before proceeding
3. Update solution.md when the deviation improves the design
4. Record all deviations in this plan for traceability

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[component: component-name]` - For multi-component features
- `[ref: document/section; lines: 1, 2-3]` - Links to specifications, patterns, or interfaces and (if applicable) line(s)
- `[activity: type]` - Activity hint for specialist agent selection

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

```markdown
# Single-line format
- Success: [Criterion] `[ref: requirements/AC-X.Y]`

# Multi-line format
- Success:
  - [ ] [Criterion 1] `[ref: requirements/AC-X.Y]`
  - [ ] [Criterion 2] `[ref: solution/Section]`
```

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `.start/specs/002-windows-system-telemetry/requirements.md` - Product Requirements
- `.start/specs/002-windows-system-telemetry/solution.md` - Solution Design
- `src/exo/utils/info_gatherer/info_gatherer.py` - Existing `IS_DARWIN` dispatch, macmon lifecycle, and `GatheredInfo` union to extend
- `src/exo/utils/info_gatherer/macmon.py` - Reference pattern for raw-to-normalized telemetry (`TaggedModel` + `from_raw`/`from_raw_json`)
- `src/exo/shared/apply.py` - `apply_node_gathered_info`'s exhaustive `match` over `GatheredInfo`, which requires a new `case` arm
- `src/exo/shared/types/profiling.py` - `SystemPerformanceProfile`, `MemoryUsage`, `NodeIdentity` models to extend

**Key Design Decisions**:

- **ADR-1**: Platform-dispatched telemetry provider - A new `IS_WINDOWS` flag drives a `_monitor_windows_gpu` task, mirroring `IS_DARWIN`'s dispatch shape, instead of patching Windows checks into Darwin-oriented functions.
- **ADR-2**: Windows GPU source layering - NVML (`pynvml`, NVIDIA) tried first, DXGI (`ctypes`, vendor-neutral incl. AMD) as fallback, WMI for CPU/GPU identity strings only; LibreHardwareMonitor rejected (external .NET process, often needs admin rights).
- **ADR-3**: Publish VRAM this spec; do not wire it into placement - `SystemPerformanceProfile` gains `vram_total`/`vram_available`, but `place_instance`/`filter_cycles_by_memory` are untouched in this phase.
- **ADR-4**: Multi-GPU-vendor tie-break - NVML device index 0 (the same device `_has_nvml_cuda()` already selects) is authoritative when both NVIDIA and non-NVIDIA GPUs are present.

**Implementation Context**:

```bash
# Testing
uv run pytest                       # Unit + integration tests (EXO_TESTS=1 set automatically)
uv run pytest src/exo/utils/info_gatherer/tests/test_windows_telemetry.py  # Targeted

# Quality
uv run ruff check                   # Linting
uv run basedpyright                 # Strict type checking
nix fmt                             # Formatting

# Full validation (run before considering any phase complete)
uv run basedpyright && uv run ruff check && nix fmt && uv run pytest
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [ ] [Phase 1: Shared Telemetry Data Contract](phase-1.md)
- [ ] [Phase 2: Windows GPU Telemetry Provider](phase-2.md)
- [ ] [Phase 3: Windows Node Identity & Packaging](phase-3.md)
- [ ] [Phase 4: Integration & Validation](phase-4.md)

---

## Plan Verification

Before this plan is ready for implementation, verify:

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All requirements.md acceptance criteria map to specific tasks | ✅ |
| All solution.md components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |
