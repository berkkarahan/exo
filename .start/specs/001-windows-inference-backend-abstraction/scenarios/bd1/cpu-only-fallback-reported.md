---
unit: bd1
feature: Windows Backend Detection
priority: P1
---
# Windows node with no supported GPU reports only OnnxCpu

## Scenario
On a Windows machine with no supported GPU (or with only the `onnx-cpu` extra installed), run `uv run exo`, then call `curl http://localhost:52415/state`.

## Expected
The response's node entry includes `"OnnxCpu"`.
The response does not include `"OnnxDirectMl"` or `"OnnxCuda"`.
The node starts successfully rather than erroring out for lack of a GPU.
