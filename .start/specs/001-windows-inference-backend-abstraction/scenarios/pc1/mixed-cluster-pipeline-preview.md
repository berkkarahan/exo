---
unit: pc1
feature: Windows Distributed-Collectives Abstraction & Placement Integration
priority: P0
---
# Mixed Windows+Mac cluster offers a pipeline placement spanning both

## Scenario
With a macOS/Linux exo node and a Windows exo node running on the same network (both discovered, visible in `GET /state`), call `curl "http://localhost:52415/instance/previews?model_id=<pipeline-shardable-model>"`.

## Expected
At least one entry in `previews` has `"sharding": "Pipeline"`, `"instance_meta": "OnnxPipeline"`, and a memory/placement breakdown spanning both the Windows node and the macOS/Linux node.
The entry has `"error": null`.
