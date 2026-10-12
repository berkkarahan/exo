---
unit: wsl1
feature: windows-environment-workflow-setup
priority: P1
---
# setup.sh recommends the CPU extra when no NVIDIA GPU is detected

## Scenario
Inside a WSL2 Ubuntu distribution with no `nvidia-smi` binary present (no GPU passthrough configured), run `scripts/wsl2/setup.sh`.

## Expected
The script's output recommends `uv sync --extra mlx-cpu` rather than a CUDA extra.
The script's output does not error out or block on the absence of a GPU — CPU-only is treated as a valid, supported configuration.
