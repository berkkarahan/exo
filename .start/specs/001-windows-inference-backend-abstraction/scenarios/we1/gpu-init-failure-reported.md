---
unit: we1
feature: Windows Execution Engine (ONNX Runtime GenAI Builder/Engine)
priority: P1
---
# GPU execution-provider initialization failure is reported, not silent

## Scenario
On a Windows machine where the GPU driver is missing, outdated, or otherwise fails DirectML/CUDA initialization (simulated by disabling/uninstalling the GPU driver, or forcing initialization failure via a test configuration), attempt to create and load a single-node instance that would otherwise use GPU acceleration.

## Expected
The instance does not report `"ready"` with silently incorrect behavior; either the load fails with a clear error surfaced via `/instance/await` (a non-"ready" terminal event), or the node visibly falls back to CPU and this is reflected in `/state` — not a hang, not a crash with an unrelated stack trace.
