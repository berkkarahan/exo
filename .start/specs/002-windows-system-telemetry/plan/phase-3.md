---
title: "Phase 3: Windows Node Identity & Packaging"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Windows Node Identity & Packaging

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: solution/Implementation Examples; _try_wmi_identity]`
- `[ref: solution/Implementation Gotchas; pyproject.toml uv environments]`
- `[ref: solution/Constraints; CON-3]`

**Key Decisions**:
- WMI identity lookups return the existing `"Unknown Model"`/`"Unknown Chip"` literals on failure (`system_info.py:122-123`) so failure never regresses below current non-Darwin behavior.
- New Windows-only dependencies must use `sys_platform == 'win32'` PEP 508 markers so Darwin/Linux `uv` resolution (`pyproject.toml:188`) is untouched, and `win32` must be added to `uv`'s `environments` list for `uv sync` to succeed on Windows at all.

**Dependencies**:
- Phase 1 — `NodeIdentity` itself is unchanged, but this phase populates it via `StaticNodeInformation.gather() -> get_model_and_chip()`, which already flows into `apply.py`'s existing `StaticNodeInformation` case (`apply.py:386-399`, unmodified).
- Independent of Phase 2 — identity resolution does not depend on the GPU telemetry provider. `[parallel: true]` with Phase 2.

---

## Tasks

Replaces the hardcoded `"Unknown Model"`/`"Unknown Chip"` on Windows with real CPU/GPU names via WMI, and makes the new Windows-only dependencies (`pynvml` reuse, `wmi`/`pywin32`) resolvable by `uv` without breaking Darwin/Linux.

- [ ] **T3.1 Windows CPU/GPU identity resolution and dependency declaration** `[parallel: true]` `[activity: backend-api]`

  1. Prime: Read `get_model_and_chip()`'s Darwin-only `system_profiler` implementation `[ref: solution/Implementation Context/Code Context; system_info.py]` (`system_info.py:120-150`) and `uv`'s current environment restriction `[ref: solution/Constraints; CON-3]` (`pyproject.toml:184-189`).
  2. Test: `get_model_and_chip()` on a platform where `sys.platform == "win32"` (monkeypatched) returns real CPU/GPU name strings when a mocked WMI query succeeds (`Win32_Processor.Name`, `Win32_VideoController.Name`); returns `("Unknown Model", "Unknown Chip")` unchanged when the WMI query raises or the `wmi`/`pywin32` package is unavailable — asserting parity with the pre-existing Darwin-failure-path literals, never a crash. `uv.lock`/`pyproject.toml` dependency declarations resolve without error under `uv lock --dry-run` (or equivalent) simulated for `sys_platform == 'darwin'`, `'linux'`, and `'win32'` marker environments.
  3. Implement: Add a `win32` branch to `get_model_and_chip()` in `src/exo/utils/info_gatherer/system_info.py` that queries `Win32_Processor.Name` for `chip` and `Win32_VideoController.Name` for a GPU-derived `model` string (or an equivalent CPU/GPU naming split consistent with how macOS's `model`/`chip` fields are populated at `system_info.py:142-148`), wrapped in `try/except Exception` returning the existing `("Unknown Model", "Unknown Chip")` defaults on any failure; add `wmi; sys_platform == 'win32'` (or `pywin32; sys_platform == 'win32'`) to `pyproject.toml`'s dependencies and add `"sys_platform == 'win32'"` to the `environments` list at `pyproject.toml:188`.
  4. Validate: Unit tests pass; `uv run basedpyright` clean (note: `pyproject.toml:152` pins `pythonPlatform = "Darwin"` for static analysis — confirm the new Windows branch still type-checks under Darwin-platform analysis, since `basedpyright` checks syntax/types, not runtime platform); `uv run ruff check` clean; `uv sync` (or `uv lock`) succeeds without resolution errors.
  5. Success: A Windows node reports its real CPU and GPU model name instead of "Unknown Model"/"Unknown Chip" `[ref: requirements/Feature 3; criterion 1]`; an undetectable GPU still returns a labeled, non-crashing fallback `[ref: requirements/Feature 3; criterion 2]`; Darwin/Linux `uv` dependency resolution is unaffected by the new Windows-only dependency `[ref: solution/Constraints; CON-3]`.

- [ ] **T3.2 Phase Validation** `[activity: validate]`

  Run all Phase 3 tests covering `get_model_and_chip()`'s Windows branch. Verify against `solution.md`'s Implementation Gotchas section and `requirements.md` Feature 3 acceptance criteria. `uv run basedpyright && uv run ruff check` both pass with zero errors; confirm `pyproject.toml`'s `environments` list change does not alter existing Darwin/Linux dependency resolution output.
