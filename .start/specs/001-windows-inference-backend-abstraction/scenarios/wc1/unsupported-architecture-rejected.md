---
unit: wc1
feature: Windows Tensor/Array Abstraction (Weight Conversion)
priority: P1
---
# Unsupported architecture is rejected, not silently broken

## Scenario
On a Windows-only single-node cluster, attempt to create an instance for a model outside the initial Windows-supported architecture set (e.g. a MoE model such as a DeepSeek or GPT-OSS variant) via `POST /instance`, or check `GET /instance/previews?model_id=<model_id>` first.

## Expected
`GET /instance/previews` either returns no valid placement for the Windows-only cycle, or `POST /instance` followed by `/instance/await` surfaces a clear error rather than hanging or crashing the node.
The error is specific enough to indicate the architecture is unsupported on this backend, not a generic/unrelated exception.
