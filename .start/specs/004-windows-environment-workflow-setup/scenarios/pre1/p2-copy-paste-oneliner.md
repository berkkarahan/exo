---
unit: pre1
feature: windows-environment-workflow-setup
priority: P2
---
# A copy-pasteable PowerShell one-liner chains all three checks

## Scenario
Locate the PowerShell one-liner code block in `docs/windows-precommit.md` and paste it into a PowerShell 5.1+ prompt.

## Expected
The one-liner runs `uv run basedpyright`, `uv run ruff check`, and `uv run pytest` in sequence, stopping (or clearly reporting) on the first failure rather than silently continuing past it.
The one-liner uses valid PowerShell syntax (e.g., `;` with `$LASTEXITCODE` checks, not raw POSIX `&&`, which PowerShell 5.1 does not support natively).
