---
id: dg1
title: No-peers-after-timeout discovery diagnostic
type: feature
dependencies: [dw1]
---
# No-peers-after-timeout discovery diagnostic

## Goal
Log a single, clear warning when a node has been running for more than 30 seconds with zero discovered peers, naming Windows Defender Firewall as a likely cause and pointing at the `exo-setup-firewall` setup command, so operators get an actionable signal instead of silent failure.

## Requirements
- `Router` (`src/exo/routing/router.py`) tracks whether any `FromSwarm.Connection(connected=True)` event (existing case handled at `router.py:201-210`) has occurred since startup.
- If zero peers have connected within 30 seconds of `Router.run` starting, exactly one `logger.warning(...)` is emitted naming the firewall as a likely cause and referencing the setup command from unit `fw1`.
- Once any peer has ever connected, the warning permanently disarms for that node's lifetime — it never fires after a successful connection, and never fires more than once total per node run.
- The diagnostic is platform-agnostic (not gated to `win32`) — it is a generic "discovery appears stuck" signal useful on any OS, not a Windows-specific code path.

## Constraints
- Follow existing patterns (see AGENTS.md) — use the existing `loguru`-based `logger` already imported in `router.py`/`main.py`; no new logging framework or dependency.
- Must not change discovery control flow, retries, or fail the node — this is purely an additive, non-fatal diagnostic.
- Full test coverage for all requirements.

## Interfaces
Consumes the existing `FromSwarm.Connection` events already flowing through `Router._networking_recv` (`router.py:186-219`) — defines no new interface, adds one internal timer/state check inside `Router`.
</content>
