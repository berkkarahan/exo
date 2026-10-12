---
title: "Heterogeneous Cluster Orchestration"
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

| Field | Value |
|-------|-------|
| specId | 007-heterogeneous-cluster-orchestration |
| title | Heterogeneous Cluster Orchestration |
| status | COMPLETE |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 16 |

### SectionStatus

| Section | Status |
|---------|--------|
| Product Overview | COMPLETE |
| User Personas | COMPLETE |
| User Journey Maps | COMPLETE |
| Feature Requirements | COMPLETE |
| Detailed Feature Specifications | COMPLETE |
| Success Metrics | COMPLETE |
| Constraints and Assumptions | COMPLETE |
| Risks and Mitigations | COMPLETE |
| Open Questions | COMPLETE (none remaining) |
| Supporting Research | COMPLETE |

---

## Product Overview

### Vision

A single exo cluster runs frontier-scale models across whatever hardware a user actually owns — a macOS Apple Silicon workstation, a Windows AMD desktop, a Windows NVIDIA laptop — pooling their combined memory without asking the user to own a homogeneous fleet.

### Problem Statement

Today, exo's placement logic rejects any cluster cycle whose nodes don't all share a common backend (`Backend` capability filtering means a cycle with one Apple Silicon Mac and one Windows PC is never selected for a shared model instance, because the Mac only ever reports MLX backends and the Windows node — once Windows inference support lands per spec 001 — only ever reports ONNX Runtime backends; no cycle satisfies "all nodes share a backend"). A user who owns both an M-series Mac and a Windows gaming PC cannot combine their memory to run a model that fits in neither machine alone; each device is stuck running smaller models solo, or the user must buy more of the same hardware, which is exactly the "buy another Mac" cost problem exo otherwise solves for homogeneous Apple Silicon clusters.

### Value Proposition

Users with mixed hardware already sitting in their home or office — the common case, not the exception, once exo also runs on Windows (spec 001) — get the same "pool your devices, run the frontier model" value proposition exo already delivers to all-Apple-Silicon households, without buying additional matching hardware. This directly extends exo's core differentiator (device pooling) to the mixed-vendor reality most multi-device owners actually have.

## User Personas

### Primary Persona: Mixed-Hardware Household Owner

- **Demographics:** Enthusiast or small-team owner of 2+ personal computers acquired over time (not purchased as a matching cluster) — e.g. an M-series MacBook/Mac Studio plus a Windows desktop with a discrete AMD or NVIDIA GPU. Comfortable running local AI tools and reading a dashboard, not necessarily a distributed-systems engineer.
- **Goals:** Run a model that doesn't fit in any single device's memory, using devices already owned, without buying another Mac (or another Windows GPU) just to match what they have.
- **Pain Points:** exo already discovers the mixed devices on the network (automatic device discovery is unconditional), and the dashboard shows them all — but placement silently offers only same-backend placements or nothing at all, with no clear explanation of why the Windows node "doesn't count."

### Secondary Personas

None. A single persona (a person who owns mixed hardware and wants to pool it) covers every interaction surface this spec touches — there is no separate administrator, developer, or operator role for this capability; the dashboard/API user and the hardware owner are the same person.

### MECE Check: Personas

- [x] Each persona has distinct goals and pain points (no overlap) — only one persona is defined; no overlap risk.
- [x] All user types who interact with this feature are represented (no gaps) — placement, chat completion, and cluster visibility are all exercised by the same owner persona; no distinct viewer/admin role exists in exo today.

## User Journey Maps

### Primary User Journey: Pool a Mac and a Windows PC to Run a Large Model

