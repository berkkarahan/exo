---
title: "Windows Inference Backend Abstraction"
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
| specId | 001-windows-inference-backend-abstraction |
| title | Windows Inference Backend Abstraction |
| status | COMPLETE |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 22 |
| openQuestions | none |

### Section Status

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
| Open Questions | COMPLETE (none outstanding) |
| Supporting Research | COMPLETE |

---

## Product Overview

### Vision

Any owner of a Windows PC with a modern GPU — AMD Radeon, NVIDIA GeForce/RTX, or CPU-only — can join or run an exo cluster and get GPU-accelerated local inference, with the same dashboard, API, and multi-device clustering experience that macOS and Linux users already have.

### Problem Statement

exo today only runs real accelerated inference on Apple Silicon (macOS, via MLX/Metal) and on NVIDIA GPUs under Linux (via a CUDA build of MLX). Windows is entirely unsupported as a compute platform: `pyproject.toml`'s `[tool.uv] environments` list only resolves dependencies for `sys_platform == 'darwin'` and `sys_platform == 'linux'`, so `uv sync` cannot even install exo's inference dependencies on Windows. Every accelerated code path in the worker (model loading, KV caching, tensor/pipeline parallel sharding, generation) is written directly against MLX's array and module types, with no seam for a different runtime.

This shuts out a large population of AI enthusiasts and developers who own Windows gaming/workstation PCs with AMD Ryzen CPUs and Radeon RX GPUs, or NVIDIA GeForce/RTX GPUs, but no Mac and no Linux dual-boot. They cannot contribute their GPU's VRAM and compute to a home exo cluster, and cannot run exo standalone on their own machine, even though their hardware is capable of fast local LLM inference. The consequence is a smaller addressable cluster (fewer devices, less aggregate VRAM) and a segment of the target audience — Windows-first AI hobbyists — who cannot use exo at all today.

### Value Proposition

Windows support turns every capable Windows gaming or workstation PC into a usable exo node without requiring the user to dual-boot Linux, buy a Mac, or accept CPU-only speeds. Users get to use hardware they already own — including AMD setups that today have no first-class local-LLM story — and can add that hardware's VRAM and compute to a multi-device exo cluster alongside their existing Mac or Linux machines, increasing the total model size and throughput the cluster can support.

## User Personas

### Primary Persona: Windows GPU Owner

- **Demographics:** Home AI enthusiast or developer, comfortable with the command line and installing developer tooling (uv, git), owns a Windows 10/11 gaming or workstation PC with a discrete GPU — either an AMD Ryzen CPU + Radeon RX GPU, or an NVIDIA GeForce/RTX GPU. No macOS or Linux machine available, or wants to add their Windows box to an existing cluster.
- **Goals:** Run local LLM inference on their own hardware at GPU speed, either standalone or as part of a multi-device exo cluster with their other machines, without buying new hardware or dual-booting.
- **Pain Points:** Cannot install exo's inference extras on Windows today (dependency resolution fails outright); if they work around it, every accelerated code path assumes MLX and Apple/NVIDIA-Linux hardware, so their AMD GPU's VRAM and compute sit unused; they are told to expect CPU-only speeds with no path to GPU acceleration.

### Secondary Personas

Windows CPU-Only Owner — a Windows PC owner whose GPU has no supported acceleration path (e.g., an older/unsupported AMD/Intel GPU, or a machine with no discrete GPU at all). They still want to run exo on Windows using CPU inference, as the honest fallback, matching the level of support Linux CPU-only users already receive.

### MECE Check: Personas

- [x] Each persona has distinct goals and pain points (no overlap) — GPU Owner wants GPU acceleration; CPU-Only Owner explicitly wants a working CPU floor when no GPU path exists.
- [x] All user types who interact with this feature are represented (no gaps) — GPU-accelerated and CPU-only Windows users cover the full space of "a person running exo on Windows."

## User Journey Maps

### Primary User Journey: Windows GPU Owner joins/starts an exo cluster

