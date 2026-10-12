---
unit: dg1
feature: No-peers-after-timeout discovery diagnostic
priority: P0
---
# Warns once after 30 seconds with zero peers

## Scenario
Start `uv run exo -v` on a machine on a network with no other exo nodes reachable (isolated network segment, or a unique `--namespace` guaranteeing no peers). Let it run for 35 seconds while capturing log output.

## Expected
The captured log output contains exactly one warning-level message mentioning Windows Defender Firewall (or "firewall") and referencing the setup command, emitted between the 30-second and 35-second mark.
</content>
