# Specification: 011-dashboard-tinygrad-runtime

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-12 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | The dashboard can select and display a Tinygrad instance. |
| solution.md | completed | Direct-tier: preview generation plus the existing runtime controls. |

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Direct |
| **Status** | completed |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-12 | Classified as Direct. One preview combination and the dashboard runtime union. | Placement already accepts `InstanceMeta.Tinygrad`. The UI drops that tag and never asks for it. |
| 2026-10-12 | A cluster whose backends are only Tinygrad or Windows identities defaults the runtime to Tinygrad and Pipeline. | `MlxRing` cannot place a GGUF card on WinAMD. The stored MLX default would make the launch button look available and then fail. |
| 2026-10-12 | Preview generation adds Tinygrad with Pipeline only. | Tinygrad placement rewrites Tensor to Pipeline, so a Tensor combination would duplicate the Pipeline preview. |
| 2026-10-12 | When both an MLX Pipeline preview and a Tinygrad preview are valid, the automatic chat launch still prefers MLX. | Apple clusters keep today's choice. Tinygrad is the placement used when no MLX preview is valid. |
| 2026-10-12 | `device_backend_by_node` accepts a backend name before enum validation. | The dashboard posts the preview JSON back to `POST /instance`. A strict enum field rejects the name `WinAMD`. |
