---
unit: pc1
feature: Windows Distributed-Collectives Abstraction & Placement Integration
priority: P1
---
# Tensor sharding is not offered for a Windows-only cycle

## Scenario
With two Windows nodes discovered in the cluster (no macOS/Linux nodes), call `curl "http://localhost:52415/instance/previews?model_id=<tensor-shardable-model>"`.

## Expected
No entry in `previews` has both `"sharding": "Tensor"` and an all-Windows node set with `"error": null`; any such combination is either absent or returned with a non-null `error` explaining tensor sharding is unsupported on this backend.
