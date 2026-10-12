---
id: dw1
title: Windows-compatible discovery socket bind
type: feature
dependencies: []
---
# Windows-compatible discovery socket bind

## Goal
Make the custom IPv6 UDP multicast discovery socket in `rust/networking/src/discovery.rs` bind and operate correctly on Windows, so Windows nodes can discover and be discovered by macOS/Linux nodes, without changing the wire protocol.

## Requirements
- `Discovery::new` (`discovery.rs:39-118`) successfully binds the discovery UDP socket on Windows without relying on `SO_REUSEPORT` (which does not exist on Windows; currently gated `#[cfg(unix)]` at `discovery.rs:52-53`).
- Per ADR-3 in `solution.md`: on Windows, do not set `SO_REUSEADDR` either — let `bind()` fail loudly if the port is already taken by another exo instance, rather than emulating Unix reuse semantics that behave unsafely differently on Windows.
- IPv6 multicast group join/leave on the `ff12::e0a1:de89` group (`discovery.rs:18,72-78,91-101`), including scope-id-qualified addressing via `netwatcher`-reported interface indices, works correctly on Windows across multiple active interfaces.
- The `Header`/`Hello`/`WhatsUp` wire format (`discovery.rs:267-339`) is unchanged — a Windows node must successfully discover, and be discovered by, unmodified macOS/Linux nodes.
- Dynamic interface changes (adapter enable/disable, Wi-Fi reconnect) on Windows correctly join/leave the multicast group via the existing `netwatcher`-driven callback (`discovery.rs:59-107`) without requiring an exo restart.

## Constraints
- Follow existing patterns (see AGENTS.md) — this is an additive `cfg`-branch change, not a rewrite.
- Must not modify `Header`, `Hello`, or `WhatsUp` struct layouts or the `MAGIC`/`GROUP` constants (`discovery.rs:18-19`).
- Must not touch `rust/networking/src/swarm.rs` or `rust/networking/src/lib.rs`'s Zenoh config (`lib.rs:23-51`).
- Must not touch the patched zenoh fork (`Cargo.toml:62-89`).
- Full test coverage for all requirements, including explicit multicast join/leave and scope-id tests exercised on real Windows hardware or a Windows CI runner (not compile-check-only, per the Implementation Gotchas noted in `solution.md`).

## Interfaces
Produces the same `Discovered { zid: ZenohId, addr: SocketAddrV6 }` type (`discovery.rs:33-37`) already consumed by `networking::open`'s connect loop in `lib.rs:74-101` — no interface change, this unit is purely an internal socket-setup fix inside `Discovery::new`.
</content>
