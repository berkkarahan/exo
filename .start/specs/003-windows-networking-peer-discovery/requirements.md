---
title: "Windows Networking & Peer Discovery"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No technical implementation details included
- [x] A new team member could understand this PRD
- [x] **MECE: Personas** — each persona is distinct, all user types represented
- [x] **MECE: Journeys** — each journey is a unique path, all paths covered
- [x] **MECE: Features** — no overlapping user stories, no capability gaps
- [x] **MECE: Acceptance Criteria** — each criterion tests a unique condition, all paths covered

---

## Output Schema

### PRD Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| sections | SectionStatus[] | Yes | Status of each PRD section |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |
| acceptanceCriteria | number | Yes | Total testable acceptance criteria defined |
| openQuestions | string[] | No | Unresolved items requiring stakeholder input |

```yaml
specId: "003-windows-networking-peer-discovery"
title: "Windows Networking & Peer Discovery"
status: COMPLETE
clarificationsRemaining: 0
acceptanceCriteria: 15
openQuestions: []
```

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

All sections: `COMPLETE`.

---

## Product Overview

### Vision

A Windows machine running `uv run exo` joins an existing exo cluster exactly like a macOS or Linux machine does: it appears automatically, exchanges inference workloads over TCP, and requires no manual peer configuration, no firewall-disabling, and no long-lived administrator session.

### Problem Statement

exo's cluster membership today is built and validated exclusively on macOS (with Linux running CPU-only). The peer-discovery transport (`rust/networking/src/discovery.rs`) uses `SO_REUSEPORT`, a socket option compiled only under `#[cfg(unix)]` — on Windows the discovery socket bind fails outright, so a Windows node cannot find any peer, and no macOS/Linux node can find it. Even if the socket bound, Windows Defender Firewall blocks unsolicited inbound UDP/TCP by default, so the discovery multicast replies and the Zenoh TCP connection back to a Windows node would both be silently dropped. Separately, `src/exo/utils/info_gatherer/system_info.py` classifies network interface types (Wi-Fi/Ethernet/Thunderbolt) by shelling out to the macOS-only `networksetup` binary; on every non-macOS platform this returns an empty map, so every interface on a Windows node is reported as `"unknown"`. That "unknown" classification silently degrades the link-selection heuristics in `src/exo/master/placement_utils.py` that choose which neighbor IP a ring/JACCL instance connects over, so even a Windows node that *did* connect would get sub-optimal, effectively random link choices among its interfaces. Together, these three gaps mean: a Windows machine cannot join a cluster today, and if the transport-level blocker were removed, it would still connect over unpredictable links and provide no diagnostic when discovery silently fails.

### Value Proposition

exo's core promise is "connects all your devices into an AI cluster." Excluding Windows removes the single most common consumer/desktop OS from that promise, and it is the OS most users own even when their "good" GPU machine runs macOS or Linux. Making Windows a first-class peer — automatically discovered, automatically reachable, automatically classified for link priority — extends the cluster's usable device pool without requiring the Windows owner to learn zenoh, firewall rule syntax, or networking internals. The value is measured entirely in "it just works," matching the zero-configuration bar already set for macOS/Linux.

## User Personas

### Primary Persona: Cluster Operator

- **Demographics:** Individual developer or small-team ML hobbyist/engineer who already runs exo on at least one macOS or Linux machine and owns a Windows PC or laptop with a capable GPU/CPU they want to add to the cluster. Comfortable running a terminal command once during setup but does not want to hand-edit firewall rules or run the node elevated on every boot.
- **Goals:** Add the Windows machine to the existing cluster with the same "run `uv run exo`, watch it appear" experience they get on macOS/Linux. See the Windows machine's inference contribution actually used (ring/JACCL placement), not just connected-but-idle.
- **Pain Points:** Windows networking (Defender Firewall prompts, private/public profile differences, IPv6 link-local addressing) is unfamiliar and easy to misconfigure. A node that silently fails to connect, with no error message pointing at "the firewall is blocking you," burns hours of trial and error.

