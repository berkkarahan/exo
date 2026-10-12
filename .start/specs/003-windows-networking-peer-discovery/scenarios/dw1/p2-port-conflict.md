---
unit: dw1
feature: Windows-compatible discovery socket bind
priority: P2
---
# Duplicate discovery port bind fails loudly on Windows

## Scenario
On a Windows machine, start `uv run exo --discovery-port 52413`. While it is still running, in a second terminal start a second `uv run exo --discovery-port 52413 --api-port 52416` (different API port to avoid that conflict masking this test).

## Expected
The second process fails to start and exits with a non-zero status, printing an error indicating the discovery UDP port is already in use.
The first process continues running unaffected.
</content>
