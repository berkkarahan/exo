---
unit: cfg1
feature: windows-environment-workflow-setup
priority: P1
---
# Existing Darwin uv sync --extra mlx behavior is unchanged

## Scenario
On a macOS (Darwin) machine, or by inspecting the marker logic, run `uv sync --extra mlx`.

## Expected
`uv sync --extra mlx` resolves successfully exactly as it did before this spec's change, pulling in `mlx`, `mlx-lm`, `mlx-vlm`, `mflux`, and the Darwin-marked `torch`/`torchaudio`/`torchvision` entries.
The resolved dependency set is identical to what `uv sync --extra mlx` would have produced prior to the `environments` list change (i.e., adding the Windows marker to the base list produces no diff in Darwin's resolved lockfile).
