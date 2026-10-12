---
unit: iw1
feature: Windows network interface classification
priority: P2
---
# Unrecognized Windows adapter does not crash enumeration

## Scenario
On a Windows machine with a virtual adapter active (e.g. a VPN TAP/TUN adapter or Hyper-V virtual switch adapter) in addition to a physical Ethernet adapter, run `uv run exo`, wait 10 seconds, then query `GET http://localhost:52415/state`.

## Expected
Response HTTP 200 — the node starts and reports state normally despite the unrecognized adapter being present.
The physical Ethernet adapter still reports `interface_type: "ethernet"`.
The virtual adapter reports `interface_type: "unknown"` rather than causing an exception or missing entry.
</content>
