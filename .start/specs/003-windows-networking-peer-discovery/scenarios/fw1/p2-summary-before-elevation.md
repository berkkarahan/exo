---
unit: fw1
feature: Windows firewall setup CLI
priority: P2
---
# Setup CLI explains itself before requesting elevation

## Scenario
Run `uv run exo-setup-firewall` and capture stdout output printed prior to the UAC elevation prompt appearing (e.g. by piping to a log file before the prompt is triggered, or observing console output timing).

## Expected
Before the elevation prompt is shown, the console output names all 4 rules that will be created (ports 52415/TCP, 52414/TCP, 52413/UDP, and the program-scoped rule), so the operator can review the request before approving it.
</content>
