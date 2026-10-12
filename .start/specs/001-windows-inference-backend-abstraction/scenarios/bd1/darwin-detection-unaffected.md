---
unit: bd1
feature: Windows Backend Detection
priority: P2
---
# macOS backend detection is unaffected by the Windows branch

## Scenario
On a macOS (Apple Silicon) machine, run `uv run exo`, then call `curl http://localhost:52415/state`.

## Expected
The response's node entry includes `"MlxMetal"` and `"MlxCpu"`, exactly as before this change.
The response does not include any `Onnx*` backend value.
