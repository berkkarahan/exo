# Specification: 016-launcher-driver-version

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-12 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | draft | Show the OpenCL driver on the launcher row and status line. |
| solution.md | draft | Match WMI adapter names to enumerated OpenCL driver strings. |

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Direct |
| **Status** | in-progress |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-12 | Classified as Direct. One optional driver string on the existing device row. | The launcher lists adapter names. OpenCL enumeration already reads `CL_DRIVER_VERSION`, and the status line does not show it. |
| 2026-10-12 | The saved label stays the adapter name. The driver is display-only. | Two AMD rows share `device_name`. Changing the saved label would restore the wrong GPU after the caption gains a version. |
| 2026-10-12 | A name that maps to more than one driver version shows no version. | Duplicate platforms with different drivers must not pick one silently. |
