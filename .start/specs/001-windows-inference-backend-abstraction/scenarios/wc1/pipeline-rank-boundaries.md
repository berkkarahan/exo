---
unit: wc1
feature: Windows Tensor/Array Abstraction (Weight Conversion)
priority: P2
---
# First and last pipeline-rank shards produce correct end-to-end output

## Scenario
Across a two-node cluster including at least one Windows node, place a supported model with `Sharding: Pipeline` via `POST /instance` splitting layers across two ranks, then send `POST /v1/chat/completions` against the resulting instance.

## Expected
The response contains correctly generated, coherent tokens (not garbage/empty output), demonstrating the first-rank shard correctly included embeddings and excluded the LM head, and the last-rank shard correctly did the reverse.
