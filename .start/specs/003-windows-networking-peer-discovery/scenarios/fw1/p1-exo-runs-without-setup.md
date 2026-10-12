---
unit: fw1
feature: Windows firewall setup CLI
priority: P1
---
# exo starts normally even if setup was never run

## Scenario
On a fresh Windows machine where `exo-setup-firewall` has never been run, run `uv run exo`.

## Expected
The process starts successfully and `GET http://localhost:52415/state` returns HTTP 200 with this node's own ID present in `topology.nodes`.
No elevation prompt appears at any point during `uv run exo`'s startup or normal operation.
</content>
