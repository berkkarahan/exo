---
id: wc1
title: Windows Tensor/Array Abstraction (Weight Conversion)
type: feature
dependencies: [wp1]
---
# Windows Tensor/Array Abstraction (Weight Conversion)

## Goal

Convert an already-downloaded HuggingFace safetensors checkpoint into a rank-scoped ONNX Runtime GenAI model graph covering exactly the assigned `[start_layer, end_layer)` range, cached on disk so conversion happens at most once per `(model_id, device_rank, world_size)`.

## Requirements

- New module `src/exo/worker/engines/onnx/convert.py` exposes a function that takes a `ModelId` and a `PipelineShardMetadata` (`start_layer`, `end_layer`, `n_layers`, `device_rank`, `world_size` — `shards.py:10-84`) and returns a filesystem path to a ready-to-load ONNX Runtime GenAI model directory.
- The produced graph includes the embedding table only when `shard.is_first_layer` is true (`shards.py:35-36`), includes the LM head only when `shard.is_last_layer` is true (`shards.py:38-40`), and includes exactly the transformer layers in the half-open range `[start_layer, end_layer)` — no off-by-one inclusion/exclusion at either boundary.
- The conversion source is the safetensors data already produced by the existing shard downloader (`impl_shard_downloader.py:154-208`); this unit does not implement any new download logic.
- Converted graphs are cached under the existing model storage roots (`EXO_DEFAULT_MODELS_DIR`/`EXO_MODELS_DIRS`), keyed by `f"{model_id}-rank{device_rank}-of-{world_size}"`; a second call for the same key returns the cached path without reconverting.
- If the requested model's architecture is outside the initial supported set (Llama-family dense decoder architectures per solution.md ADR-5), the function raises a typed, catchable error rather than silently producing a broken graph or crashing with an unrelated exception.
- New module `src/exo/worker/engines/onnx/types.py` provides a thin typed wrapper around `onnxruntime_genai.Model`/`Generator` objects, following the same pattern as `engines/mlx/types.py`'s `Model` wrapper around `mlx.nn.Module` — guaranteeing the interface the rest of the Windows engine relies on (e.g. a guaranteed generation-step call shape) even though the underlying native library is not strongly typed.

## Constraints

- Follow existing patterns (see AGENTS.md) — strict typing, `frozen=True`/`strict=True` Pydantic models for any new data types, descriptive names, no abbreviations.
- Must not import or depend on `mlx`/`mlx_lm` in any way.
- Full test coverage for all requirements: tests covering first-shard (embeddings included, LM head excluded), middle-shard (neither included), last-shard (LM head included, embeddings excluded), cache-hit-returns-without-reconversion, and unsupported-architecture-raises-typed-error.

## Interfaces

`convert_for_rank(model_id: ModelId, shard: PipelineShardMetadata) -> Path` in `convert.py` — consumed by we1's `OnnxGenAiBuilder.load()`. Depends on `Backend`/enum additions from wp1 only indirectly (via shared conventions); its direct input type `PipelineShardMetadata` is pre-existing and unmodified.
