---
title: "Phase 2: Multi-Path Parsing & Absolute-Override Regression Lock"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Multi-Path Parsing & Absolute-Override Regression Lock

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: solution/Building Block View > Implementation Examples > os.pathsep-based multi-path parsing]`
- `[ref: solution/Architecture Decisions; ADR-3]`
- `[ref: solution/Risks and Technical Debt > Known Technical Issues]` — the verified non-issue regarding `EXO_HOME`/`EXO_DASHBOARD_DIR` absolute-path overrides
- `[ref: solution/Interface Specifications > Environment Variable Contract]`

**Key Decisions**:
- ADR-3: Replace `raw.split(":")` with `raw.split(os.pathsep)` in the directory-list parser — identical behavior on POSIX (`os.pathsep == ':'`), fixes the Windows drive-letter collision (`os.pathsep == ';'`).
- Verified via `pathlib.PureWindowsPath` that `EXO_HOME`/`EXO_DASHBOARD_DIR`/`EXO_RESOURCES_DIR` already accept absolute Windows overrides correctly today because pathlib's `/` operator discards the left operand when the right operand is itself absolute — this phase adds a regression test locking that behavior in, not a code fix.

**Dependencies**:
- Phase 1 (both changes land in the same file, `src/exo/shared/constants.py`; Phase 2 can be implemented independently of Phase 1's diff but should be verified together before Phase 4's integration pass).

---

## Tasks

This phase fixes the one verified functional bug in this feature (colon-vs-drive-letter collision) and adds regression coverage proving the `EXO_HOME`/`EXO_DASHBOARD_DIR` absolute-override behavior that DESIGN GUIDANCE flagged as a concern is, in fact, already correct.

- [ ] **T2.1 `os.pathsep`-based multi-path parsing** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read the current `_parse_colon_dirs` implementation `[ref: solution/Implementation Context; file: src/exo/shared/constants.py lines 38-42]` and the traced walkthrough table `[ref: solution/Building Block View > Implementation Examples > os.pathsep-based multi-path parsing]`.
  2. Test: Add/extend tests parametrized over `os.pathsep`: (a) POSIX-style values (`/tmp/a:/tmp/b`) still split into two entries when `os.pathsep` is mocked/actual `:`; (b) a Windows drive-letter value (`D:\exo-models`) mocked with `os.pathsep == ';'` splits into exactly one entry equal to the full path; (c) two Windows paths separated by `;` (`D:\exo-models;E:\more-models`) split into exactly two correct entries.
  3. Implement: Rename/modify `_parse_colon_dirs` to split on `os.pathsep` instead of the literal `":"`, preserving the existing `if p` empty-segment filter and `.expanduser()` call exactly as-is `[ref: solution/Building Block View > Implementation Examples > os.pathsep-based multi-path parsing]`.
  4. Validate: `uv run pytest src/exo/shared/tests/test_xdg_paths.py` passes, including `test_default_dir_always_prepended_to_models_dirs`, `test_overlap_between_dirs_and_read_only_dirs`, and `test_empty_read_only_dirs_when_unset` unmodified. `uv run basedpyright && uv run ruff check` clean.
  5. Success: `EXO_MODELS_DIRS`/`EXO_MODELS_READ_ONLY_DIRS` parse correctly on Windows for drive-letter paths `[ref: requirements/AC F2.1, F2.2]`; POSIX parsing is byte-for-byte unchanged `[ref: requirements/AC F2.3]`.

- [ ] **T2.2 Absolute-override regression lock for `EXO_HOME`/`EXO_DASHBOARD_DIR`** `[activity: validate]` `[parallel: true]`

  1. Prime: Read the verified-non-issue note `[ref: solution/Risks and Technical Debt > Known Technical Issues]` documenting that pathlib's absolute-path join semantics already make `EXO_HOME`/`EXO_DASHBOARD_DIR`/`EXO_RESOURCES_DIR` accept absolute overrides (including Windows drive-letter paths) without any code change.
  2. Test: Add a regression test that sets `EXO_HOME` to an absolute Windows-style path (e.g. `r"D:\custom-exo"`) under a mocked `sys.platform == "win32"` and asserts `EXO_CONFIG_HOME == Path(r"D:\custom-exo")` (i.e. the `home /` prefix is fully discarded, not appended). Add an equivalent test for a POSIX absolute path (e.g. `/opt/custom-exo`) under `sys.platform == "linux"`.
  3. Implement: No production code change for this task — it is a pure regression-test addition proving existing behavior, per ADR-3's sibling finding. If the new test fails, escalate immediately per the Deviation Protocol rather than "fixing" working code.
  4. Validate: `uv run pytest src/exo/shared/tests/test_xdg_paths.py` passes with the two new absolute-override tests green on the first run (no implementation change needed). `uv run basedpyright && uv run ruff check` clean.
  5. Success: Absolute `EXO_HOME`/`EXO_DASHBOARD_DIR` overrides are locked in by an executable regression test on both Windows-style and POSIX-style absolute paths `[ref: solution/Interface Specifications > Environment Variable Contract; EXO_HOME entry]`.

- [ ] **T2.3 Phase Validation** `[activity: validate]`

  - Run the full `test_xdg_paths.py` suite (all tests from Phase 1 and Phase 2 combined). Confirm zero changes to any pre-existing assertion. Run `uv run basedpyright` and `uv run ruff check`. Verify against `solution.md` ADR-3 and the Environment Variable Contract, and `requirements.md` Feature 2 acceptance criteria.
