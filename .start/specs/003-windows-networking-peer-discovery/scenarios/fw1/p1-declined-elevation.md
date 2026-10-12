---
unit: fw1
feature: Windows firewall setup CLI
priority: P1
---
# Declining elevation aborts cleanly

## Scenario
Run `uv run exo-setup-firewall` and click "No"/cancel on the UAC elevation prompt.

## Expected
The command process exits with a non-zero status code.
The printed output states that elevation was required and was not granted.
Running `netsh advfirewall firewall show rule name=all | findstr /I exo` afterward shows zero exo-related rules were created by this run.
</content>
