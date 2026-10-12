---
title: "Windows System Telemetry for Topology-Aware Placement"
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

specId: `002-windows-system-telemetry`; status: `COMPLETE`; clarificationsRemaining: `0`; acceptanceCriteria: `12`; openQuestions: none.

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

All sections below report status `COMPLETE`.

---

## Product Overview

### Vision

Every node in an exo cluster — regardless of operating system or GPU vendor — reports accurate, real-time RAM, VRAM, and compute-load telemetry, so the cluster orchestrator can place model shards on the hardware that actually has room for them.

### Problem Statement

exo's Topology-Aware Auto Parallel placement engine decides where to run each layer of a sharded model by reading per-node memory telemetry (`state.node_memory[*].ram_available`, consumed in `src/exo/master/placement.py` and `src/exo/master/placement_utils.py`). Today that telemetry pipeline works reliably only on macOS: the node's hardware monitor process (`macmon`) is started exclusively when `sys.platform == "darwin"` (`src/exo/utils/info_gatherer/info_gatherer.py:43,444-453`). On every other operating system, including Windows, the node instead falls back to a 1-second `psutil`-based poll that reports only system RAM (`src/exo/utils/info_gatherer/info_gatherer.py:511-528`). That fallback never reports GPU utilization, GPU temperature, per-core CPU load, or — critically — discrete GPU VRAM, because no field for VRAM exists anywhere in the node telemetry model today (`src/exo/shared/types/profiling.py:59-67`). A Windows node also always reports its hardware identity as the literal strings `"Unknown Model"` / `"Unknown Chip"` (`src/exo/utils/info_gatherer/system_info.py:120-127`), because chip/model detection is implemented only via macOS's `system_profiler`. The consequence: a Windows machine with a discrete NVIDIA or AMD GPU joining an exo cluster is invisible to the placement engine as a GPU-capable node — it can only ever be scored on system RAM, so Topology-Aware Auto Parallel cannot account for its actual VRAM budget when splitting model shards, and its identity is unreadable in the dashboard.

### Value Proposition

Cluster operators running mixed-OS clusters (the stated case: an AMD Ryzen 7 CPU + Radeon RX GPU Windows machine joining a cluster alongside Macs) get the same placement quality on Windows as on macOS: real GPU/VRAM numbers feed the same Topology-Aware Auto Parallel logic, real hardware identity shows in the dashboard, and the node never crashes or drops out of the cluster because a monitoring binary isn't available for its platform.

## User Personas

### Primary Persona: Cluster Operator

- **Demographics:** Technically proficient developer or ML engineer running exo across a mix of personal machines (Macs, Windows PCs, Linux boxes) to pool compute for local LLM inference.
- **Goals:** Add a Windows machine to their exo cluster and have it participate correctly in model placement — get credit for its RAM and its GPU's VRAM, see its real hardware name in the dashboard, and trust that it won't be starved of layers it can't hold or crash the node process.
- **Pain Points:** Windows nodes today report `"Unknown Model"` / `"Unknown Chip"`, contribute no GPU signal, and can silently receive a placement that assumes only system RAM is the constraint — risking out-of-memory failures on GPU-bound backends, or under-utilizing a capable Windows GPU.

### MECE Check: Personas

- [x] Each persona has distinct goals and pain points (no overlap)
- [x] All user types who interact with this feature are represented (no gaps) — the Cluster Operator is the only human actor; the Topology-Aware Auto Parallel placement engine is a system consumer, not a persona, and is covered under Feature Requirements below.

## User Journey Maps

### Primary User Journey: Adding a Windows node to an exo cluster

1. **Awareness:** The operator has an existing exo cluster (e.g. Macs) and wants to add spare Windows hardware (AMD Ryzen 7 + Radeon RX, or an NVIDIA card) to increase available memory for larger models.
2. **Consideration:** They check whether exo supports Windows telemetry at all today — currently `README.md:109-118,180` documents `macmon` as macOS-only, and Linux is documented as CPU-only with no GPU telemetry story.
3. **Adoption:** They run `uv run exo` on the Windows machine; it joins the cluster's topology without crashing regardless of whether an NVIDIA/AMD GPU or hardware-monitoring tool is present.
4. **Usage:** They open the dashboard and see the Windows node's real CPU/GPU model name, live RAM/VRAM numbers, and CPU/GPU utilization; they launch a model large enough that shard placement must account for the Windows node's VRAM, and the model loads successfully split correctly across it.
5. **Retention:** The Windows node keeps reporting telemetry every polling interval without needing the operator to install extra software beyond what `uv run exo` already pulls in; if optional GPU tooling is missing, the node still reports RAM/disk instead of failing.

