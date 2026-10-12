---
unit: cfg1
feature: windows-environment-workflow-setup
priority: P0
---
# uv sync resolves a lockfile on native Windows

## Scenario
On a native Windows machine (or a Windows-platform uv resolution check), open `pyproject.toml` and inspect the `[tool.uv] environments` list, then run `uv sync` (no `--extra` flags) from the repository root.

## Expected
The `environments` list under `[tool.uv]` contains `"sys_platform == 'win32'"` in addition to the existing `"sys_platform == 'darwin'"` and `"sys_platform == 'linux'"` entries.
`uv sync` exits with status 0 and produces/updates `uv.lock` without an "no supported environments" or equivalent resolution error.
No `mlx`, `mlx-cpu`, `mlx-cuda12`, or `mlx-cuda13` package appears in the resolved dependency set for the Windows platform (the base dependency set only).
