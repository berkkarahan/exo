---
id: net1
title: Networking mode & port reference documentation
type: feature
dependencies: []
---
# Networking mode & port reference documentation

## Goal
Produce a standalone, precise reference document explaining exo's three default ports and exactly which of them work under WSL2 default NAT mode versus mirrored networking mode, plus native Windows LAN behavior.

## Requirements
- Create `docs/windows-networking.md` documenting exo's three default ports: API (52415, TCP), Zenoh (52414, TCP), discovery (52413, custom IPv6 UDP multicast on group `ff12::e0a1:de89`), citing `src/exo/main.py:380-484` for the port defaults and `rust/networking/src/discovery.rs:18,46-78` for the discovery mechanism.
- Document native Windows: all three ports behave as on any LAN host (no NAT layer) — Windows Firewall prompts may appear on first run and must be allowed for LAN discovery to work; state this explicitly as a native-Windows caveat.
- Document WSL2 default NAT mode: state explicitly, port by port, which work and which don't — 52415 (API) works via WSL2's automatic `localhost` port-forwarding from the Windows host; 52414 (Zenoh) and 52413 (discovery, UDP multicast) do not reach other LAN machines because the WSL2 instance sits behind a virtual NAT switch and is not on the same L2 multicast domain as the LAN.
- Document WSL2 mirrored networking mode (`.wslconfig` `[wsl2] networkingMode=mirrored`): state that with mirrored mode enabled, the WSL2 instance shares the host's network interfaces directly, so all three ports behave as if the exo process were running natively on the LAN — include the exact `.wslconfig` snippet and note that it requires Windows 11 22H2 or later and a `wsl --shutdown` + restart to take effect.
- Include a single summary table: rows = the three ports, columns = {Native Windows, WSL2 default NAT, WSL2 mirrored mode}, cells = works/does-not-reach-LAN/localhost-only as appropriate.
- Document that this file is referenced by, not duplicated into, `win1`'s and `wsl1`'s documentation.

## Constraints
- Follow existing patterns (see AGENTS.md) — plain Markdown, no build tooling.
- Every port number and discovery-mechanism claim must cite the exact file:line from solution.md's Implementation Context (`src/exo/main.py:380-484`, `rust/networking/src/discovery.rs:18,46-78`) — no invented port numbers or mechanisms.
- Must not describe or modify exo's actual networking code — this unit is documentation only.

## Interfaces
`win1` and `wsl1` link to `docs/windows-networking.md` from their respective setup sections rather than re-describing the port/mode matrix inline.
