---
title: "Phase 3: Long-Path Packaging & Documentation"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Long-Path Packaging & Documentation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: solution/Architecture Decisions; ADR-5]`
- `[ref: solution/Implementation Context; file: packaging/pyinstaller/exo.spec lines 10-27, 65-70]`
- `[ref: requirements/Feature 4 - Long Path Awareness for Deep Model Snapshot Directories]`
- `[ref: solution/Interface Specifications > Environment Variable Contract]` — for the README env-var table update

**Key Decisions**:
- ADR-5: Long-path support is a build-manifest opt-in (`longPathAware`-equivalent PyInstaller `EXE()` option) for the frozen build, plus documentation for source installs — not new runtime path-manipulation code.
- No change to `download_utils.py`'s file I/O; exo's own code already uses `pathlib`/`os` exclusively with no raw Win32 API calls.

**Dependencies**:
- Independent of Phase 1 and Phase 2's `constants.py` changes; can run in parallel with them, but documentation updates in this phase reference the finished environment-variable behavior from Phase 2 (the `os.pathsep` change), so documentation content should be finalized after Phase 2's task T2.1 is implemented.

---

## Tasks

This phase declares Windows long-path awareness for the frozen build and brings `README.md`'s environment-variable and file-location documentation up to date with the Windows behavior introduced in Phases 1-2.

- [ ] **T3.1 Long-path-aware manifest declaration for the frozen Windows build** `[activity: backend-api]`

  1. Prime: Read the current `exo.spec` `EXE()` call and platform-conditional `BINARIES`/`DATAS` structure `[ref: solution/Implementation Context; file: packaging/pyinstaller/exo.spec lines 72-117]`.
  2. Test: Since this is a build-manifest change with no Python runtime behavior to unit-test, validate by confirming (a) `exo.spec` still parses as valid Python/PyInstaller spec syntax, and (b) the added manifest option is scoped so it only applies conditionally for `sys.platform == "win32"` builds, mirroring the existing `if sys.platform == "darwin":` pattern already used for `MACMON_PATH`/`BINARIES` in the same file.
  3. Implement: Add a Windows-only long-path-aware manifest declaration to the `EXE()` call in `exo.spec` (e.g. via PyInstaller's manifest/`uac_admin`-style options or an embedded manifest XML fragment declaring `longPathAware=true`), following the same `if sys.platform == "win32":` conditional style already used for the `darwin` macmon block.
  4. Validate: Manual review confirms the change is additive-only (no existing `DATAS`/`BINARIES`/`HIDDEN_IMPORTS` entries are altered) and gated strictly to Windows, per the Must Not Touch boundary on macOS/Linux packaging behavior.
  5. Success: The frozen Windows build declares itself long-path-aware `[ref: requirements/AC F4.1]`; no change to macOS or Linux packaging output.

- [ ] **T3.2 README.md Windows documentation update** `[activity: validate]` `[parallel: true]`

  1. Prime: Read the existing "File Locations (Linux)" and "Environment Variables" sections of `README.md` to match their existing tone and table format.
  2. Test: N/A (documentation-only task); validated by proofreading against the actual resolved behavior implemented in Phase 1/Phase 2.
  3. Implement: Add a "File Locations (Windows)" subsection documenting `%APPDATA%\exo\config.toml` (config), `%LOCALAPPDATA%\exo\models` (default models dir), `%LOCALAPPDATA%\exo\Cache\exo_log` (logs), and the legacy `~/.exo` reuse-in-place note; update the `EXO_MODELS_DIRS`/`EXO_MODELS_READ_ONLY_DIRS` row in the Environment Variables table to read "colon-separated (semicolon-separated on Windows)"; add a short troubleshooting note pointing source (non-frozen) Windows users at the `LongPathsEnabled` registry setting for Feature 4's edge case.
  4. Validate: Proofread the new sections against `solution.md`'s Interface Specifications and the actual resolved paths from Phase 1, so documentation never contradicts implementation.
  5. Success: A new Windows user can read `README.md` alone and correctly predict where their config, models, and logs will live, and how to fix a long-path failure on a source install `[ref: requirements/AC F4.2]`.

- [ ] **T3.3 Phase Validation** `[activity: validate]`

  - Confirm `exo.spec` remains valid and its Windows-only addition does not affect the existing `darwin`-conditional `MACMON_PATH` block or any `DATAS`/`HIDDEN_IMPORTS` entry. Confirm `README.md`'s new content accurately reflects the resolved paths implemented in Phase 1 and the separator behavior implemented in Phase 2. Verify against `requirements.md` Feature 4 and `solution.md` ADR-5.