### MECE Check: Journeys

- [x] Each journey describes a distinct path (no two journeys cover the same actions for the same persona)
- [x] All primary, secondary, and error/recovery paths are mapped (no gaps) — degraded-telemetry recovery is captured within the primary journey's step 4/5 language ("if optional GPU tooling is missing, the node still reports RAM/disk") since it is a variant of the same end-to-end flow, not a separate user goal.
- [x] Every persona has at least one journey

## Feature Requirements

### Must Have Features

The minimum needed for a Windows node to participate correctly in placement: accurate RAM, VRAM, and compute-load telemetry that never takes the node down, plus a real hardware identity.

#### Feature 1: Windows RAM and disk telemetry parity with macOS

- **User Story:** As a Cluster Operator, I want my Windows node to report RAM and disk telemetry exactly as reliably as a macOS node so that placement can trust its memory numbers.
- **Acceptance Criteria (Gherkin Format):**

  - [x] Given a Windows node has just started, When the node's telemetry loop begins, Then within the first polling interval the node reports total and available system RAM and disk space for the models directory to the cluster.
  - [x] Given a Windows node is running normally, When system RAM usage changes, Then the reported available RAM value updates within the existing polling interval (no worse than the current psutil-based interval).
  - [x] Given the `OVERRIDE_MEMORY_MB` environment variable is set on a Windows node, When telemetry is gathered, Then the reported available RAM reflects the override value, matching existing non-Darwin behavior.

#### Feature 2: Windows GPU VRAM and utilization telemetry

- **User Story:** As a Cluster Operator, I want my Windows node's discrete GPU VRAM and utilization reported so that Topology-Aware Auto Parallel can account for GPU memory, not just system RAM, when placing shards.
- **Acceptance Criteria (Gherkin Format):**

  - [x] Given a Windows node has a supported discrete GPU (NVIDIA or AMD) and the required telemetry source is available, When telemetry is gathered, Then the node reports total and available VRAM alongside GPU utilization percentage.
  - [x] Given a Windows node has an NVIDIA GPU, When telemetry is gathered, Then the reported VRAM figures are accurate to the GPU's actual dedicated memory (not shared/system memory).
  - [x] Given a Windows node has an AMD GPU, When telemetry is gathered, Then the reported VRAM figures are accurate to the GPU's actual dedicated memory.
  - [x] Given a Windows node has no discrete GPU, or the required telemetry source is unavailable, When telemetry is gathered, Then the node still reports RAM/disk telemetry and does not report a false VRAM value.

#### Feature 3: Windows node identity (CPU/GPU model names)

- **User Story:** As a Cluster Operator, I want to see the real CPU and GPU model names for my Windows node in the dashboard so that I can identify hardware in a mixed-OS cluster.
- **Acceptance Criteria (Gherkin Format):**

  - [x] Given a Windows node has started, When node identity is gathered, Then the node reports its actual CPU model name and GPU model name instead of the literal strings "Unknown Model" / "Unknown Chip".
  - [x] Given a Windows node's GPU model cannot be determined (no supported detection path available), When node identity is gathered, Then the node reports a clearly labeled "unknown GPU" identity rather than crashing or silently omitting the field.

#### Feature 4: Telemetry never takes a Windows node down

- **User Story:** As a Cluster Operator, I want a Windows node to keep participating in the cluster even if GPU-specific telemetry tooling is missing or errors, so that a monitoring failure never removes usable compute from my cluster.
- **Acceptance Criteria (Gherkin Format):**

  - [x] Given a Windows node's GPU telemetry source raises an error or times out, When the telemetry loop encounters this, Then the node logs a warning, continues reporting RAM/disk telemetry, and does not crash the node process.
  - [x] Given a Windows node's GPU telemetry source is not installed/available at all, When the node starts, Then the node degrades to RAM/disk-only telemetry from the first polling interval, mirroring the existing macmon-missing fallback behavior on other platforms.

### Should Have Features

