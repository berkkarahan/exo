---
unit: we1
feature: Windows Execution Engine (ONNX Runtime GenAI Builder/Engine)
priority: P2
---
# GPU memory usage is visible during generation

## Scenario
On a Windows machine with a supported GPU, create and load a single-node GPU instance, then while a chat completion request is in progress, call `curl http://localhost:52415/state` (or the node memory-info equivalent).

## Expected
The response includes GPU memory/VRAM usage information for the node/instance, non-zero and consistent with the loaded model's size, rather than omitting GPU memory data entirely.
