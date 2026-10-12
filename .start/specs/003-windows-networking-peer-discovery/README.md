# Specification: 003-windows-networking-peer-discovery

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-11 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-09-11 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | PRD complete, zero `[NEEDS CLARIFICATION]` markers, 4 MoSCoW categories addressed, Gherkin acceptance criteria for all Must Have / Should Have features |
| solution.md | completed | SDD complete, grounded in `discovery.rs`, `lib.rs`, `swarm.rs`, `networking.rs`, `system_info.py`, `thunderbolt.py`, `main.py`, `placement.py`, `placement_utils.py`, `topology.py`, `ports.py`, `topics.py`, `router.py`, `Cargo.toml`, `pyproject.toml`; 4 ADRs confirmed |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Factory |
| **Status** | completed |

For Incremental tier, see `plan/README.md`.
For Factory tier, see `manifest.md`, `units/`, `scenarios/`.
For Direct tier, no decomposition artifacts are produced — implement-direct reads requirements.md and solution.md directly.

Factory decomposition produced 5 units (`pe1`, `dw1`, `iw1`, `fw1`, `dg1`) — 4 run in parallel (`pe1`, `dw1`, `iw1`, `fw1`, none share dependencies), followed sequentially by `dg1` (depends on `dw1`). Each unit has 3-5 scenarios with at least one P0, testing observable behavior exclusively through `uv run exo`'s HTTP API (`GET /state`, `POST /instance`) and the new `exo-setup-firewall` CLI's process exit codes / `netsh advfirewall` output — never internal Rust function names, per `scenario-guide.md`.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-11 | Classified as Factory — multiple distinct user-facing capabilities (Windows peer discovery, firewall exception provisioning, Windows interface classification) across independent Rust and Python surfaces; parallel unit work is explicit. | Classifier rationale verbatim per task specification. |
| 2026-09-11 | Firewall provisioning is a separate, opt-in, idempotent elevated setup command (`exo-setup-firewall`), not an in-process elevation prompt inside `uv run exo`. | The exo runtime process must never require Administrator privileges to start or operate normally (epic constraint). A standalone, review-before-elevate command mirrors the proven approach used by comparable LAN-cluster tools (Tailscale, Syncthing) and avoids surprising operators with UAC prompts on every launch. See `solution.md` ADR-1. |
| 2026-09-11 | NetworkDirect/RDMA is out of scope this phase; only a Could-Have research spike is planned, with plain TCP as the supported Windows transport. | `placement.py:51-54` gates `InstanceMeta.MlxJaccl` to `Backend.MlxMetal` only, and `placement.py:200-219` requires an RDMA cycle with RDMA control enabled on every node — a Windows/mixed cluster has no path to satisfy this today, and consumer Windows hardware has no Thunderbolt-RDMA equivalent (NetworkDirect targets RoCE/iWARP NICs uncommon outside datacenter/workstation-class hardware). Shipping a partial RDMA path this phase would create false expectations. See `solution.md` ADR-2 and `requirements.md` Won't Have. |
| 2026-09-11 | Windows `SO_REUSEPORT` gap (`discovery.rs:52-53`) is fixed by omitting `SO_REUSEADDR` on Windows entirely and letting `bind()` fail loudly on port conflict, rather than emulating Unix reuse semantics. | Windows `SO_REUSEADDR` has materially different (weaker) semantics than Unix and can silently let an unrelated process steal a bound UDP port — worse than exo's actual single-socket-per-node need. Failing loudly on conflict is simpler, safer, and more debuggable. See `solution.md` ADR-3. |
| 2026-09-11 | Windows interface classification (replacing the macOS-only `networksetup` shell-out in `system_info.py:59-90`) sources adapter media type from the Windows WMI subsystem (`Win32_NetworkAdapter`), keyed by `NetConnectionID` to match `psutil.net_if_addrs()` interface names. | No Windows equivalent of `networksetup -listallhardwareports` exists; WMI is the standard, stable way to query adapter media type on Windows without a heavyweight new dependency. Leaving interfaces `"unknown"` (today's behavior on every non-macOS platform) silently degrades link prioritization in `placement_utils.py:find_ip_prioritised`, which is a real performance bug, not cosmetic. See `solution.md` ADR-4. |

## Context

Epic 3: Windows networking and peer discovery. exo's peer-to-peer control plane (Zenoh TCP transport plus a custom IPv6 UDP multicast discovery protocol) is already largely cross-platform — built on the portable `netwatcher` crate and vanilla Zenoh TCP — but three narrow, nameable gaps currently make Windows completely non-functional as a cluster peer: (1) `rust/networking/src/discovery.rs:52-53`'s `#[cfg(unix)]`-gated `SO_REUSEPORT` call, which is the single most Windows-specific line in the Rust tree; (2) `src/exo/utils/info_gatherer/system_info.py:59-90`'s macOS-only `networksetup` shell-out, which leaves every Windows network interface classified as `"unknown"` and silently degrades link-selection heuristics in `src/exo/master/placement_utils.py`; and (3) the complete absence of any Windows Defender Firewall provisioning story for exo's 3 fixed ports (API 52415, Zenoh TCP 52414, discovery UDP 52413, all defined in `src/exo/main.py:380-487`) plus its dynamically-chosen ephemeral tensor/prefill ports.

This spec's `solution.md` intentionally rejects a networking rewrite in favor of four small, independently-shippable, additive patches (per the task's DESIGN GUIDANCE), each isolated to its own factory unit: `pe1` (Windows `uv` package resolution), `dw1` (Windows-safe discovery socket bind), `iw1` (Windows interface classification via WMI), `fw1` (standalone, opt-in, idempotent firewall setup CLI), and `dg1` (a "no peers after 30s" diagnostic warning, dependent on `dw1` being merged first so the diagnostic is exercised against working Windows discovery). RDMA/NetworkDirect is explicitly deferred to a future research spike (Could Have in `requirements.md`), and the exo runtime process is designed to never require elevated privileges at runtime — elevation is confined entirely to the one-time `exo-setup-firewall` setup command.

---
*This file is managed by the specify-meta skill.*
</content>
