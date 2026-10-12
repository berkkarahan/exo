---
id: pc1
title: Windows Distributed-Collectives Abstraction & Placement Integration
type: feature
dependencies: [we1]
---
# Windows Distributed-Collectives Abstraction & Placement Integration

## Goal

Enable a Windows node to participate as one rank in a pipeline-sharded multi-node instance (alongside other Windows nodes and/or existing MLX nodes), by adding a point-to-point activation-exchange transport and the placement/coordination types the master needs to offer such placements.

## Requirements

- New `src/exo/worker/engines/onnx/collectives.py` implements point-to-point activation hand-off between adjacent pipeline ranks, reusing the existing wire tensor-blob framing pattern (`disaggregated/adapter.py`'s `array_to_bytes`/`bytes_to_array` shape and `protocol.py`-style `Header`/`write_header`/`write_done` primitives) adapted for numpy arrays instead of `mx.array`.
- `src/exo/shared/types/worker/instances.py` gains `InstanceMeta.OnnxPipeline` (added to the enum at lines 15-17, alongside `MlxRing`/`MlxJaccl`) and a new `OnnxPipelineInstance(BaseInstance)` dataclass with `hosts_by_node: dict[NodeId, list[Host]]` and `ephemeral_port: int` fields (mirroring `MlxRingInstance`, lines 28-30), and the `Instance` type alias (line 39) is extended to `MlxRingInstance | MlxJacclInstance | OnnxPipelineInstance`.
- `src/exo/master/placement.py`'s `INSTANCE_META_BACKENDS` mapping (lines 51-54) gains `InstanceMeta.OnnxPipeline: [Backend.OnnxDirectMl, Backend.OnnxCuda, Backend.OnnxCpu]`, following the same restrictive pattern as the existing `MlxJaccl: [Backend.MlxMetal]` entry — `OnnxPipeline` must never be valid for a cycle containing only MLX backends.
- `place_instance`'s `Sharding.Tensor` validation block (`placement.py:133-156`) is extended so tensor-sharding requests are rejected for cycles where any node's only available backend is an `Onnx*` value, consistent with tensor parallelism being out of scope for Windows in this phase (solution.md ADR-1 trade-off).
- A pipeline-sharded placement spanning a mix of Windows and existing MLX/Linux nodes is offered by `GET /instance/previews` and, once created, correctly hands off activations rank-to-rank regardless of which ranks are Windows vs. MLX.
- If a requested model's architecture is outside the Windows-supported initial set (wc1/ADR-5), cycles containing only Windows nodes are excluded from valid placements for that model at preview time.

## Constraints

- Follow existing patterns (see AGENTS.md) — additive-only changes to `Backend`/`InstanceMeta`/`Instance` (no renamed/removed members), matching the codebase's existing pattern-match-driven dispatch style (e.g. `match progress:` in `placement.py`).
- Must not modify `MlxRingInstance`, `MlxJacclInstance`, or the existing `INSTANCE_META_BACKENDS` entries for `MlxRing`/`MlxJaccl`.
- Full test coverage for all requirements: tests for `place_instance` correctly including/excluding Windows-containing cycles for pipeline vs. tensor sharding requests, and a round-trip test for the activation wire codec (encode/decode preserves shape and values).

## Interfaces

`InstanceMeta.OnnxPipeline`, `OnnxPipelineInstance`, and the extended `Instance` union in `instances.py`; the extended `INSTANCE_META_BACKENDS` mapping in `placement.py`; `collectives.py`'s activation send/receive functions, called by we1's `OnnxGenAiEngine.step()` when the bound shard is not the first/last pipeline rank.
