# Specification: 005-windows-filesystem-state-paths

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-11 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-09-11 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 4 features (2 Must, 1 Should, 1 Could), 11 Gherkin acceptance criteria, zero open questions |
| solution.md | completed | 5 confirmed ADRs, EARS acceptance criteria fully mapped to requirements.md, single-module resolution seam in `src/exo/shared/constants.py` |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Incremental |
| **Status** | completed |

**Tier values**: `Direct` (no artifacts) | `Incremental` (plan/) | `Factory` (manifest.md + units/ + scenarios/) | `None` (not yet chosen)

For Incremental tier, see `plan/README.md` (4 phases: Platform-Aware Root Resolution, Multi-Path Parsing & Absolute-Override Regression Lock, Long-Path Packaging & Documentation, Final Integration & Cross-Platform Validation).

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-11 | Classified as Incremental — change_type=refactor, but the path-resolution change touches more than two components (constants, download utilities, Hugging Face cache resolution, info gatherer, packaging), so phase boundaries are warranted rather than Direct. | Verbatim classifier rationale used to select the decomposition tier for this spec. |
| 2026-09-11 | Config/data/cache roots split as `EXO_CONFIG_HOME → %APPDATA%\exo` (roaming), `EXO_DATA_HOME → %LOCALAPPDATA%\exo` (local), `EXO_CACHE_HOME → %LOCALAPPDATA%\exo\Cache` (local, nested) — model weights explicitly land under `%LOCALAPPDATA%`, never `%APPDATA%`. | `%APPDATA%` is the Windows convention for small, roaming, user-following configuration (a single TOML file fits); `%LOCALAPPDATA%` is the convention for machine-specific, potentially multi-hundred-gigabyte data (model weights) that must never be swept into a domain-joined roaming profile and its network sync / quota impact. Windows provides only one non-roaming per-user root, so data and cache share it via a `Cache` subfolder, matching the pattern other cross-platform Windows apps (e.g. VS Code) already use. See solution.md ADR-1. |
| 2026-09-11 | Existing Windows installations with a pre-existing `~/.exo` directory are detected and reused in place (all three roots resolve to `~/.exo`, with one INFO log line stating so) rather than silently auto-migrated to the new `%APPDATA%`/`%LOCALAPPDATA%` split, and rather than being silently left behind under a stale, invisible-to-the-new-code root. | Auto-migrating would risk an unrequested, disk-thrashing copy of tens-to-hundreds of gigabytes of model weights the user did not ask for at that moment; leaving legacy data untouched while creating a new empty root would make the user's existing downloads invisible to the fixed exo, which is worse than doing nothing. Reuse-in-place with a single log line was the explicitly recommended option in the spec brief (CONTEXT item 10b) and satisfies "no silent moves of multi-gigabyte model directories" while still telling the user where their data lives. See solution.md ADR-2. |

## Context

This specification covers Epic 5 (Windows Filesystem & State Paths): replacing the implicit "non-Linux falls through to `~/.exo`" behavior in `src/exo/shared/constants.py` with an explicit, conventional Windows split between `%APPDATA%` (roaming, small config) and `%LOCALAPPDATA%` (local, model weights/caches/logs), fixing a verified colon-vs-drive-letter parsing bug in `EXO_MODELS_DIRS`/`EXO_MODELS_READ_ONLY_DIRS`, and addressing Windows long-path limits for deeply nested Hugging Face snapshot directories — all while leaving every existing Linux and macOS environment-variable override and default behavior byte-for-byte unchanged, per the existing regression suite in `src/exo/shared/tests/test_xdg_paths.py`.

Two scope decisions were made explicit during solution design (both logged above): the exact `%APPDATA%`/`%LOCALAPPDATA%` role split, and the choice of detect-and-reuse-in-place over silent auto-migration for users who already have data under a legacy `~/.exo` on Windows. A third finding worth noting for implementers: the spec brief's design guidance suspected `EXO_HOME`/`EXO_DASHBOARD_DIR` being "resolved home-relative" would block supplying an absolute Windows override path — this was verified empirically (via `pathlib.PureWindowsPath` join semantics) to already work correctly today on both POSIX and Windows, so `plan/phase-2.md` locks that finding in with a regression test rather than proposing an unnecessary code fix.

---
*This file is managed by the specify-meta skill.*
