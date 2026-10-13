# Specification: 014-tinygrad-progress-deadlines

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-12 |
| **Current Phase** | Completed |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Handshake identity, progress deadlines, and the next request after cancel. |
| solution.md | completed | Direct-tier checks in the tinygrad pipeline and engine. |

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Direct |
| **Status** | completed |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-12 | Classified as Direct. One pipeline handshake payload, one budget object, and the existing runner step/submit order. | OpenCL line classification and launcher controls are already in place. The plan's remaining recovery work that can be proven without sleep or a second machine is identity, deadlines, and cancel-then-request. |
| 2026-10-12 | Handshake carries instance, rank, world size, model, protocol `tinygrad-pipeline`, and version 1. A mismatch fails `open`. | The previous handshake accepted any empty frame, so a peer on another model could exchange hidden states. |
| 2026-10-12 | Deadlines are checked around compile, prefill, decode, and each transport receive. Defaults are 600, 120, 60, and 30 seconds. | A silent peer leaves the receive loop. A clock that jumps past a budget raises before the next forward. Normal Qwen generation stays inside the defaults. |
| 2026-10-12 | Cancel-all is applied by `step`, then the runner submits the next task, which drops the cancel-all flag. | That is the order in `handle_generation_tasks`. The next task must generate. |
