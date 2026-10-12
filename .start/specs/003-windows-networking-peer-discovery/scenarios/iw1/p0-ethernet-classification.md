---
unit: iw1
feature: Windows network interface classification
priority: P0
---
# Windows Ethernet adapter classifies correctly

## Scenario
On a Windows machine with an active Ethernet adapter and connected to at least one peer node, run `uv run exo`, wait 10 seconds, then query `GET http://localhost:52415/state`.

## Expected
Response HTTP 200.
`node_network[<this node's id>].interfaces` contains an entry whose `ip_address` matches the Ethernet adapter's IP and whose `interface_type` is `"ethernet"`.
No entry for that adapter reports `interface_type` as `"unknown"`.
</content>
