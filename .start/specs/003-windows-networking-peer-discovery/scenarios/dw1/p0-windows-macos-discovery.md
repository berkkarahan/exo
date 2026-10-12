---
unit: dw1
feature: Windows-compatible discovery socket bind
priority: P0
---
# Windows node and macOS node discover each other

## Scenario
Start `uv run exo` on a Windows machine and `uv run exo` on a macOS machine, both on the same LAN with default (matching) `--namespace`, `--zenoh-port`, and `--discovery-port`. Wait 10 seconds. On each machine, run `curl http://localhost:52415/state`.

## Expected
Both `GET /state` responses return HTTP 200.
The Windows node's response has the macOS node's node ID present under `topology.nodes`.
The macOS node's response has the Windows node's node ID present under `topology.nodes`.
Discovery succeeds within 10 seconds of both processes being up (well within 5 announce cycles at 1/sec).
</content>
