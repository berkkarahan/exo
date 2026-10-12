---
unit: cfg1
feature: windows-environment-workflow-setup
priority: P1
---
# Darwin/Linux-only MLX and torch extras keep their original platform markers

## Scenario
Inspect `pyproject.toml` lines covering the `mlx`, `mlx-cpu`, `mlx-cuda12`, and `mlx-cuda13` optional-dependency groups and their `[tool.uv.sources]` marker expressions for `mlx`, `mlx-cuda-12`, `mlx-cuda-13`, `mlx-lm`, `mflux`, `torch`, `torchvision`, and `torchaudio`.

## Expected
Every `sys_platform` marker on these extras and sources still reads exactly `'darwin'` or `'linux'` — none has been changed to include `'win32'`.
Attempting `uv sync --extra mlx` (or `mlx-cpu`/`mlx-cuda12`/`mlx-cuda13`) on a Windows platform still fails to resolve, because the extras' own markers exclude `win32` even though the base `environments` list now includes it.
