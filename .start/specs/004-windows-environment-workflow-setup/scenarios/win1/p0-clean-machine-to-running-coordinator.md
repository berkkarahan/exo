---
unit: win1
feature: windows-environment-workflow-setup
priority: P0
---
# Clean Windows 11 machine reaches a running coordinator within the documented time budget

## Scenario
Starting from a clean Windows 11 machine with none of the prerequisites installed, follow `docs/windows-setup.md`'s native Windows section step by step: run `scripts\windows\setup.ps1` (with `-InstallMissing` to auto-resolve any gaps), build the dashboard, run `uv sync`, then `uv run exo`.

## Expected
`http://localhost:52415` is reachable in a browser and renders the exo dashboard within the time budget stated in the documentation (dependency install dominates; a few minutes after `uv sync` completes, per solution.md's Deployment View).
`curl http://localhost:52415/v1/models` returns an HTTP response (not a connection error).
No step in the documented sequence required a command not listed in `docs/windows-setup.md` or `README.md`.
