---
id: we1
title: Windows Execution Engine (ONNX Runtime GenAI Builder/Engine)
type: feature
dependencies: [wp1, wc1]
---
# Windows Execution Engine (ONNX Runtime GenAI Builder/Engine)

## Goal

Implement the `Builder`/`Engine` ABC pair (`engines/base.py:16-60`) for Windows, using ONNX Runtime GenAI with DirectML/CUDA/CPU execution-provider selection, so a Windows node can load and serve text-generation chat completions exactly like the existing MLX engine does.

## Requirements

- New `src/exo/worker/engines/onnx/builder.py` defines `OnnxGenAiBuilder(Builder)` implementing `connect(bound_instance)`, `load(bound_instance) -> Generator[ModelLoadingResponse]`, `build() -> Engine`, `close()` — matching `MlxBuilder`'s structure (`engines/mlx/builder.py:32-113`) but backed by `onnxruntime_genai` instead of `mlx`.
- `connect()` selects and initializes the appropriate execution provider (DirectML, CUDA, or CPU) based on the node's detected `Backend` value; if initialization fails, it raises a typed error rather than silently degrading (PRD Business Rule 2) — this is where DirectML/CUDA availability is actually exercised, not just probed (bd1 only probes cheaply for `gather()`).
- `load()` calls wc1's `convert_for_rank()` (or its cache) to obtain the rank-scoped ONNX Runtime GenAI model directory, then loads it, yielding `ModelLoadingResponse` progress updates the same way `utils_mlx.py`'s load path does (layer-count progress).
- New `src/exo/worker/engines/onnx/engine.py` defines `OnnxGenAiEngine(Engine)` implementing `warmup()`, `submit(task)`, `step() -> Iterable[tuple[TaskId, Chunk | CancelledResponse | FinishedResponse]]`, `close()`, `serve_prefill(request, wfile)` — driving `onnxruntime_genai.Generator.generate_next_token()` per call to `step()` and yielding `Chunk` text output.
- Single-node (world_size=1) generation works end-to-end: a chat completion request against a Windows-only instance returns correctly generated tokens.
- CPU-only operation works identically when only `Backend.OnnxCpu` is available (no GPU EP), satisfying the CPU-fallback requirement without any separate code path — the same `OnnxGenAiEngine` class serves both, differing only in which execution provider was selected at `connect()` time.

## Constraints

- Follow existing patterns (see AGENTS.md) — exact ABC method signatures from `engines/base.py:16-60` must not be altered; this unit implements them, does not change them.
- Must not import `mlx`/`mlx_lm`.
- Runs inside the existing per-shard isolated `AsyncProcess` runner (`supervisor.py:181-274`) unchanged — this unit does not touch `supervisor.py` or `runner.py`.
- Full test coverage for all requirements: tests for the `connect()`/`load()`/`build()` lifecycle with a mocked `onnxruntime_genai`, and for `step()` yielding correctly shaped `Chunk` objects.

## Interfaces

`OnnxGenAiBuilder(Builder)` and `OnnxGenAiEngine(Engine)`, matching `engines/base.py:16-60` exactly. Consumed by br1 (registered as the Windows entry in the Backend Registry) and by pc1 (which adds the activation-exchange hooks this engine calls during pipeline-sharded generation).
