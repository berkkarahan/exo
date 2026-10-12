---
title: "Phase 1: Platform-Aware Root Resolution"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Platform-Aware Root Resolution

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: solution/Solution Strategy]` — single-module resolution seam, all branching stays inside `constants.py`
- `[ref: solution/Building Block View > Implementation Examples > Windows-aware root resolution with legacy detection]`
- `[ref: solution/Runtime View > Complex Logic]` — the four-branch resolution algorithm and its required evaluation order
- `[ref: solution/Architecture Decisions; ADR-1, ADR-2]`

**Key Decisions**:
- ADR-1: `EXO_CONFIG_HOME → %APPDATA%\exo`, `EXO_DATA_HOME → %LOCALAPPDATA%\exo`, `EXO_CACHE_HOME → %LOCALAPPDATA%\exo\Cache` on Windows, only when no legacy root exists.
- ADR-2: If `home / ".exo"` already exists on Windows and `EXO_HOME` is unset, reuse it in place for all three roots and log exactly one line; never auto-migrate.
- Branch order is a hard requirement: `EXO_HOME` (any platform) → Linux XDG → Windows (legacy-check, then fresh-install split) → other (macOS fallback, unchanged).

**Dependencies**:
- None — this is the first phase and the sole prerequisite for every later phase (Phase 2's parsing fix lives in the same file but is functionally independent; Phase 3 and 4 both depend on this phase's resolution logic existing).

---

## Tasks

This phase establishes the corrected Windows path-resolution branch inside `src/exo/shared/constants.py`, including legacy-root detection and reuse-in-place, while proving the existing Linux/macOS/`EXO_HOME` branches are provably unchanged.

- [ ] **T1.1 Windows fresh-install root resolution** `[activity: backend-api]`

  1. Prime: Read the current `_get_xdg_dir` implementation `[ref: solution/Implementation Context; file: src/exo/shared/constants.py lines 7-22]` and the branch-order algorithm `[ref: solution/Runtime View > Complex Logic]`.
  2. Test: On a mocked `sys.platform == "win32"` with `APPDATA`/`LOCALAPPDATA` set and no `EXO_HOME` and no pre-existing `~/.exo` (mock `Path.exists` to return `False`), assert `EXO_CONFIG_HOME == Path(APPDATA) / "exo"`, `EXO_DATA_HOME == Path(LOCALAPPDATA) / "exo"`, `EXO_CACHE_HOME == Path(LOCALAPPDATA) / "exo" / "Cache"`; also test the fallback when `APPDATA`/`LOCALAPPDATA` are unset, expecting `home / "AppData" / "Roaming" / "exo"` and `home / "AppData" / "Local" / "exo"`.
  3. Implement: Extend `src/exo/shared/constants.py`'s root-resolution logic with a `sys.platform == "win32"` branch inserted between the existing `EXO_HOME` check and the existing Linux check's `else` fallthrough, per the illustrative structure in `[ref: solution/Building Block View > Implementation Examples]`.
  4. Validate: `uv run pytest src/exo/shared/tests/test_xdg_paths.py` — new Windows tests pass; all pre-existing tests in the file are still present and unmodified. `uv run basedpyright` and `uv run ruff check` clean on `constants.py`.
  5. Success: Windows fresh-install resolves to the `%APPDATA%`/`%LOCALAPPDATA%` split with no environment variables required `[ref: requirements/AC F1.1]`; missing `APPDATA`/`LOCALAPPDATA` fail safely to Windows' own default locations `[ref: solution/Acceptance Criteria; Error Handling Criteria]`.

- [ ] **T1.2 Legacy `~/.exo` detection and reuse-in-place** `[activity: backend-api]`

  1. Prime: Read the legacy-detection sub-case of the traced walkthrough `[ref: solution/Building Block View > Implementation Examples; row 2 and row 3]` and the fail-safe requirement for `OSError` during the existence check `[ref: solution/Runtime View > Error Handling]`.
  2. Test: On a mocked `sys.platform == "win32"` with no `EXO_HOME` and `Path.exists` mocked to return `True` for `home / ".exo"`, assert all three roots resolve to `home / ".exo"` and that a log line is emitted (assert via `loguru`'s test sink or `caplog`-equivalent capture) stating the reused path. Separately, test that when `Path.exists` raises `OSError`, resolution falls through to the fresh-install branch from T1.1 without raising.
  3. Implement: Add the legacy-root existence check (wrapped to treat any `OSError` as "not found") before the fresh-install `APPDATA`/`LOCALAPPDATA` split from T1.1, and add the one `logger.info(...)` call on the reuse path. Add the `loguru` import to `constants.py` (its one new import for this feature) `[ref: solution/Cross-Cutting Concepts > Logging/Auditing]`.
  4. Validate: `uv run pytest src/exo/shared/tests/test_xdg_paths.py` passes including the new legacy-detection tests; `uv run basedpyright && uv run ruff check` clean.
  5. Success: Pre-existing `~/.exo` on Windows is reused in place with exactly one log line `[ref: requirements/AC F3.1, F3.2]`; a Windows machine with no legacy root never creates one `[ref: requirements/AC F3.3]`; `EXO_HOME` still takes precedence over the legacy check on every platform `[ref: solution/Acceptance Criteria; Edge Case Criteria - EXO_HOME precedence]`.

- [ ] **T1.3 Phase Validation** `[activity: validate]`

  - Run the full `test_xdg_paths.py` suite plus the new Windows/legacy tests added in T1.1/T1.2. Confirm every pre-existing Linux and macOS assertion (`test_xdg_paths_on_linux`, `test_xdg_default_paths_on_linux`, `test_legacy_exo_home_takes_precedence`, `test_macos_uses_traditional_paths`) still passes with an unmodified assertion body `[ref: solution/Constraints; CON-3]`. Run `uv run basedpyright` and `uv run ruff check` against `src/exo/shared/constants.py` and `src/exo/shared/tests/test_xdg_paths.py`. Verify against `solution.md`'s Runtime View branch-order algorithm and `requirements.md` Feature 1 and Feature 3 acceptance criteria.
