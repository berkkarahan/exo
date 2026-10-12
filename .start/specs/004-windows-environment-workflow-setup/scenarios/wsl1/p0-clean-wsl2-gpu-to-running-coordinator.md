---
unit: wsl1
feature: windows-environment-workflow-setup
priority: P0
---
# Clean WSL2 Ubuntu machine with an NVIDIA GPU reaches a running coordinator reachable from Windows

## Scenario
Starting from a clean WSL2 Ubuntu distribution on a Windows host with an NVIDIA GPU and current WSL2 NVIDIA driver installed, follow the WSL2 setup documentation: run `scripts/wsl2/setup.sh`, build the dashboard, run the recommended `uv sync --extra mlx-cudaNN` command, then `uv run exo`.

## Expected
From a browser on the Windows host (not inside WSL2), `http://localhost:52415` is reachable and renders the exo dashboard within the documented time budget.
`curl http://localhost:52415/v1/models` (run from either the Windows host or inside WSL2) returns an HTTP response.
No step in the documented sequence required a command not listed in the WSL2 setup documentation.
