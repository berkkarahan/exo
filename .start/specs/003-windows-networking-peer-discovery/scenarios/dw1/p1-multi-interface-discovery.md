---
unit: dw1
feature: Windows-compatible discovery socket bind
priority: P1
---
# Discovery works across multiple active Windows interfaces

## Scenario
On a Windows machine with both an active Ethernet adapter and an active Wi-Fi adapter connected to the same LAN as a macOS peer node, start `uv run exo`. Wait 10 seconds and query `GET /state`. Then disable the Ethernet adapter (leaving only Wi-Fi active), restart `uv run exo`, wait 10 seconds, and query `GET /state` again.

## Expected
In the first run (both adapters active), the macOS peer's node ID appears in `topology.nodes`.
In the second run (Wi-Fi only), the macOS peer's node ID also appears in `topology.nodes` — confirming discovery is not hard-coded to a single interface.
</content>
