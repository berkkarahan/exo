# Specification: 009-gguf-model-card

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-12 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | A GGUF-only repository can become a model card that places on WinAMD. |
| solution.md | completed | Direct-tier design: one file, header metadata, realized float16 budget. |

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Direct |
| **Status** | completed |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-12 | Classified as Direct. One registration path plus the download filter that makes that filename the weight payload. | The parked plan's workflow item is one vertical slice. Dashboard selection stays a later item. |
| 2026-10-12 | `storage_size` is the larger of the file size and the float16 size of tensors the loader can place. | Placement treats `storage_size` as the memory budget. Quantized GGUF expands to float16 in tinygrad. |
| 2026-10-12 | Split GGUF sets are rejected. One `gguf_filename` downloads one file. | The loader globs every `*.gguf` in the directory, so a partial split set would be read as the model. |
| 2026-10-12 | A safetensors index still wins unless the caller passes `gguf_filename`. | Existing custom-model registration keeps its current card. |
