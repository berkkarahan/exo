# Specification: 010-placement-memory

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-12 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Tinygrad placement reserves resident shards before accepting another. |
| solution.md | completed | Direct-tier budget: float16 weights, KV cache, temporary allowance. |

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Direct |
| **Status** | completed |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-12 | Classified as Direct. One budget function and the Tinygrad branch of `place_instance`. | The gatherer already reports OpenCL capacity. The missing piece is the reservation placement consults. |
| 2026-10-12 | Available memory for a Tinygrad placement is the smaller of the reported free sample and device capacity minus resident budgets. | A loaded runner is another process. On this machine `CL_DEVICE_GLOBAL_FREE_MEMORY_AMD` stayed near the device total while Qwen was resident. NVIDIA's free-memory sample already excludes other processes, so subtracting the reservation from that sample would count the model twice. |
| 2026-10-12 | The KV term uses the card's context length, key-value heads, and attention heads at float16. Cards without those fields keep today's weight-only budget. | The tinygrad cache stores keys and values in the activation dtype, which this backend realizes as float16. MLX cards that omit attention heads must not change. |
| 2026-10-12 | A temporary allowance of one eighth of the shard's weight bytes is added only when the KV term is non-zero. | Dequantization and the forward pass allocate workspace beyond the weights. The fraction is a ceiling, not a measured peak. |
