# Requirements: 010-placement-memory

## Problem

Tinygrad placement treats `ModelCard.storage_size` as the whole cost of a shard and treats the gatherer's `ram_available` as unused. A Windows OpenCL runner holds float16 weights and a key-value cache in a different process. The gatherer on this machine kept reporting about 16 GiB free while Qwen2.5-0.5B was loaded, so a second placement would be accepted against memory that is already reserved.

## Acceptance criteria

- [x] A card with attention heads, key-value heads, and a context length budgets float16 weights for the assigned layers, a float16 key-value cache for that context, and a temporary allowance.
- [x] A card missing any of those fields budgets only its weight bytes, so existing MLX placement tests keep their current threshold.
- [x] GGUF registration stores `num_attention_heads` from the header. The curated Qwen card stores the head count read from `qwen2.5-0.5b-instruct-q4_k_m.gguf` (14).
- [x] Tinygrad placement treats available bytes as the smaller of the reported free sample and device capacity minus the budgets of instances already in state. A second copy is refused when the first reservation consumes the node's available bytes. A free sample that already excludes that runner is not reduced a second time. Placing again with those instances removed succeeds.
- [x] MLX placement does not subtract reservations, so a node whose available bytes equal `storage_size` can still place an MLX instance.
