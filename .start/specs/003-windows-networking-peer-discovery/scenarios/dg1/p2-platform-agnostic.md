---
unit: dg1
feature: No-peers-after-timeout discovery diagnostic
priority: P2
---
# Diagnostic also fires on non-Windows platforms

## Scenario
Start `uv run exo -v` on a macOS or Linux machine on an isolated network with no reachable peers and let it run for 35 seconds while capturing log output.

## Expected
The same "likely firewall" warning message fires around the 30-second mark on macOS/Linux exactly as it would on Windows, confirming the diagnostic is a generic discovery-health check rather than gated to `win32`.
</content>
