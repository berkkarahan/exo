---
unit: wsl1
feature: windows-environment-workflow-setup
priority: P1
---
# setup.sh detects the NVIDIA GPU and recommends the matching CUDA extra

## Scenario
Inside a WSL2 Ubuntu distribution with `nvidia-smi` reporting a CUDA 12.x driver, run `scripts/wsl2/setup.sh`.

## Expected
The script's output recommends `uv sync --extra mlx-cuda12` (matching the detected CUDA major version), not `mlx-cuda13` or `mlx-cpu`.
The script does not run `uv sync` itself with the wrong extra — it recommends the correct command for the developer to run (or runs the correct one if the script's documented behavior is to auto-run it after confirmation).
