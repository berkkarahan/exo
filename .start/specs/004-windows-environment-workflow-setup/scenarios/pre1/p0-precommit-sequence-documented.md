---
unit: pre1
feature: windows-environment-workflow-setup
priority: P0
---
# Non-Nix pre-commit sequence is documented and runnable

## Scenario
Open `docs/windows-precommit.md` and, on a machine with `uv` installed and dependencies synced, run each documented command in order: `uv run basedpyright`, `uv run ruff check`, `uv run pytest`.

## Expected
`docs/windows-precommit.md` lists exactly these three commands (matching AGENTS.md's documented commands verbatim) as the Windows pre-commit sequence.
Each command is runnable as written (correct flags, no invented flags) and produces a pass/fail result consistent with running the same command on macOS/Linux.
