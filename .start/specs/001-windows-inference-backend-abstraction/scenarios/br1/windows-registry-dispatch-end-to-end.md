---
unit: br1
feature: Backend Registry
priority: P0
---
# Windows node dispatches to the ONNX Runtime GenAI builder end-to-end

## Scenario
On a Windows machine, run `uv run exo`, create a single-node text-generation instance for a supported model, and send a `POST /v1/chat/completions` request.

## Expected
The request returns correctly generated tokens (proving the runner's registry lookup selected and correctly constructed the Windows builder for this node's detected backend, since no other builder can produce a working generation on Windows).
No exception referencing an MLX-specific import or type appears in the node's logs.
