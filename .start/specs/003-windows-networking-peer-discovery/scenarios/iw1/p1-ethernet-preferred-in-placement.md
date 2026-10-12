---
unit: iw1
feature: Windows network interface classification
priority: P1
---
# Ethernet is preferred over Wi-Fi for ring placement on Windows

## Scenario
Connect a Windows node (with both Ethernet and Wi-Fi active, both reachable by the peer) to a macOS or Linux peer forming a 2-node ring-eligible topology. Create a small model instance via `POST http://localhost:52415/instance` using an `MlxRing` placement from `GET /instance/previews`. Inspect the resulting instance's `hosts_by_node` entries (via `GET /instance/{instance_id}` or `/state`).

## Expected
The host IP used for the Windows node's neighbor connection matches the Windows node's Ethernet adapter IP, not its Wi-Fi adapter IP — matching the existing macOS-only Ethernet-over-Wi-Fi priority behavior in `find_ip_prioritised`.
</content>
