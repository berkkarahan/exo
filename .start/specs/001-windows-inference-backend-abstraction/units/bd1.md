---
id: bd1
title: Windows Backend Detection
type: feature
dependencies: [wp1]
---
# Windows Backend Detection

## Goal

Detect which GPU execution providers (DirectML, CUDA) and CPU fallback are actually available on a Windows node at startup, and report them via the existing `NodeBackends` info-gathering mechanism so placement and the dashboard see accurate Windows capability.

## Requirements

- `src/exo/utils/info_gatherer/info_gatherer.py`'s `NodeBackends.gather()` (currently lines 372-383) gains a Windows-specific branch, structured the same way as the existing `if IS_DARWIN: backends.append(Backend.MlxMetal)` branch (line 378-379): always append `Backend.OnnxCpu` on Windows; append `Backend.OnnxCuda` if an NVIDIA GPU is detected (reusing the existing `_has_nvml_cuda()` helper already used at line 380, which is cross-platform); append `Backend.OnnxDirectMl` if a DirectX 12-capable GPU adapter (AMD, NVIDIA, or Intel) is detected via a new DXGI/D3D12 adapter-enumeration probe.
- A node only advertises `OnnxDirectMl`/`OnnxCuda` capability if the corresponding runtime actually initializes successfully during the probe — never advertise capability that later fails to deliver (PRD Business Rule 1).
- The detection probe must not import `onnxruntime_genai` (a heavy native library) merely to enumerate adapters; use a lightweight DXGI enumeration check so `gather()` stays cheap, consistent with the existing lightweight `_has_nvml_cuda()` check pattern.
- Non-Windows platforms (`IS_DARWIN`, Linux) are completely unaffected — this unit adds a branch, it does not restructure the existing Darwin/CUDA branches.
- `GET /state` (or the equivalent node-info surface `NodeBackends` feeds) reflects the detected Windows `Backend` values for a running Windows node.

## Constraints

- Follow existing patterns (see AGENTS.md) — mirror the `IS_DARWIN`/`_has_nvml_cuda()` branch structure exactly; async-thread-offload pattern (`await to_thread.run_sync(...)`, line 380) for any blocking probe call.
- Do not modify the Darwin or existing CUDA-detection branches.
- Full test coverage for all requirements: unit tests for the new detection branch under mocked "GPU present"/"GPU absent"/"probe fails" conditions.

## Interfaces

Extends `NodeBackends.gather()` (async classmethod, unchanged signature) in `src/exo/utils/info_gatherer/info_gatherer.py`. Consumes `Backend.OnnxDirectMl`/`OnnxCuda`/`OnnxCpu` from wp1. Its output (the `list[Backend]` a node reports) is consumed by br1 (registry dispatch) and pc1 (placement's `INSTANCE_META_BACKENDS` filtering).
