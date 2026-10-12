---
unit: meta1
feature: windows-environment-workflow-setup
priority: P1
---
# New section links to all four supporting documents

## Scenario
Inspect the Markdown links inside the new `### Run from Source (Windows)` section.

## Expected
The section contains a working relative Markdown link to each of: `docs/windows-setup.md`, the WSL2 setup documentation, `docs/windows-networking.md`, and `docs/windows-precommit.md`.
Each linked file exists on disk at the path referenced (no broken links to not-yet-created files).