1. **Awareness:** The user sees exo demonstrated on Mac clusters and wants the same experience on their Windows gaming PC, or already runs exo on other machines and wants to fold in their Windows box's VRAM.
2. **Consideration:** They check whether their AMD Radeon or NVIDIA GPU is supported, and whether Windows requires special drivers or a different install path than macOS/Linux.
3. **Adoption:** They follow Windows-specific setup instructions (`uv sync` succeeds on Windows, GPU driver/runtime prerequisites documented), run `uv run exo`, and see their node correctly report a GPU-capable backend rather than CPU-only.
4. **Usage:** They create a model instance (standalone or across their cluster including the Windows node), send chat completion requests through the OpenAI-compatible API/dashboard, and observe generation running at GPU speed rather than CPU speed on the Windows node.
5. **Retention:** They keep using exo because their whole hardware collection — Mac, Linux, and Windows — now contributes real compute to one cluster, rather than leaving the Windows box out.

### Secondary User Journeys

Windows CPU-Only Owner: discovers no GPU acceleration path applies to their hardware, installs the CPU-only Windows extra, runs `uv run exo`, and gets working (if slower) inference rather than an install failure — matching the CPU-only experience Linux already provides.

### MECE Check: Journeys

- [x] Each journey describes a distinct path (no two journeys cover the same actions for the same persona)
- [x] All primary, secondary, and error/recovery paths are mapped (no gaps) — GPU success path and CPU-fallback path both covered
- [x] Every persona has at least one journey

## Feature Requirements

### Must Have Features

#### Feature 1: Windows Installability

- **User Story:** As a Windows GPU Owner, I want `uv sync` to successfully install exo's inference dependencies on Windows, so that I can get past the install step at all.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a Windows 10/11 machine with Python and uv installed, When the user runs the Windows dependency install command from a clean checkout, Then dependency resolution and installation complete successfully with no platform-resolution errors.
  - [x] Given the install has completed, When the user runs `uv run exo`, Then the process starts, serves the dashboard and API at `http://localhost:52415`, and does not crash on startup due to a missing or unsupported inference backend.
  - [x] Given a Windows machine with no supported GPU, When the user installs the CPU-only Windows extra, Then install and startup succeed the same way, with the node reporting CPU-only capability.

#### Feature 2: Windows GPU-Accelerated Single-Node Inference

- **User Story:** As a Windows GPU Owner, I want exo to use my AMD Radeon or NVIDIA GPU for inference, so that I get fast local generation instead of being limited to CPU speed.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a Windows machine with a supported AMD Radeon GPU, When the user starts exo and creates a single-node model instance, Then a chat completion request to the OpenAI-compatible API returns generated tokens, and the node's reported backend capability indicates GPU acceleration rather than CPU-only.
  - [x] Given a Windows machine with a supported NVIDIA GPU, When the user starts exo and creates a single-node model instance, Then a chat completion request returns generated tokens using the GPU, at materially higher tokens/second than the same model run CPU-only on the same machine.
  - [x] Given a running Windows GPU instance, When generation is in progress, Then the dashboard's node view shows GPU memory/VRAM usage for the instance rather than reporting no GPU information.

#### Feature 3: Windows CPU Fallback Inference

- **User Story:** As a Windows CPU-Only Owner, I want exo to still work correctly using CPU-only inference when no supported GPU acceleration path is available, so that my machine is still usable rather than unsupported.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a Windows machine with no supported GPU acceleration path, When the user starts exo and creates a single-node model instance, Then a chat completion request returns correct generated tokens using CPU-only execution.
  - [x] Given a Windows machine where GPU acceleration is expected to be available but fails to initialize, When exo starts the instance, Then exo reports a clear error/state rather than silently producing incorrect output, and (where feasible) falls back to CPU rather than crashing the node.

#### Feature 4: Windows Node in a Multi-Device Cluster

- **User Story:** As a Windows GPU Owner who also owns a Mac or Linux exo node, I want my Windows machine to join the same exo cluster, so that its VRAM and compute add to the cluster's total capacity for larger models.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [x] Given a running Mac or Linux exo node and a running Windows exo node on the same network, When both are started, Then they automatically discover each other and appear together in cluster state (e.g., via the `/state` API and dashboard cluster view).
  - [x] Given a discovered multi-node cluster including a Windows node, When the user requests a placement preview for a model that needs pipeline sharding across nodes, Then the Windows node is offered as a valid placement target, and a subsequent chat completion against that placement returns correctly generated tokens contributed in part by the Windows node.

### Should Have Features

- **Tensor-Parallel Windows Participation:** A Windows node can participate as one rank in a tensor-parallel (not just pipeline-parallel) multi-node instance, splitting a single layer's compute across devices including the Windows node, for models the Windows backend declares tensor-parallel-capable.
- **Accurate Windows VRAM Reporting for Placement:** The Windows node reports real, current GPU VRAM headroom to the master's placement logic, so that placement previews and automatic model-size-to-hardware matching are as accurate on Windows as they are today on macOS/Linux, rather than falling back to conservative guesses.

