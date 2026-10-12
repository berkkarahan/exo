# Specification: 001-windows-inference-backend-abstraction

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-11 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-09-11 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Business-level PRD for Windows GPU (AMD DirectML / NVIDIA CUDA+DirectML) and CPU inference support; 4 Must-Have, 2 Should-Have, 2 Could-Have features; 0 open questions. |
| solution.md | completed | Registry-dispatched backend plugin architecture extending the existing `Engine`/`Builder` ABC seam; 5 confirmed ADRs (ONNX Runtime GenAI, lazy-cached conversion, reused wire-codec transport, registry dispatch, narrow initial architecture set). |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Factory |
| **Status** | completed |

**Tier values**: `Direct` (no artifacts) | `Incremental` (plan/) | `Factory` (manifest.md + units/ + scenarios/) | `None` (not yet chosen)

For Factory tier, see `manifest.md`, `units/`, `scenarios/`. 6 units (`wp1`, `bd1`, `wc1`, `we1`, `br1`, `pc1`), 4 execution-order groups, 24 scenarios total (4 per unit average, every unit has at least one P0).

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-11 | Classified as Factory — solution.md describes 4+ components (backend registry, Windows execution engine, tensor/array abstraction, distributed-collectives abstraction); requirements span multiple user-facing capabilities; parallel unit work is explicit. | Classifier rationale, recorded verbatim per spec decomposition instructions. |
| 2026-09-11 | ADR-1 (solution.md): Windows inference runtime is ONNX Runtime GenAI (`onnxruntime-genai`), using the DirectML execution provider for AMD/Intel/NVIDIA and the CUDA execution provider for NVIDIA, with CPU EP as fallback — rejecting raw ONNX Runtime (no KV-cache/sampling/model-builder scaffolding), Vulkan compute (no packaged LLM runtime to build on), and a ported mlx-cuda (NVIDIA/Linux-only community fork, cannot serve the AMD/DirectML half of the epic at all). | Directly satisfies the epic's requirement to support both AMD (Radeon, via DirectML) and NVIDIA (via CUDA or DirectML) setups without vendor-specific hand-rolled runtimes, while reusing a maintained conversion/KV-cache/sampling toolchain instead of building one from scratch. |
| 2026-09-11 | Scope decision: Windows CPU-only fallback (`Backend.OnnxCpu`) is Must-Have — it is the honest floor when no GPU execution provider is available or initializes successfully, and gives the Windows CPU-Only Owner persona a working experience instead of "unsupported," matching the level of support Linux CPU-only users already receive. | Recommended default from the task brief, confirmed: a GPU-only feature would leave a real persona (older/unsupported GPU hardware, or GPU init failure) with no path to using exo on Windows at all. |
| 2026-09-11 | Scope decision: the image/diffusion engine (`engines/image/**`, `mflux`-based) is explicitly out of scope for this phase (requirements.md Won't Have; solution.md ADR-5). Windows support in this phase covers text-generation (chat completions) only. | The image engine is a second, independent MLX coupling (its own `mlx.core` imports across `builder.py`, `distributed_model.py`, `generate.py`, `pipeline/*`, `models/*`) unrelated to the text-generation `Engine`/`Builder` work this spec scopes; bundling it would roughly double the surface area for one phase with no corresponding epic requirement (the epic epic text is about "high-speed tensor parallel execution," i.e. LLM inference, not image generation). |
| 2026-09-11 | Scope decision: pipeline parallelism across Windows (and mixed Windows/MLX) nodes is Must-Have; full tensor parallelism on Windows is Should-Have, not Must-Have, for this phase. | ONNX Runtime GenAI has no first-class collective-ops primitive for tensor-parallel all-reduce, and `auto_parallel.py`'s per-architecture MLX tensor-sharding strategies cannot be reused as-is on any other backend; pipeline parallelism only needs adjacent-rank point-to-point activation hand-off, which the existing disaggregated-prefill wire-codec pattern already supports reusing (ADR-3), making it achievable in this phase while tensor parallelism honestly is not. |
| 2026-09-11 | Scope decision: initial Windows-supported model architecture set is Llama-family dense decoder architectures only (matching ONNX Runtime GenAI's model-builder tool's first-class support); MoE architectures (DeepSeek, Qwen-MoE, GLM, GPT-OSS, etc.) and broader architecture parity with MLX are Could-Have, tracked for later phases. | `auto_parallel.py`'s architecture-specific tensor-parallel sharding strategies (lines 605-1610) span many MoE-family architectures that are MLX-module-specific; attempting full parity with ONNX Runtime GenAI in one phase is not realistic, and an honest narrow launch set with a documented growth path is preferable to an overpromised broad-parity claim. |

## Context

exo is a distributed AI inference cluster (Python 3.13/uv, Rust/PyO3 for zenoh networking, Svelte 5 dashboard) that today only runs accelerated inference on macOS (MLX/Metal) and NVIDIA-on-Linux (MLX/CUDA fork); Windows cannot even install exo's inference dependencies (`pyproject.toml`'s `uv` `environments` list is Darwin/Linux-only). This spec adds Windows as a first-class inference platform — GPU-accelerated via ONNX Runtime GenAI (DirectML for AMD/Intel/NVIDIA, CUDA for NVIDIA) and CPU-accelerated as an honest fallback — without modifying any existing MLX code path. The design widens the existing `engines/base.py` `Engine`/`Builder` ABC seam with a new sibling backend (`engines/onnx/`), a backend-capability registry replacing `bootstrap.py`'s hardcoded builder selection, a rank-scoped weight-conversion/caching pipeline (safetensors → ONNX Runtime GenAI graph), and a reused wire-codec transport for cross-node pipeline-parallel activation hand-off — enabling both standalone single-node Windows operation and Windows nodes joining existing mixed-platform exo clusters.

Full requirements: `requirements.md`. Full technical design and ADRs: `solution.md`. Factory decomposition: `manifest.md`, `units/{wp1,bd1,wc1,we1,br1,pc1}.md`, `scenarios/<unit-id>/*.md`.

---
*This file is managed by the specify-meta skill.*