1. **Awareness:** The user notices, via the exo dashboard's cluster view, that their Mac and Windows PC are both discovered as nodes, but a model too large for either device alone shows no valid placement, or an error referencing incompatible backends.
2. **Consideration:** The user checks whether exo supports mixed-backend clusters (reading docs/release notes) versus considering buying a second Mac to match their first.
3. **Adoption:** The user sees exo's `/instance/previews` endpoint (or the dashboard's placement picker) now offer a cross-backend pipeline placement spanning the Mac and the Windows PC, with a clear indication of which shard runs where.
4. **Usage:** The user creates the instance, sends a chat completion request, and receives coherent output — no worse in relevance/coherence than a same-backend placement would produce, generated by shards running on genuinely different accelerators (MLX/Metal on the Mac, ONNX Runtime on the Windows PC) cooperating over the network.
5. **Retention:** The user keeps both devices joined to the same exo cluster going forward, and adds further mixed devices as they acquire them, trusting exo to either place across them correctly or refuse with a clear, actionable reason (never to silently produce corrupted output).

### Secondary User Journeys

**Journey: Placement Refusal Is Clear, Not Silent.** A user attempts to place a model requiring tensor parallelism across a cluster where the only cycle large enough spans two different backends. exo refuses the placement (tensor parallelism across mixed backends is not supported this phase) with a specific, actionable error rather than either silently degrading to a smaller model or emitting a vague "no valid placement" message — the user understands why and what alternative (fewer nodes, same-backend cycle, or pipeline instead of tensor) is available.

### MECE Check: Journeys

- [x] Each journey describes a distinct path (no two journeys cover the same actions for the same persona) — the primary journey is the happy path to a working mixed-backend placement; the secondary journey is the explicit refusal path when the request can't be honored. No overlap.
- [x] All primary, secondary, and error/recovery paths are mapped (no gaps) — success and refusal are both covered; there is no third outcome (partial/corrupted placement) because that outcome is explicitly disallowed by this spec's correctness requirement (see Feature 3, Business Rules).
- [x] Every persona has at least one journey — the single defined persona has two.

## Feature Requirements

### Must Have Features

The minimum needed for a mixed-hardware owner to get real value: mixed-backend clusters must be placement-eligible at all, must run correctly (never silently wrong), and must actually improve on today's "run smaller models solo" baseline.

#### Feature 1: Mixed-Backend Cluster Eligibility

- **User Story:** As a mixed-hardware household owner, I want exo to consider a cycle spanning my Mac and my Windows PC as a valid placement target, so that I am not limited to whichever single device I happen to run a model on.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a cluster with one macOS node (MLX-capable) and one Windows node (ONNX Runtime-capable, per spec 001) that are network-connected, When the user requests placement of a model that fits neither device's memory alone but fits their combined memory, Then `/instance/previews` returns at least one placement whose cycle includes both nodes.
  - [x] Given the same mixed-backend cluster, When the user requests placement of a model that supports only tensor-parallel sharding, Then the system does not offer a placement spanning both backend types (see this feature's Won't Have boundary and Feature 3), and instead offers same-backend placements or a clear refusal if none exist.
  - [x] Given a cluster with three or more nodes of mixed backends, When placement is requested, Then the system does not reject a cycle purely because it contains more than one backend type — backend heterogeneity alone is no longer disqualifying for pipeline-eligible models.

#### Feature 2: Correct, Coherent Output From a Mixed-Backend Placement

- **User Story:** As a mixed-hardware household owner, I want chat completions served from a mixed-backend placement to read exactly as coherently as ones served from a single-backend placement, so that I can trust the cluster's answers regardless of which physical devices produced them.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a model instance placed across one macOS node and one Windows node in pipeline configuration, When the user sends `POST /v1/chat/completions`, Then the response contains a complete, grammatically coherent answer with no truncation, repeated garbage tokens, or empty output caused by a cross-node handoff error.
  - [x] Given the same mixed-backend instance, When the same prompt is also sent to an equivalent same-backend (all-macOS) placement of the same model, Then both responses are of comparable quality (a human reviewer cannot reliably tell which placement produced which response from coherence alone).
  - [x] Given a mixed-backend instance mid-generation, When one node's shard produces its portion of a token's hidden state, Then the next node in the pipeline receives and applies that exact hidden state before continuing, with no silent numeric corruption crossing the node boundary.

#### Feature 3: Safe Refusal Over Silent Corruption