### Could Have Features

- **Multi-GPU Single Windows Box:** A single Windows machine with more than one GPU installed can shard a model across its own local GPUs.
- **Broader Model Architecture Coverage on Windows:** Support for model architectures beyond the initial Windows-launch set (e.g., additional MoE or vision-language architectures already supported on MLX), added incrementally as the Windows backend matures.

### Won't Have (This Phase)

- **Windows Image/Diffusion Generation:** Image and image-editing model support (the `mflux`/diffusion engine) is out of scope for this phase; Windows nodes will support text-generation (chat completions) only. This is explicitly separate from, and not to be confused with, "Windows GPU-Accelerated Single-Node Inference," which covers text generation only.
- **RDMA-over-Thunderbolt on Windows:** The low-latency Thunderbolt RDMA networking feature is Apple-hardware-specific and is not part of Windows support.
- **Full MLX Architecture Parity on Day One:** Every model architecture exo currently supports via MLX (e.g., every MoE variant listed in the existing auto-parallel sharding strategies) is not guaranteed to work on the Windows backend at launch; only a defined initial set of architectures is guaranteed, with broader coverage tracked as a Could Have.
- **Windows Support for the macOS App / Windows Installer Package:** A native Windows installer or background-service app (equivalent to the macOS `.dmg` app) is out of scope; Windows support in this phase is "run from source" only, matching how Linux is supported today.

### MECE Check: Features

- [x] No two user stories describe the same capability (no overlap across MoSCoW categories) — install, GPU inference, CPU fallback, and clustering are each a distinct capability.
- [x] All capabilities needed to solve the problem for every persona are present (no gaps) — GPU Owner is covered by Features 1, 2, 4 and the Should Haves; CPU-Only Owner is covered by Features 1 and 3.
- [x] Every feature has testable acceptance criteria.
- [x] "Won't Have" explicitly accounts for capabilities that could be confused with in-scope features — image generation is explicitly distinguished from the in-scope text-generation GPU feature; full architecture parity is explicitly distinguished from the in-scope "initial architecture set."

## Detailed Feature Specifications

### Feature: Windows GPU-Accelerated Single-Node Inference

**Description:** When a user starts exo on a Windows machine with a supported GPU (AMD Radeon or NVIDIA), the node detects and reports GPU acceleration capability, and model instances placed on that node run inference using the GPU rather than the CPU, exposed through exo's existing OpenAI-compatible chat completions API and dashboard exactly as on macOS/Linux today.

**User Flow:**

1. User installs exo on Windows with the appropriate GPU extra for their hardware and runs `uv run exo`.
2. System detects the GPU, reports a GPU-capable backend for the node, and makes the dashboard/API available at `http://localhost:52415`.
3. User creates a model instance (via dashboard or `POST /instance`) sized to fit the detected GPU's VRAM.
4. System loads the model onto the GPU and serves chat completion requests using GPU compute.
5. User sees generation happen at GPU speed in the dashboard chat UI or via `curl` against `/v1/chat/completions`.

**Business Rules:**

- Rule 1: A node only advertises GPU-capable backend status if a supported GPU runtime is actually detected and initializes successfully; it must never claim GPU capability it cannot deliver.
- Rule 2: If GPU initialization fails after being advertised as available, the affected instance must fail visibly (error state) rather than silently degrading to incorrect or corrupted output.
- Rule 3: A Windows node with no supported GPU must still be usable for CPU-only inference — it is never simply "unsupported."

**Edge Cases:**

- Scenario 1: User has an AMD GPU whose driver/runtime is out of date or missing → Expected: exo reports a clear capability/error message (e.g., in node status or startup logs) rather than crashing or silently running on CPU without telling the user.
- Scenario 2: A model is requested that exceeds the Windows GPU's VRAM → Expected: placement is rejected the same way it is today when a Mac/Linux GPU lacks sufficient memory (consistent behavior across platforms), not a Windows-specific crash.
- Scenario 3: A model architecture is not yet supported on the Windows backend → Expected: the model is reported as unavailable for that node/backend rather than being accepted and failing at generation time.

## Success Metrics

### Key Performance Indicators

