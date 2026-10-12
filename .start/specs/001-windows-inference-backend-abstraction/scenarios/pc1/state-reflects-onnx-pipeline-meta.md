---
unit: pc1
feature: Windows Distributed-Collectives Abstraction & Placement Integration
priority: P2
---
# Cluster state reflects the OnnxPipeline instance metadata

## Scenario
After creating a Windows-involved pipeline-sharded instance, call `curl http://localhost:52415/state`.

## Expected
The instance entry in the response has `instance_meta`/type information identifying it as `OnnxPipeline`, distinct from `MlxRing`/`MlxJaccl` instances also potentially present in the same cluster.