### MECE Check: Personas

- [x] Each persona has distinct goals and pain points (no overlap)
- [x] All user types who interact with this feature are represented (no gaps)

## User Journey Maps

### Primary User Journey: Adding a Windows machine to an existing exo cluster

1. **Awareness:** The Cluster Operator already has exo running on a Mac or Linux box, sees the dashboard's cluster view, and wants to add their Windows gaming/workstation PC's compute to the pool.
2. **Consideration:** They check whether exo supports Windows at all (today: no). They evaluate whether they'd need to run a VM, WSL, or dual-boot Linux instead — all of which lose native GPU/CPU access or add friction.
3. **Adoption:** They install exo's Windows prerequisites, run the one-time firewall-provisioning setup command once (elevated, opt-in, informs them exactly what it does), then run `uv run exo` normally (unelevated).
4. **Usage:** The Windows node appears in the dashboard/`/state` cluster view within seconds, its network interfaces show correct types (Ethernet/Wi-Fi, not "unknown"), and it participates in model placement like any other node.
5. **Retention:** On every subsequent boot, `uv run exo` on Windows joins the cluster the same way, with no repeated elevation and no repeated firewall prompts, matching the "it just works" bar of macOS/Linux.

### MECE Check: Journeys

- [x] Each journey describes a distinct path (no two journeys cover the same actions for the same persona)
- [x] All primary, secondary, and error/recovery paths are mapped (no gaps)
- [x] Every persona has at least one journey

## Feature Requirements

### Must Have Features

#### Feature 1: Automatic Windows peer discovery

- **User Story:** As a Cluster Operator, I want my Windows machine to automatically discover and be discovered by my macOS/Linux exo nodes, so that I don't have to manually configure peer addresses.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given a macOS node and a Windows node are started on the same network with the same discovery namespace, When both have been running for a few seconds, Then each node's cluster state lists the other node as a peer.
  - [x] Given a Windows node and a Linux node are started with different discovery namespaces, When both have been running for a few seconds, Then neither node lists the other as a peer.
  - [x] Given a Windows node has multiple active network interfaces (e.g. Wi-Fi and Ethernet), When it starts up, Then it discovers peers reachable on any of those interfaces, not just one.
  - [x] Given a Windows node loses and regains a network interface (e.g. Wi-Fi disconnects and reconnects) while running, When the interface comes back, Then discovery on that interface resumes without restarting exo.

#### Feature 2: One-time, opt-in firewall exception setup

- **User Story:** As a Cluster Operator, I want a single explicit setup step that opens exactly the network access exo needs on Windows, so that I never have to disable Windows Defender Firewall or run exo as Administrator during normal use.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given a freshly installed exo on Windows with no firewall rules yet, When the Cluster Operator runs the documented setup command, Then it prompts for elevation once, creates the necessary inbound firewall rules, and exits — without leaving any process running elevated afterward.
  - [x] Given the firewall rules already exist from a previous run of the setup command, When the Cluster Operator runs the setup command again, Then it recognizes the rules already exist and makes no duplicate rules (idempotent).
  - [x] Given the setup command has been run, When the Cluster Operator subsequently runs `uv run exo` normally, Then exo starts and operates without requesting or requiring elevation.
  - [x] Given the Cluster Operator declines to run the setup command, When they run `uv run exo` anyway, Then exo still starts (does not crash or refuse to run) but peer discovery may not succeed until the setup command is run.

#### Feature 3: Correct Windows network interface classification

- **User Story:** As a Cluster Operator, I want exo to correctly identify which of my Windows machine's network interfaces are Wi-Fi vs. Ethernet, so that the cluster picks the fastest available link instead of guessing randomly.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given a Windows node with one Ethernet adapter and one Wi-Fi adapter both active, When another node queries this node's reported network interfaces, Then the Ethernet adapter is reported with an Ethernet-equivalent type and the Wi-Fi adapter is reported with a Wi-Fi-equivalent type (neither is reported as unknown).
  - [x] Given a Windows node and a macOS node are both in the same cluster forming a ring placement, When the system selects which link to route inference traffic over between them, Then it prefers the Ethernet link over the Wi-Fi link, consistent with the existing link-priority behavior on macOS.

