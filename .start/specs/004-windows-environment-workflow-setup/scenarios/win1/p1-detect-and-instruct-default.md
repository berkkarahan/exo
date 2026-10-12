---
unit: win1
feature: windows-environment-workflow-setup
priority: P1
---
# setup.ps1 detects a missing prerequisite and only instructs by default

## Scenario
On a machine missing Node.js, run `scripts\windows\setup.ps1` without the `-InstallMissing` switch.

## Expected
The script reports Node.js as missing and prints the exact `winget install --id <id> -e` command the developer would need to run.
The script does not itself invoke `winget install` or otherwise modify the system when `-InstallMissing` is not passed.
The script exits with a non-zero status (or otherwise clearly signals incomplete setup) rather than silently proceeding as if all prerequisites were present.
