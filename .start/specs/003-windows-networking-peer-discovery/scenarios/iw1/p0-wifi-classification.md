---
unit: iw1
feature: Windows network interface classification
priority: P0
---
# Windows Wi-Fi adapter classifies correctly

## Scenario
On a Windows machine with an active Wi-Fi adapter, run `uv run exo`, wait 10 seconds, then query `GET http://localhost:52415/state`.

## Expected
Response HTTP 200.
`node_network[<this node's id>].interfaces` contains an entry whose `ip_address` matches the Wi-Fi adapter's IP and whose `interface_type` is `"wifi"`.
</content>
