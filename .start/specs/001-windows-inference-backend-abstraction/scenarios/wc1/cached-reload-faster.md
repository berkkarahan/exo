---
unit: wc1
feature: Windows Tensor/Array Abstraction (Weight Conversion)
priority: P1
---
# Reconverting the same model+rank on a later restart uses the cache

## Scenario
On a Windows machine, create a single-node instance for a supported model and wait for `/instance/await` to report ready. Delete the instance, restart `uv run exo`, and create the same instance again (same model, same single-node placement) while timing how long `/instance/await` takes to report ready both times.

## Expected
The second `/instance/await` "ready" event arrives materially faster than the first (conversion is not repeated).
Both runs produce a working instance that returns correct generated tokens from `/v1/chat/completions`.
