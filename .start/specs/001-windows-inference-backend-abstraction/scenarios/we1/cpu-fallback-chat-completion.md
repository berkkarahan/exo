---
unit: we1
feature: Windows Execution Engine (ONNX Runtime GenAI Builder/Engine)
priority: P0
---
# CPU-only chat completion returns correct tokens

## Scenario
On a Windows machine with no supported GPU (or the `onnx-cpu` extra only), create a single-node instance for a Must-Have-architecture model, then send `POST /v1/chat/completions` with a simple prompt.

## Expected
The response returns correctly generated, coherent tokens.
Generation completes (does not hang) within a reasonable time for a small model on CPU.
The `/state` endpoint shows the node's backend as `OnnxCpu`.
