---
unit: meta1
feature: windows-environment-workflow-setup
priority: P0
---
# README.md gains a Windows section without disturbing existing content

## Scenario
Open `README.md` and locate the `### Run from Source (Windows)` heading; diff the file against its pre-unit state for the existing `### Run from Source (macOS)` and `### Run from Source (Linux)` sections.

## Expected
A `### Run from Source (Windows)` heading exists, positioned after `### Run from Source (Linux)` and before the `### macOS App` section (or the next existing `###` heading), under the `## Quick Start` heading.
The existing macOS and Linux sections' text is byte-identical to before this unit's change (no reordering, no incidental edits).
