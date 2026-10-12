---
unit: win1
feature: windows-environment-workflow-setup
priority: P1
---
# setup.ps1 -InstallMissing invokes winget for each missing prerequisite

## Scenario
On a machine missing uv, run `scripts\windows\setup.ps1 -InstallMissing`.

## Expected
The script invokes `winget install --id astral-sh.uv -e` (or the current correct winget id for uv) automatically.
After the script completes, re-running `scripts\windows\setup.ps1` (without `-InstallMissing`) reports uv as present.
