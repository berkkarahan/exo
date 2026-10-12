---
title: "Phase 4: Final Integration & Cross-Platform Validation"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Final Integration & Cross-Platform Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: solution/Quality Requirements]`
- `[ref: solution/Acceptance Criteria]` — full EARS criteria set (Main Flow, Error Handling, Edge Case)
- `[ref: requirements/Success Metrics > Key Performance Indicators]`
- `[ref: solution/Constraints; CON-3]` — zero regression on `test_xdg_paths.py`

**Key Decisions**:
- This phase makes no new design decisions; it verifies the combined output of Phases 1-3 against every acceptance criterion in `requirements.md` and `solution.md` before the feature is considered done.

**Dependencies**:
- Phase 1 (root resolution), Phase 2 (parsing fix + regression lock), and Phase 3 (packaging + docs) must all be complete before this phase starts.

---

## Tasks

This phase runs the full project quality gate across every platform branch this feature touches (Linux, macOS, and Windows, the last two simulated via `unittest.mock` since CI/dev execution here is not on native Windows hardware) and confirms the feature is fully done against both specification documents.

- [ ] **T4.1 Full cross-platform regression run** `[activity: validate]`

  1. Prime: Re-read `src/exo/shared/tests/test_xdg_paths.py` in its post-Phase-1/2 state in full, plus `requirements.md`'s Feature 1-4 Gherkin criteria and `solution.md`'s Acceptance Criteria section, to build the complete checklist of behaviors to confirm.
  2. Test: Run `uv run pytest src/exo/shared/tests/test_xdg_paths.py -v` and manually cross-check that every one of the following passes unmodified in assertion content: `test_xdg_paths_on_linux`, `test_xdg_default_paths_on_linux`, `test_legacy_exo_home_takes_precedence`, `test_macos_uses_traditional_paths`, `test_models_in_data_dir`, `test_default_dir_always_prepended_to_models_dirs`, `test_default_models_dir_override`, `test_default_dir_only_entry_when_env_unset`, `test_overlap_between_dirs_and_read_only_dirs`, `test_empty_read_only_dirs_when_unset` — plus every new Windows/legacy/pathsep/absolute-override test added in Phases 1-2.
  3. Implement: N/A — this task is pure verification; if any behavior does not match, route the fix back to the owning Phase 1/2 task per the Deviation Protocol rather than patching ad hoc in this phase.
  4. Validate: `uv run pytest` (full suite, excluding slow tests per default marker config) passes with zero failures and zero newly-skipped tests.
  5. Success: Every existing Darwin/Linux assertion is provably unchanged `[ref: solution/Constraints; CON-3]`; every new Windows-branch test passes `[ref: requirements/AC F1, F2, F3]`.

- [ ] **T4.2 Type-check and lint gate** `[activity: validate]` `[parallel: true]`

  1. Prime: Re-read the final diff of `src/exo/shared/constants.py` and `src/exo/shared/tests/test_xdg_paths.py` in full.
  2. Test: N/A — this task runs static analysis, not behavioral tests.
  3. Implement: N/A — verification only; route any type or lint error back to the relevant Phase 1/2 task.
  4. Validate: `uv run basedpyright` reports zero errors across the changed files (strict mode, no bypassing the type checker per AGENTS.md code style). `uv run ruff check` reports zero violations. `nix fmt` produces no further diff (or its diff is staged if it reformats anything).
  5. Success: The feature's diff passes the project's full pre-commit gate exactly as documented in AGENTS.md (`uv run basedpyright && uv run ruff check && nix fmt && uv run pytest`).

- [ ] **T4.3 Final specification sign-off** `[activity: validate]`

  - Cross-reference every Gherkin acceptance criterion in `requirements.md` (Features 1-4) against its corresponding EARS criterion in `solution.md`'s Acceptance Criteria section and confirm each has a passing test from T4.1 or a completed packaging/documentation task from Phase 3. Confirm no `[NEEDS CLARIFICATION]` marker or placeholder remains anywhere in `requirements.md`, `solution.md`, or `plan/`. This is the terminal validation task for the entire spec; once complete, the spec's Decomposition Status in `README.md` is updated to `completed`.
