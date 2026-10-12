---
unit: net1
feature: windows-environment-workflow-setup
priority: P1
---
# .wslconfig mirrored networking mode snippet is present and correct

## Scenario
Search `docs/windows-networking.md` for a `.wslconfig` code block.

## Expected
A code block shows a `[wsl2]` section with `networkingMode=mirrored`.
The surrounding text states this file lives at `%UserProfile%\.wslconfig` on the Windows host and that a `wsl --shutdown` (or restart) is required for the setting to take effect.
The text states that mirrored mode requires Windows 11 22H2 or later.
