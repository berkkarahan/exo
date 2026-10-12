---
unit: dg1
feature: No-peers-after-timeout discovery diagnostic
priority: P1
---
# Warning fires exactly once, not repeatedly

## Scenario
Start `uv run exo -v` on an isolated network with no reachable peers and let it run for 90 seconds while capturing log output.

## Expected
The captured log output contains exactly one occurrence of the "likely firewall" warning message across the full 90-second run, not one per checkpoint interval.
</content>
