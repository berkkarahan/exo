---
unit: net1
feature: windows-environment-workflow-setup
priority: P0
---
# Networking reference doc exists with a complete port/mode matrix

## Scenario
Open `docs/windows-networking.md` and locate the summary table covering exo's three default ports across native Windows, WSL2 default NAT mode, and WSL2 mirrored networking mode.

## Expected
The document exists at `docs/windows-networking.md` and lists all three ports by number and protocol: 52415/TCP (API), 52414/TCP (Zenoh), 52413/UDP (discovery, IPv6 multicast).
The summary table has exactly three rows (one per port) and three columns (Native Windows, WSL2 default NAT, WSL2 mirrored mode), with an unambiguous per-cell status (works / localhost-only / does-not-reach-LAN or equivalent wording).
The discovery port row states plainly that it does not reach other LAN machines under WSL2 default NAT mode.
