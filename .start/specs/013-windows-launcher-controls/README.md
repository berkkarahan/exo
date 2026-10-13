# Specification: 013-windows-launcher-controls

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-12 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Stop, restart, close, saved device settings, and separate status lines. |
| solution.md | completed | Direct-tier controller beside the existing Start window. |

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Direct |
| **Status** | completed |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-12 | Classified as Direct. One controller and the existing window. | Start already spawns `python -m exo`. The missing behavior is stopping that tree, restoring the last device, and showing process, API, and device separately. |
| 2026-10-12 | Stop uses `taskkill /T /F` on Windows. | `Popen.terminate` ends the parent and leaves runner children. The pidfile lock is released when the process exits. |
| 2026-10-12 | Settings store the device name, the row label, and the memory limit. | Two AMD adapters share the device name `AMD`. The label is what the dropdown restores. |
| 2026-10-12 | Firewall and driver-version reporting stay out of this slice. | The dropdown already names the adapter. Firewall rules are a separate Windows capability. |
