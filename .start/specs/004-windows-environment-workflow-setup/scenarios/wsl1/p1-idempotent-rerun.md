---
unit: wsl1
feature: windows-environment-workflow-setup
priority: P1
---
# Re-running setup.sh after success is a clean no-op

## Scenario
After a successful first run of `scripts/wsl2/setup.sh` (all prerequisites present), run `scripts/wsl2/setup.sh` again.

## Expected
The script reports every prerequisite (Python 3.13, uv, Node.js, Rust) as already present.
The script exits with status 0 and performs no installs or other side effects on this second run.
