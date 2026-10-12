---
unit: dw1
feature: Windows-compatible discovery socket bind
priority: P0
---
# Mismatched namespace prevents discovery on Windows

## Scenario
Start `uv run exo --namespace clusterA` on a Windows machine and `uv run exo --namespace clusterB` on a macOS or Linux machine on the same LAN. Wait 10 seconds. Query `GET http://localhost:52415/state` on both.

## Expected
Neither node's `topology.nodes` list includes the other node's ID.
No error or crash occurs on either node — both remain running normally with only themselves in `topology.nodes`.
</content>
