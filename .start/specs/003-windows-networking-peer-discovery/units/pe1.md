---
id: pe1
title: Enable Windows package resolution
type: feature
dependencies: []
---
# Enable Windows package resolution

## Goal
Make `uv sync`/`uv lock` able to resolve exo's Python dependencies on `sys_platform == 'win32'`, without changing macOS/Linux resolution.

## Requirements
- `pyproject.toml`'s `tool.uv.environments` list (currently `["sys_platform == 'darwin'", "sys_platform == 'linux'"]`, `pyproject.toml:188`) includes `"sys_platform == 'win32'"`.
- `uv lock` succeeds on a Windows machine and produces a lockfile entry set covering `win32`.
- `uv sync --extra mlx-cpu` succeeds on Windows (CPU-only backend, matching Linux's current CPU-only status — no MLX GPU/Metal extras are pulled in on Windows).
- macOS and Linux dependency resolution behavior is unchanged (no regression).

## Constraints
- Follow existing patterns (see AGENTS.md).
- Do not add a new `mlx-windows`-style extra unless an existing MLX backend extra already supports Windows; if none does, Windows resolves against the same `mlx-cpu` extra Linux uses.
- Full test coverage for all requirements — verified via `uv lock`/`uv sync` exit codes on all three platforms (CI or manual, whichever the implementer has access to).

## Interfaces
None — this unit only changes `pyproject.toml` configuration; it defines no runtime interface consumed by other units.
</content>