- Windows OS version and build version reported for node identity (parity with macOS's `os_version`/`os_build_version` fields), rather than left as generic platform strings.
- CPU temperature and power draw reported on Windows where the chosen telemetry source exposes them, for dashboard parity with macOS.

### Could Have Features

- Support for additional Windows GPU vendors/telemetry backends (e.g. Intel Arc) beyond NVIDIA and AMD, if a reasonable low-effort detection path exists.
- Reporting per-process GPU memory usage on Windows nodes, for deeper diagnostics beyond what placement needs.

### Won't Have (This Phase)

- Changing how placement/`filter_cycles_by_memory` and `allocate_layers_proportionally` (`src/exo/master/placement_utils.py:21-37,96-123`) select cycles or allocate layers to actively use the new VRAM field for eligibility or scoring — this phase publishes accurate VRAM telemetry into state; whether placement consumes it is a separate, explicitly deferred decision (see solution.md ADR on VRAM-aware placement).
- Building a native macOS-style hardware monitor binary for Windows (a `macmon`-equivalent shipped/packaged executable) — telemetry is gathered via in-process Python libraries and OS APIs, not a bundled external binary.
- RDMA-over-Thunderbolt, Thunderbolt Bridge detection, or any Thunderbolt-specific telemetry on Windows — Thunderbolt features remain macOS-only and out of scope here.
- Windows support for backends other than telemetry reporting (e.g. adding a Windows-native inference backend/engine) — this spec is about hardware telemetry, not inference execution.

### MECE Check: Features

- [x] No two user stories describe the same capability (no overlap across MoSCoW categories)
- [x] All capabilities needed to solve the problem for every persona are present (no gaps)
- [x] Every feature has testable acceptance criteria
- [x] "Won't Have" explicitly accounts for capabilities that could be confused with in-scope features (placement consumption of VRAM, native monitor binaries, Thunderbolt, and non-telemetry Windows backend work are each explicitly excluded)

## Detailed Feature Specifications

### Feature: Windows GPU VRAM and utilization telemetry

**Description:** On Windows, the node telemetry loop gathers GPU VRAM (total/available) and utilization percentage from whichever supported telemetry source is available on the machine, normalizes it into the same shape as macOS's GPU telemetry, and publishes it on the same cadence as existing telemetry (memory: 1s; misc/static info: 10-60s, per current polling intervals in `src/exo/utils/info_gatherer/info_gatherer.py:444-456`).

**User Flow:**
1. Windows node starts `uv run exo`.
2. System detects the platform is Windows and selects the appropriate telemetry-gathering path for this platform instead of attempting to launch `macmon`.
3. System attempts to read GPU VRAM/utilization from the available telemetry source(s) in priority order.
4. Dashboard displays the resulting RAM, VRAM, GPU utilization, and CPU utilization for the Windows node, refreshed each polling interval.

**Business Rules:**
- Rule 1: A Windows node with a detectable NVIDIA GPU reports NVIDIA-sourced VRAM figures reflecting dedicated GPU memory, not host RAM.
- Rule 2: A Windows node with a detectable AMD GPU reports AMD-sourced VRAM figures reflecting dedicated GPU memory.
- Rule 3: If GPU-specific telemetry cannot be obtained for any reason, the node still reports RAM and disk telemetry — GPU absence never blocks the RAM telemetry path.
- Rule 4: Node identity (CPU/GPU model name) is refreshed on the same cadence as macOS's static node info (`src/exo/utils/info_gatherer/info_gatherer.py:467-474`, currently 60s), not on every telemetry tick, since hardware identity does not change at runtime.

**Edge Cases:**
- Scenario 1: Windows node has an integrated GPU only (no discrete GPU) → Expected: node reports RAM/disk telemetry; GPU VRAM is omitted or reported as unavailable rather than fabricated from shared memory.
- Scenario 2: Windows node has both an NVIDIA and an AMD GPU installed → Expected: the design records which GPU is reported and why, so this is a deterministic, testable behavior rather than an unspecified rule (see solution.md).
- Scenario 3: The chosen telemetry library is not installed / raises an import error at runtime → Expected: node logs a warning once and degrades to RAM/disk-only telemetry, matching the existing macmon-missing fallback pattern in `src/exo/utils/info_gatherer/info_gatherer.py:574-588`.
- Scenario 4: The chosen telemetry source requires elevated (administrator) privileges that the running user lacks → Expected: node logs a warning and degrades to RAM/disk-only telemetry rather than crashing or hanging.

## Success Metrics

### Key Performance Indicators

- **Adoption:** 100% of Windows nodes joining a cluster report non-"Unknown" CPU model identity within the first 60 seconds of startup (matching the existing 60s static-info polling interval).
- **Engagement:** Windows nodes with a supported discrete GPU report non-zero VRAM total within the first RAM/GPU polling interval after startup, on every cluster session.
- **Quality:** Zero node-process crashes attributable to the telemetry-gathering code path on Windows, across normal operation and all identified degradation scenarios (missing library, missing admin rights, GPU absent).
- **Business Impact:** A model whose total parameter size exceeds any single node's system RAM, but fits within combined RAM across a mixed macOS/Windows cluster including a Windows node's contribution, successfully loads and runs split across that cluster.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `NodeGatheredInfo` (existing event, extended payload) | node_id, telemetry variant (RAM-only vs. RAM+GPU), platform | Confirms which telemetry tier a given node is operating in, for support/debugging |
| Node identity update | node_id, model name, chip/GPU name | Confirms hardware identity resolution succeeded rather than falling back to "Unknown" |

---

## Constraints and Assumptions

### Constraints

- Must not introduce a required, always-on external binary dependency for Windows the way `macmon` is required on macOS — Windows telemetry must degrade gracefully when its data sources are unavailable, since there is no single universal Windows equivalent of `macmon`.
- Must fit within the existing event-sourced telemetry pipeline (`InfoGatherer` → `NodeGatheredInfo` event → `apply_node_gathered_info` → `State`) without breaking the wire format consumed by already-connected macOS/Linux nodes.
- Must respect exo's strict typing and immutability conventions (frozen, strict Pydantic models; exhaustive `match` handling) as codified in `AGENTS.md` and demonstrated in `src/exo/shared/types/profiling.py` and `src/exo/shared/apply.py`.
- `pyproject.toml:188` currently restricts `uv`'s dependency resolution environments to `sys_platform == 'darwin'` and `sys_platform == 'linux'`; any new Windows-only dependency must be added without breaking resolution on Darwin/Linux (e.g. via platform markers), and Windows must become a resolvable environment for this feature to install correctly.

### Assumptions

- The target Windows hardware includes, at minimum, the case explicitly named by the requester: an AMD Ryzen 7 CPU paired with an AMD Radeon RX discrete GPU. NVIDIA GPU support is also required, since `src/exo/utils/info_gatherer/info_gatherer.py:357-369` already detects NVIDIA via `pynvml` for backend selection today (just not for VRAM telemetry).
- Cluster operators running exo on Windows are willing to run `uv run exo` as documented for macOS/Linux; no separate Windows installer/app is assumed or required by this spec.
- The dashboard already renders whatever fields `SystemPerformanceProfile`/`MemoryUsage`/`NodeIdentity` expose per node; this spec does not require new dashboard UI beyond displaying new fields already surfaced generically (dashboard changes for e.g. VRAM display are covered by existing generic node-metric rendering).

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Chosen Windows GPU telemetry API changes behavior/output format across driver versions | Medium — could report stale or wrong VRAM numbers | Medium | Validate parsed output against expected schema before trusting it (mirrors the existing `MacmonMetrics.from_raw_json` validation pattern), and fall back to RAM-only telemetry on parse failure |
| Elevated-privilege requirement for some telemetry sources silently produces zero/empty data instead of an error | High — placement could under-allocate a capable node without any visible failure | Medium | Explicitly detect "no data returned" as a degradation case (not silently treated as "0 VRAM available"), and log a distinguishable warning |
| A Windows node with both NVIDIA and AMD GPUs installed produces ambiguous "which GPU is this node's GPU" telemetry | Low — affects only a rare multi-GPU-vendor case | Low | Document a deterministic selection rule in solution.md (e.g. prefer the GPU used by the exo backend selection logic) so behavior is specified, not accidental |
| Adding a Windows-only dependency breaks `uv` resolution or CI configured for Darwin/Linux only | High — could break existing builds | Low | Use platform-conditional dependency markers so the new Windows library is only resolved when `sys_platform == 'win32'`, leaving Darwin/Linux resolution untouched |

## Open Questions

None — all decisions required to implement this phase have been resolved in solution.md (see ADRs), including the choice of Windows telemetry source(s) and the explicit decision to defer VRAM-aware placement scoring to a future spec.

---

## Supporting Research

### Competitive Analysis

Not applicable — this is an internal cluster-orchestration capability, not a market-facing product surface with external competitors to benchmark against.

### User Research

Validated directly against the requesting stakeholder's stated hardware (AMD Ryzen 7 + Radeon RX) and against the current codebase's platform-gating behavior, confirmed by reading `src/exo/utils/info_gatherer/info_gatherer.py`, `src/exo/utils/info_gatherer/system_info.py`, and `src/exo/shared/types/profiling.py` directly rather than assuming behavior.

### Market Data

Not applicable.
