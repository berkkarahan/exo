---
unit: meta1
feature: windows-environment-workflow-setup
priority: P2
---
# Existing in-page anchors remain valid after the edit

## Scenario
Check that GitHub-style anchor links to the existing macOS and Linux sections (e.g., `README.md#run-from-source-macos`, `README.md#run-from-source-linux`) still resolve to the correct headings after this unit's edit.

## Expected
Both pre-existing anchors resolve to their original headings, unchanged in wording and heading level.
The new `### Run from Source (Windows)` heading produces its own new anchor (e.g., `#run-from-source-windows`) without colliding with any existing anchor in the document.
