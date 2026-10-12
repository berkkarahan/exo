---
unit: bd1
feature: Windows Backend Detection
priority: P1
---
# Windows node with AMD GPU reports OnnxDirectMl backend

## Scenario
On a Windows machine with an AMD Radeon GPU and the `onnx-directml` extra installed, run `uv run exo`, then call `curl http://localhost:52415/state`.

## Expected
The response's node entry for this machine includes `"OnnxDirectMl"` in its backend/capability list.
The response includes `"OnnxCpu"` alongside it.
The response does not include `"OnnxCuda"` (no NVIDIA GPU present).
