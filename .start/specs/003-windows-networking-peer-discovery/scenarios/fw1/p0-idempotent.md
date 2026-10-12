---
unit: fw1
feature: Windows firewall setup CLI
priority: P0
---
# Setup CLI is idempotent on re-run

## Scenario
With the 4 exo firewall rules already present (from a prior run of `uv run exo-setup-firewall`), run `uv run exo-setup-firewall` a second time, approving elevation.

## Expected
The command exits with status code 0.
Running `netsh advfirewall firewall show rule name=all | findstr /I exo` afterward still shows exactly 4 exo-related rules — no duplicates were created.
</content>
