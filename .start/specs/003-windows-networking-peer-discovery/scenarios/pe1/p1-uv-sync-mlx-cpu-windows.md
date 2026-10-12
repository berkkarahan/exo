---
unit: pe1
feature: Enable Windows package resolution
priority: P1
---
# uv sync --extra mlx-cpu succeeds on Windows

## Scenario
On a Windows machine, from the repo root run `uv sync --extra mlx-cpu`.

## Expected
Command exits with status code 0.
The installed environment does not include any macOS-only package (e.g. no `macmon`-adjacent Metal-only MLX extra is pulled in).
`uv run exo --help` (or `--no-worker --no-api` combined with an immediate Ctrl-C) runs without an `ImportError` or `ModuleNotFoundError` originating from a missing platform-specific dependency.
</content>
