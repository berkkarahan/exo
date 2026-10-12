---
id: br1
title: Backend Registry
type: refactor
dependencies: [we1, bd1]
---
# Backend Registry

## Goal

Replace `bootstrap.py`'s hardcoded image-vs-text `if/else` builder selection with a registry lookup keyed by the node's detected `Backend` capability, so the runner entrypoint can dispatch to `MlxBuilder`, `MfluxBuilder`, or the new `OnnxGenAiBuilder` without a growing `if/elif` chain.

## Requirements

- New `src/exo/worker/runner/backend_registry.py` defines a `BACKEND_BUILDERS` mapping (or equivalent lookup function) from `(is_image_model, Backend)` to a `Builder` factory callable, registering the existing `MfluxBuilder`/`MlxBuilder` construction logic (currently `bootstrap.py:67-86`) and the new `OnnxGenAiBuilder` (we1) as entries.
- `src/exo/worker/runner/bootstrap.py`'s `entrypoint()` function (`bootstrap.py:40-105`) is modified to call the registry instead of the inline `if bound_instance.is_image_model: ... else: ...` block, while producing byte-for-byte identical `Builder` construction behavior for existing MLX/image instances (no behavior change for macOS/Linux).
- The registry lookup correctly selects `OnnxGenAiBuilder` when the bound instance's assigned backend (via `BoundInstance`/`ShardMetadata`) is `OnnxDirectMl`, `OnnxCuda`, or `OnnxCpu`.
- If no registered builder matches a given `(is_image_model, Backend)` combination, the registry raises a clear, typed error at entrypoint time (not a silent no-op or an unrelated `AttributeError`).
- Existing MLX-patch application (`apply_mlx_patches()`, `bootstrap.py:75-77`) continues to run only on the MLX code path, not on the Windows path.

## Constraints

- Follow existing patterns (see AGENTS.md) — no behavior change to the MLX/image construction calls themselves, only how they are selected.
- Must not modify `engines/base.py`, `engines/mlx/**`, or `engines/image/**` internals.
- Full test coverage for all requirements: tests asserting the registry returns the correct builder type for each `(is_image_model, Backend)` combination, and raises for an unregistered combination.

## Interfaces

A lookup function/mapping in `backend_registry.py`, consumed by `bootstrap.entrypoint()`. Depends on `OnnxGenAiBuilder` (we1) and on `Backend` values actually being detectable (bd1) so the dispatch key is meaningful end-to-end.
