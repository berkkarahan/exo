---
unit: fw1
feature: Windows firewall setup CLI
priority: P0
---
# Setup CLI creates exactly 4 named firewall rules

## Scenario
On a Windows machine with no pre-existing exo firewall rules, from an ordinary (non-elevated) terminal run `uv run exo-setup-firewall` and approve the UAC elevation prompt. Afterward, from any terminal run `netsh advfirewall firewall show rule name=all | findstr /I exo`.

## Expected
The setup command exits with status code 0.
The `netsh` output lists exactly 4 rules whose names reference exo: one TCP rule for port 52415 (API), one TCP rule for port 52414 (Zenoh), one UDP rule for port 52413 (discovery), and one program-scoped rule referencing the exo interpreter/binary path.
No elevated process remains running after the command exits (verify via Task Manager or `Get-Process` showing no lingering elevated exo-setup-firewall process).
</content>