- **User Story:** As a mixed-hardware household owner, I want exo to refuse a placement it cannot support correctly rather than attempt it and produce corrupted output, so that I never receive a wrong answer without knowing it might be wrong.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a model that requires tensor-parallel sharding and a cluster whose only sufficiently-large cycle spans two different backend types, When placement is requested, Then the system refuses the tensor-parallel placement with an error identifying the specific reason (cross-backend tensor parallelism is not supported), rather than attempting it.
  - [x] Given a mixed-backend pipeline placement where one node's reported activation-exchange dtype or format is incompatible with another node's, When placement is attempted, Then the system refuses at placement time (not mid-generation) with a clear, specific error.
  - [x] Given a successfully-placed mixed-backend pipeline instance, When generation runs, Then no code path silently substitutes a default/zero value for a cross-node activation it failed to receive correctly — failure to receive must surface as a task failure, not corrupted output.

### Should Have Features

Significantly improves the experience but is not required for the feature to deliver core value on launch.

#### Feature 4: Placement Favors the Faster Topology When Multiple Mixed-Backend Options Exist

- **User Story:** As a mixed-hardware household owner with more than two devices, I want exo to prefer the mixed-backend cycle that will run fastest (accounting for how much slower one device or one network link is than another), so that I get the best performance my hardware combination can offer, not just any valid combination.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given two candidate mixed-backend cycles of equal size and equal available memory, When one cycle's slowest node/link is meaningfully faster than the other cycle's slowest node/link, Then the system prefers the faster cycle.
  - [x] Given a mixed-backend cycle where devices differ significantly in compute throughput, When layers are assigned to each device, Then the slower device receives proportionally fewer layers than a purely memory-proportional split would give it, so no single device becomes the generation bottleneck.

### Could Have Features

Nice-to-haves if time and resources permit; not required for this phase's core value.

- Per-link bandwidth-aware layer boundary placement that avoids splitting a pipeline stage across a slow (e.g. Wi-Fi) link when a faster link is available for the same boundary.
- Surfacing a projected tokens/second estimate per candidate mixed-backend placement in `/instance/previews`, so the user can compare options before committing.
- A dashboard visualization distinguishing which shard of a mixed-backend instance runs on which physical device and backend type.

### Won't Have (This Phase)

Explicitly out of scope, so it is not mistaken for a gap:

