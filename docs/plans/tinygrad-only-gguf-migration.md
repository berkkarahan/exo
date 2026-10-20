# Tinygrad-Only GGUF Inference Migration Plan

> **For Hermes:** Execute incrementally; each code slice requires failing-first tests.

**Goal:** Make tinygrad the sole inference runtime and serve any GGUF model.

**Architecture:** Retain exo's placement, runner, and API lifecycle while migrating model discovery and default placement to Tinygrad, then removing MLX/image/vLLM inference paths and dependencies where appropriate. Grow GGUF coverage through explicit architecture adapters and numerical/integration tests; GGUF is a weight/container format, not a universal model graph.

**Tech Stack:** Python, tinygrad, GGUF, FastAPI, pytest.

---

## Milestones

1. **Tinygrad is the default for newly gathered nodes and omitted API placement choices.** Add tests for Darwin/Linux backend discovery defaults, declared-device overrides, CPU fallback, API parameter defaults, and API placement commands. Update runtime-sensitive monitoring along with discovery. Preserve explicit MLX selection only as a temporary compatibility path until legacy removal is planned.
2. **Tinygrad is the sole inference engine.** Remove implicit MLX builder fallback only after migration policy for existing `MlxRing`/`MlxJaccl` placements is specified and covered. Inventory and resolve image (mflux/MLX), ONNX, vLLM, dependencies, catalog backends, dashboard controls, and startup imports without routing incompatible instance types to Tinygrad.
3. **GGUF support expands by tested architecture and quantization.** Inventory GGUF metadata, tensor mapping, forward semantics, tokenizer/chat templates, and quantization support; implement one architecture vertical-slice at a time. Do not alias unsupported model types to Llama. Pin tinygrad to the API range actually tested.
4. **Serve and validate.** Add a real HTTP lifecycle test using a small local GGUF fixture, then test representative community GGUF models across supported architectures and quantizations. Universal GGUF acceptance requires documenting/handling architecture constraints; a generic GGUF file cannot be assumed to encode an executable graph supported by tinygrad.

## This iteration's verification context

The repository already contains Tinygrad checkpoint, GGUF tokenizer/weights, generation, pipeline, and engine implementations; current model-type allowlist is Llama, Qwen2, and Qwen3. `tinygrad` 0.14.0 imports in the project `uv` environment. On this Windows host, Tinygrad CPU tests initially failed because the process `PATH` contains an inaccessible system-profile WindowsApps entry; excluding exactly that entry from the test subprocess made all 27 checkpoint/generation tests pass. This is a test-environment workaround, not proof of a permanent runtime fix.
