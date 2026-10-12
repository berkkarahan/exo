---
title: "Windows Filesystem State Paths"
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

| specId | title | status | phases | totalTasks | parallelTasks | specReferences | clarificationsRemaining |
|--------|-------|--------|--------|------------|-----------------|-------------------|--------------------------|
| 005-windows-filesystem-state-paths | Windows Filesystem State Paths | COMPLETE | 4 | 12 | 2 | 34 | 0 |

### PhaseStatus

| phase | name | status | tasks | file | detail |
|-------|------|--------|-------|------|--------|
| 1 | Platform-Aware Root Resolution | COMPLETE | 3 | phase-1.md | |
| 2 | Multi-Path Parsing & Absolute-Override Regression Lock | COMPLETE | 3 | phase-2.md | |
| 3 | Long-Path Packaging & Documentation | COMPLETE | 3 | phase-3.md | |
| 4 | Final Integration & Cross-Platform Validation | COMPLETE | 3 | phase-4.md | |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate — read the phase's Context Priming section and the referenced solution.md sections in full.
2. **During Implementation**: Reference specific solution.md sections in each task via `[ref: ...]` tags.
3. **After Each Task**: Run `uv run basedpyright && uv run ruff check` and the relevant test file.
4. **Phase Completion**: Verify all specification requirements listed in the phase's Tasks section are met before marking the phase checkbox complete.

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale in the relevant phase file.
2. Obtain approval before proceeding.
3. Update solution.md when the deviation improves the design.
4. Record all deviations in this plan for traceability.

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

- `.start/specs/005-windows-filesystem-state-paths/requirements.md` - Product Requirements (Features F1-F4, Gherkin ACs)
- `.start/specs/005-windows-filesystem-state-paths/solution.md` - Solution Design (ADR-1 through ADR-5, Implementation Examples, EARS Acceptance Criteria)
- `src/exo/shared/constants.py` - the single file whose internal logic changes (lines 7-108)
- `src/exo/shared/tests/test_xdg_paths.py` - existing regression guard that must keep passing unmodified (lines 10-213)

**Key Design Decisions**:

- **ADR-1**: Windows `%APPDATA%`/`%LOCALAPPDATA%` root split — `EXO_CONFIG_HOME → %APPDATA%\exo`, `EXO_DATA_HOME → %LOCALAPPDATA%\exo`, `EXO_CACHE_HOME → %LOCALAPPDATA%\exo\Cache`.
- **ADR-2**: Legacy `~/.exo` reuse-in-place — if it already exists on Windows, keep using it and log one line; never auto-migrate or dual-root silently.
- **ADR-3**: Replace hard-coded `:` with `os.pathsep` when parsing `EXO_MODELS_DIRS`/`EXO_MODELS_READ_ONLY_DIRS` — fixes the Windows drive-letter collision, byte-for-byte unchanged on POSIX.
- **ADR-4**: Leave Hugging Face's own cache/token resolution (`huggingface_utils.py:65-67`) untouched — do not redirect it to a Windows-conventional path.
- **ADR-5**: Long-path support is a build-manifest opt-in in `packaging/pyinstaller/exo.spec` plus documentation, not new runtime path-manipulation code.

**Implementation Context**:

```bash
# Testing
uv run pytest src/exo/shared/tests/test_xdg_paths.py   # targeted regression suite
uv run pytest                                            # full suite (excludes slow tests)

# Quality
uv run basedpyright     # strict type checking, must be 0 errors
uv run ruff check       # linting

# Formatting
nix fmt

# Full validation gate (per AGENTS.md)
uv run basedpyright && uv run ruff check && nix fmt && uv run pytest
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [ ] [Phase 1: Platform-Aware Root Resolution](phase-1.md)
- [ ] [Phase 2: Multi-Path Parsing & Absolute-Override Regression Lock](phase-2.md)
- [ ] [Phase 3: Long-Path Packaging & Documentation](phase-3.md)
- [ ] [Phase 4: Final Integration & Cross-Platform Validation](phase-4.md)

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
