---
unit: bd1
feature: Windows Backend Detection
priority: P0
---
# Windows node with NVIDIA GPU reports OnnxCuda backend

## Scenario
On a Windows machine with an NVIDIA GPU and the `onnx-cuda` extra installed, run `uv run exo`, then call `curl http://localhost:52415/state`.

## Expected
The response's node entry for this machine includes `"OnnxCuda"` in its backend/capability list.
The response also includes `"OnnxCpu"` (CPU fallback is always reported alongside GPU capability).
The response does not include any Darwin-only backend value (`MlxMetal`).
