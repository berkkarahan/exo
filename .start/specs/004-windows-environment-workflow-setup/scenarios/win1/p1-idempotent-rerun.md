---
unit: win1
feature: windows-environment-workflow-setup
priority: P1
---
# Re-running setup.ps1 after success is a clean no-op

## Scenario
After a successful first run of `scripts\windows\setup.ps1 -InstallMissing` (all prerequisites installed), run `scripts\windows\setup.ps1` again (without `-InstallMissing`).

## Expected
The script reports every prerequisite (Python 3.13, uv, Node.js, Rust/MSVC) as already present.
The script exits with status 0 and performs no installs, file writes, or other side effects on this second run.