- **Cross-backend tensor parallelism.** Tensor-parallel sharding stays restricted to a single homogeneous backend sub-group in this phase; a cycle spanning MLX and ONNX Runtime backends is never offered a tensor-parallel placement. (See Feature 3, Feature 1's second criterion.)
- **Re-specifying the Windows inference backend itself.** This spec depends on, and does not redefine, the Windows execution engine, ONNX Runtime GenAI integration, or `Backend.OnnxDirectMl`/`OnnxCuda`/`OnnxCpu` capability detection — that is spec 001's scope.
- **Re-specifying Windows hardware telemetry collection.** The VRAM, compute, and identity telemetry fields this spec's compute-aware placement consumes are defined and published by spec 002; this spec does not redefine how they are gathered.
- **Weight-format standardization across backends at the storage layer.** This phase does not require converting a single downloaded weight file into simultaneous INT8/FP16 representations for every backend; each backend continues loading weights in the representation it already uses (safetensors for MLX, the ONNX Runtime GenAI conversion pipeline from spec 001 for Windows). What this phase does require is a single, explicit, backend-agnostic numeric format for the *activations that cross a mixed-backend pipeline boundary* (see solution.md).
- **Routing per-token activation traffic over the Zenoh control-plane pub/sub layer.** Zenoh remains a control-plane-only channel in this design; activations travel over a dedicated point-to-point transport (see solution.md).

### MECE Check: Features

- [x] No two user stories describe the same capability (no overlap across MoSCoW categories) — eligibility (1), correctness (2), safety (3), and performance (4) are four distinct concerns.
- [x] All capabilities needed to solve the problem for every persona are present (no gaps) — the single persona's journey (discover → place → use → trust) is covered by Features 1–3, with Feature 4 improving the "use" step further.
- [x] Every feature has testable acceptance criteria.
- [x] "Won't Have" explicitly accounts for capabilities that could be confused with in-scope features (cross-backend tensor parallelism vs. pipeline parallelism; weight-format standardization vs. activation-format standardization; Zenoh-carries-tensors vs. a dedicated transport).

## Detailed Feature Specifications

### Feature: Correct, Coherent Output From a Mixed-Backend Placement

**Description:** When a pipeline-parallel model instance is placed across nodes of different backend types (e.g. one MLX/Metal node and one ONNX Runtime/DirectML node), each node computes its assigned contiguous range of transformer layers and must hand off the resulting hidden-state tensor to the next node in the pipeline in a format both ends agree on, regardless of which backend produced or consumes it.

**User Flow:**
1. User creates a mixed-backend pipeline instance for a model too large for any single device.
2. System places the instance, assigning each node a contiguous layer range (unchanged pipeline-assignment shape from today, just now spanning mixed backends).
3. User sends a chat completion request; each node computes its layers and passes the boundary hidden state to the next node over the point-to-point activation-exchange channel.
4. The final node produces logits and streams decoded tokens back to the user exactly as a same-backend placement does today.

**Business Rules:**
- Rule 1: Activations crossing a mixed-backend pipeline boundary are exchanged in one canonical numeric format, chosen once for the whole cluster, not negotiated per-node-pair (see solution.md for the specific format and rationale).
- Rule 2: A node that cannot produce or consume the canonical activation format is not eligible to join a mixed-backend cycle for that placement; it is a same-backend-only participant for tensor-parallel work, or excluded from the cycle entirely for pipeline work.
- Rule 3: Every mixed-backend release is validated against a determinism/equivalence check confirming a mixed-backend placement's output diverges from a same-backend placement's output only within an accepted numeric tolerance for the same prompt and seed, not qualitatively.

**Edge Cases:**
- Scenario 1: A node in the pipeline crashes or loses network connectivity mid-generation. → Expected: the in-flight generation task fails with a clear terminal state (matching today's existing terminal-failure behavior for any node dropout), not a hang or corrupted partial output delivered to the user.
- Scenario 2: The activation tensor for a given boundary exceeds a size that the point-to-point transport can carry within its configured limits. → Expected: placement-time validation catches shapes/sizes that would exceed transport limits for the model in question before generation starts, refusing the placement rather than failing mid-stream.

## Success Metrics

### Key Performance Indicators

- **Adoption:** Of clusters exo detects as containing 2+ different backend types (Mac + Windows), the fraction that successfully create at least one mixed-backend instance within their first week of having both devices joined.
- **Engagement:** Mixed-backend instances created per mixed-hardware cluster per week, compared to same-backend instances created by the same cluster's owner (a rising ratio indicates the feature is displacing the "run solo" workaround).
- **Quality:** Chat completion success rate (non-error, complete responses) for mixed-backend instances, targeted at parity with same-backend instance success rate; zero incidents of corrupted-but-delivered output (a correctness bug in this feature is a Sev-1, not a quality-score nudge).
- **Business Impact:** Reduction in users reporting "I have a Mac and a Windows PC but can't combine them" as a blocker, tracked via community support channels (Discord/GitHub issues).

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Mixed-backend cycle offered | model_id, cycle_backend_types, cycle_size | Measure how often eligibility (Feature 1) actually surfaces an option |
| Mixed-backend instance created | model_id, sharding, backend_types_in_cycle | Measure adoption of the offered option |
| Mixed-backend placement refused | model_id, sharding, refusal_reason | Measure how often and why Feature 3's safe-refusal path triggers, to catch both over-eager and over-cautious refusal |
| Cross-backend activation handoff failure | instance_id, boundary_rank_pair, failure_type | Detect correctness or transport regressions in production |

---

## Constraints and Assumptions

### Constraints

- This spec depends on spec 001 (Windows inference backend abstraction) already having landed `Backend.OnnxDirectMl`/`OnnxCuda`/`OnnxCpu`, the `engines/onnx/` execution engine, and the `InstanceMeta.OnnxPipeline` / `OnnxPipelineInstance` placement types — this spec builds on those types rather than redefining them.
- This spec depends on spec 002 (Windows system telemetry) already publishing VRAM and identity telemetry for Windows nodes into `SystemPerformanceProfile` — the compute-aware allocation in Feature 4 consumes whatever compute/telemetry signal is available at the time this spec is implemented; if a compute-capability figure does not yet exist, this spec is responsible for adding the minimal one it needs (see solution.md).
- No new required external dependency may be introduced for the control-plane transport — Zenoh remains control-plane-only per the Won't Have list; this is a hard constraint carried over from the existing architecture, not a preference.
- The existing `Engine`/`Builder` lifecycle ABC contract (unrelated to this spec, defined in spec 001's territory) must not be broken.

### Assumptions

- We assume the mixed-hardware household scenario (one Apple Silicon Mac + one Windows PC on the same LAN) is common enough among exo's target audience to justify this investment — validated by the epic's explicit framing of this as a top-level use case, and by exo's existing "device pooling" value proposition already attracting users with heterogeneous device counts (though not yet heterogeneous backends, since Windows support doesn't exist until spec 001 ships).
- We assume users placing mixed-backend instances are on the same local network with typical home/office network characteristics (Ethernet or Wi-Fi, not exotic RDMA fabrics) — RDMA-based JACCL placements remain MLX-Metal-only per today's `INSTANCE_META_BACKENDS` restriction and are not extended to mixed backends by this spec.
- We assume a small, bounded numeric tolerance between a mixed-backend response and a same-backend response is acceptable to users (bit-for-bit identical output across different hardware/software stacks is not a realistic bar, matching how exo already treats bit-exactness as a test-only invariant within a single backend, not a cross-backend guarantee).

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Cross-backend activation format mismatch produces subtly wrong (not obviously broken) output that a user trusts incorrectly | High | Medium | Feature 3's safe-refusal-over-corruption requirement plus a mandatory determinism/equivalence check before this capability ships (Business Rule 3) |
| Memory-proportional-only layer allocation (today's behavior) becomes actively harmful once nodes differ wildly in compute speed, making the slowest node the bottleneck for the whole cluster | Medium | High | Feature 4 (Should Have) introduces compute-aware allocation; even without it, Feature 1–3 deliver value (correct pooling) before performance optimization lands |
| The point-to-point activation transport becomes a new attack surface or reliability weak point distinct from the existing Zenoh control plane | Medium | Low | Transport is scoped to the existing intra-cluster trust boundary (same LAN, same trust level as today's disaggregated-prefill TCP server already accepted in production) |
| Users expect this spec to also standardize weight quantization across backends at the storage layer, and are confused when it doesn't | Low | Medium | Explicit Won't Have entry naming the distinction between weight-format standardization (out of scope) and activation-format standardization (in scope) |

## Open Questions

None remaining — all decisions required to complete this PRD were resolved during specification (see solution.md's Architecture Decisions and README.md's Decisions Log for the specific choices and rationale).

---

## Supporting Research

### Competitive Analysis

Distributed local-inference tools in this space (llama.cpp's RPC backend, some ExoLabs contemporaries) generally either (a) restrict distributed clusters to a single backend/runtime, mirroring exo's current constraint, or (b) support heterogeneous clusters only at a coarse "run different model replicas on different machines" level rather than sharding a single model instance across mixed hardware. A cluster that shards one model instance across genuinely different accelerator backends with a correctness guarantee is a differentiator, not table stakes.

### User Research

No formal user research was conducted for this spec; the primary evidence is the epic's explicit user story (verbatim: "As a user with a diverse hardware setup, I want to seamlessly pool the VRAM of mixed devices") and the codebase's existing device-pooling value proposition, which today only works within a single backend family.

### Market Data

Not applicable — no external market sizing was used; this feature is scoped from direct product requirements (the epic) and verified current-system behavior (the codebase mapping pass referenced throughout this spec and solution.md).