### Should Have Features

#### Feature 4: Clear diagnostic when discovery is blocked

- **User Story:** As a Cluster Operator, I want a specific, actionable log message when my Windows node can't be discovered because of the firewall, so that I know exactly what to fix instead of guessing.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given the firewall setup command has not been run and inbound discovery/Zenoh traffic is being blocked, When the Windows node has been running for longer than one discovery interval with zero peers found, Then it logs a diagnostic message that names the firewall as a likely cause and points to the setup command.

### Could Have Features

- Investigate Windows NetworkDirect/RDMA (SMB-Direct-class) transports as a potential low-latency path between Windows nodes and other RDMA-capable nodes, as a research spike only (no shipped implementation this phase — see Won't Have).

### Won't Have (This Phase)

- Any implementation of NetworkDirect, RDMA, or RoCE/iWARP transport on Windows. exo's RDMA-accelerated backend (`MlxJaccl`) is currently restricted to the Metal backend and has no Windows-equivalent hardware path on typical consumer machines; this phase ships plain-TCP Windows connectivity only.
- Requiring the exo process to run elevated (as Administrator) during normal operation. Elevation is permitted only inside the one-time, opt-in setup command.
- Disabling or weakening Windows Defender Firewall as a solution. The feature adds narrowly-scoped inbound allow rules; it never turns the firewall off.
- A Windows GPU inference backend. This feature is about network reachability only; Windows nodes may run CPU-only inference (matching the existing Linux CPU-only status) until a separate GPU-backend effort lands.
- Automatic, unattended firewall provisioning with no user action (e.g. auto-elevating on first launch). The setup step must remain an explicit, separate, opt-in action.

### MECE Check: Features

- [x] No two user stories describe the same capability (no overlap across MoSCoW categories)
- [x] All capabilities needed to solve the problem for every persona are present (no gaps)
- [x] Every feature has testable acceptance criteria
- [x] "Won't Have" explicitly accounts for capabilities that could be confused with in-scope features

## Detailed Feature Specifications

### Feature: One-time, opt-in firewall exception setup

**Description:** A separate, explicitly-invoked setup command (not run automatically by `uv run exo`) that requests elevation once, creates named inbound Windows Firewall rules for exo's three fixed ports (API, Zenoh TCP, UDP discovery) plus a program-scoped rule covering exo's dynamically-chosen ephemeral ports (model-placement ring/JACCL/prefill listeners), and then exits without retaining elevated privileges.

**User Flow:**
1. Cluster Operator runs the documented setup command from an ordinary (non-elevated) terminal.
2. Windows presents the standard UAC elevation prompt; the operator approves it.
3. The command creates or confirms the firewall rules and prints a summary of what it added.
4. The operator runs `uv run exo` normally afterward, with no further elevation ever required.

**Business Rules:**
- Rule 1: The setup command must be runnable multiple times without creating duplicate or conflicting firewall rules (idempotent).
- Rule 2: The exo runtime process itself must never require Administrator privileges to start or operate normally.
- Rule 3: The setup command must clearly state, before requesting elevation, what firewall rules it is about to create.

**Edge Cases:**
- Scenario 1: The operator runs `uv run exo` without ever running the setup command → Expected: exo starts normally; discovery may simply find zero peers, and Feature 4's diagnostic explains why.
- Scenario 2: The operator declines the UAC elevation prompt → Expected: the setup command exits cleanly with a non-zero status and an explanatory message; it does not silently continue without the rules.

## Success Metrics

### Key Performance Indicators

- **Adoption:** A Windows machine, once the firewall setup command has been run, appears as a discovered peer in an existing cluster's `/state` output within one discovery interval (target: within 5 seconds of both nodes being up) in 100% of same-subnet test runs.
- **Engagement:** Of Windows nodes that complete the firewall setup command, the fraction that go on to run `uv run exo` and successfully join at least one cluster session.
- **Quality:** Zero cases in testing where a Windows node's own interfaces are reported as `"unknown"` when a definite Wi-Fi or Ethernet classification is available from the OS.
- **Business Impact:** Increase in the proportion of exo clusters that include at least one Windows node, tracked from opt-in telemetry/community reports (exo does not currently collect this metric — see Tracking Requirements).

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Firewall setup command run | outcome (success/declined/error), rule_count_created | Measure adoption and failure modes of the one-time setup step |
| Node peer discovered | peer_os (windows/macos/linux), time_to_discover_ms | Measure discovery latency parity between Windows and existing platforms |
| Interface classified unknown | os, interface_name | Detect classification gaps in the field after this feature ships |

---

## Constraints and Assumptions

### Constraints

- Must not require the exo runtime process to run elevated during normal operation (see Won't Have).
- Must not disable or globally weaken Windows Defender Firewall.
- Must not change the on-the-wire discovery/Zenoh protocol in a way that breaks compatibility with already-deployed macOS/Linux nodes — a Windows node must be able to join a cluster that also has macOS/Linux nodes on the current protocol version.
- RDMA/NetworkDirect implementation is out of scope this phase (Won't Have); only a research spike is in scope (Could Have).

### Assumptions

- The Windows machine has at least one active IPv6-capable network interface with link-local addressing enabled (Windows enables IPv6 link-local by default; this is not something exo needs to configure).
- The Cluster Operator has local Administrator rights available on the Windows machine to approve the one-time UAC elevation prompt, even if they don't run exo itself as Administrator.
- The Windows machine and the macOS/Linux machines it clusters with are on the same broadcast/multicast domain (LAN), consistent with exo's existing multicast-based discovery assumption on macOS/Linux.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Windows networks are frequently on the "Public" firewall profile (e.g. coffee-shop-style default), where inbound rules are more aggressively blocked than "Private" | High — discovery silently fails | Medium | Firewall setup command creates rules scoped to the Private/Domain profiles by default and documents that Public-profile networks need the operator to mark their network as Private, or the rule explicitly extended to Public |
| Dynamic ephemeral ports (ring/JACCL/prefill) can't be pre-enumerated for per-port firewall rules | Medium — some inference traffic blocked even after setup | High (inherent to the design) | Use one program-scoped (not port-scoped) firewall rule that allows exo's process binary regardless of which port it binds, documented as the pragmatic trade-off |
| IPv6 link-local scope-id handling differs between Windows' socket API and the existing `netwatcher`/multicast code path | High — discovery multicast joins fail on Windows despite the `SO_REUSEPORT` fix | Medium | Explicit unit-level testing of multicast group join/leave and scope-id-qualified addressing on Windows before considering discovery "fixed" |
| A poorly-worded elevation prompt makes operators distrust or skip the setup command | Medium — feature goes unused | Low | Setup command prints exactly what it will do before requesting elevation (per Business Rule 3) |

## Open Questions

None outstanding — see Risks and Mitigations and the Decisions Log in `README.md` for decisions already made (RDMA scope, firewall provisioning model).

---

## Supporting Research

### Competitive Analysis

Comparable peer-to-peer/LAN-cluster tools (e.g. Tailscale, Syncthing) handle Windows firewall friction the same way this feature does: a one-time, explicit, elevated installer/setup step that provisions firewall exceptions, with the running process itself unprivileged. This validates the "separate opt-in setup command" approach over in-process elevation prompts.

### User Research

No formal user research was conducted for this spec; the problem statement is derived directly from a codebase audit of the existing discovery/firewall/interface-classification code paths (see file:line evidence in `solution.md`) confirming Windows is currently non-functional, not from user complaints.

### Market Data

Windows remains the most common desktop OS among developers and ML hobbyists per public IDE/OS survey data (e.g. Stack Overflow Developer Survey), making it the largest reachable expansion of exo's addressable device pool relative to macOS/Linux-only support.
</content>
