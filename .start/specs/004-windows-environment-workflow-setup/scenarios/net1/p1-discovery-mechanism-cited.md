---
unit: net1
feature: windows-environment-workflow-setup
priority: P1
---
# Discovery mechanism is described accurately

## Scenario
Read the paragraph in `docs/windows-networking.md` explaining why WSL2 default NAT mode blocks peer discovery.

## Expected
The document states that exo peer discovery uses IPv6 UDP multicast (naming the mechanism, not just "networking").
The document explains that a WSL2 instance under default NAT mode sits behind a virtual switch and is not on the same L2/multicast domain as the physical LAN, which is why the discovery port does not reach other LAN machines.
No port number or mechanism claim in this paragraph contradicts the summary table from the P0 scenario.
