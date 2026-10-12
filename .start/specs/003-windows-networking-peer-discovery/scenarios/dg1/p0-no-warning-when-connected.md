---
unit: dg1
feature: No-peers-after-timeout discovery diagnostic
priority: P0
---
# No warning fires once a peer has connected

## Scenario
Start two `uv run exo -v` nodes with matching namespaces on the same LAN so they discover each other within the first 10 seconds. Let both run for 40 seconds total while capturing log output.

## Expected
Neither node's captured log output contains the "likely firewall" warning message at any point during the 40-second run.
</content>