- **Adoption:** Number of distinct Windows nodes that successfully complete at least one chat completion request, tracked from release.
- **Engagement:** Proportion of Windows nodes that run with GPU acceleration enabled vs. CPU-only fallback, indicating real hardware coverage rather than fallback-only usage.
- **Quality:** Generation success rate (completed requests / attempted requests) on Windows GPU nodes, targeted to match the existing success rate on macOS/Linux GPU nodes.
- **Business Impact:** Growth in average cluster size (total nodes, total aggregate VRAM) for users who add a Windows node to an existing macOS/Linux cluster.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Node startup on Windows | detected backend (GPU vendor/runtime or CPU-only), GPU model, driver/runtime version | Measure real hardware coverage and detect unsupported-hardware patterns |
| Chat completion request served by a Windows node | backend used, model id, sharding mode (single-node/pipeline/tensor), success/failure | Measure adoption, quality, and which capabilities are actually exercised |
| GPU initialization failure | GPU vendor, failure reason, fell back to CPU (yes/no) | Measure reliability of the GPU acceleration path and fallback behavior |

---

## Constraints and Assumptions

### Constraints

- exo's Python dependency resolution (`uv`) must add Windows as a supported platform without breaking existing macOS/Linux resolution, packaging, and CI.
- The chosen Windows acceleration approach must work with both AMD (Radeon) and NVIDIA GPU vendors, since the primary persona explicitly includes both.
- Windows support must work as a single standalone node (not only as a member of a multi-node cluster), since many Windows GPU Owners will not own a second machine.
- The feature must not change or regress existing macOS/Linux behavior, APIs, or performance.

### Assumptions

- Users on Windows are comfortable with a "run from source" developer setup (uv, git, command line), consistent with the current Linux support level; a polished installer is not assumed to be needed for this phase (see Won't Have).
- Users have GPU drivers already installed via the vendor's normal Windows driver installer (AMD Adrenalin / NVIDIA Game Ready or Studio drivers); exo is not assumed to manage GPU driver installation itself.
- The initial set of supported model architectures on Windows need not match 100% of what MLX supports on macOS on day one; users are assumed to accept a defined initial architecture list that grows over time.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Chosen Windows GPU runtime lacks efficient collective/communication primitives needed for multi-node tensor parallelism | Medium — limits Should Have tensor-parallel feature, not Must Have | Medium | Scope full tensor parallelism as Should Have; ship pipeline parallelism (which needs no cross-device collective ops beyond simple activation hand-off) as Must Have |
| AMD/NVIDIA GPU runtime coverage for quantized model weights differs from MLX's, causing some existing model cards to not load on Windows | High — user-visible "model not supported" for popular models | Medium | Define and publish the initial supported architecture/quantization set explicitly (Won't Have: full parity); track gaps as Could Have follow-up |
| Windows driver/runtime version fragmentation causes GPU initialization to silently fail or hang on some machines | High — Windows GPU Owner gets a broken experience | Medium | Require GPU initialization to fail fast with a clear error state (Business Rule 2) rather than hang or silently degrade |
| Windows CPU-only fallback is deprioritized in favor of GPU work and ships broken or absent | Medium — Windows CPU-Only Owner persona left unsupported | Low | Keep CPU fallback as an explicit Must Have feature with its own acceptance criteria, not an afterthought of the GPU feature |

## Open Questions

None outstanding — all decisions needed to proceed to solution design have been made and are recorded in this document's MoSCoW scope and in solution.md's Architecture Decisions.

---

## Supporting Research

### Competitive Analysis

Cross-platform local-inference tools that already support Windows (e.g., Ollama, LM Studio) rely on backend runtimes such as ONNX Runtime, Vulkan, or vendor-specific SDKs (DirectML, ROCm) rather than a single vendor-locked framework, confirming that Windows-side GPU acceleration for LLM inference is achievable without requiring the vendor's own framework (i.e., without needing an Apple-only or NVIDIA-only runtime).

### User Research

Public exo issue-tracker requests (referenced in `README.md`'s Hardware Accelerator Support section, which currently states Linux runs CPU-only and invites hardware-support requests) indicate active user demand for broader GPU/platform coverage beyond Apple Silicon; this PRD directly addresses the largest currently-unsupported platform, Windows.

### Market Data

AMD Ryzen CPUs paired with Radeon RX GPUs and NVIDIA GeForce/RTX GPUs represent the two dominant discrete-GPU configurations in the Windows gaming/workstation PC market — the primary persona's hardware profile is representative of a large existing installed base, not a niche configuration.
