# Specification: 004-windows-environment-workflow-setup

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-11 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-09-11 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | PRD covering native-Windows and WSL2 setup, business-level, zero NEEDS CLARIFICATION markers |
| solution.md | completed | SDD covering the pyproject.toml platform-support fix, native/WSL2 setup scripts, networking-mode reference, and non-Nix pre-commit workflow |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decomposition

| Field | Value |
|-------|-------|
| **Tier** | Factory |
| **Status** | completed |

**Tier values**: `Direct` (no artifacts) | `Incremental` (plan/) | `Factory` (manifest.md + units/ + scenarios/) | `None` (not yet chosen)

For Incremental tier, see `plan/README.md`.
For Factory tier, see `manifest.md`, `units/`, `scenarios/`.
For Direct tier, no decomposition artifacts are produced — implement-direct reads requirements.md and solution.md directly.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-11 | Decomposition tier: Factory | Classified as Factory — two independent user-facing setup paths (native Windows and WSL2 with GPU passthrough) plus build-configuration and documentation workstreams that can proceed in parallel. |
| 2026-09-11 | Native Windows is the supported default path; WSL2 is best-effort | Native Windows gives real LAN-level peer discovery (`rust/networking/src/discovery.rs:18,46-78`'s IPv6 UDP multicast is not NAT-blocked) and is the path every other exo Windows-adjacent spec (001/002/005/006) will eventually target directly. WSL2 gives immediate access to exo's already-tested Linux dependency markers and CUDA extras (`pyproject.toml:47-72`) but sits behind a NAT boundary by default, so LAN peer discovery does not work there unless mirrored networking mode is configured. Native Windows currently has no GPU-backed inference path (MLX is Darwin/Linux-only), so it is coordinator/CPU-class only until specs 001/003 land — this trade-off is stated plainly, not hidden. |
| 2026-09-11 | Windows setup scripts detect and instruct by default; installing prerequisites via winget is opt-in | The setup script does not silently install system-level toolchains (Python, Rust/MSVC, Node.js, uv) without the developer's explicit action. Default behavior is to detect each prerequisite and print pass/fail plus the exact `winget install --id <id> -e` command for anything missing; automated installation only happens when the developer explicitly opts in (e.g., a `-InstallMissing` switch). This avoids silently modifying a developer's existing toolchain installs and matches the project's existing style of manual, copy-paste setup instructions (README.md's macOS/Linux sections). |

## Context

Epic 4: "As a developer, I want the flexibility to run the exo coordinator natively on Windows or containerized via WSL2 (with GPU passthrough) so that it integrates smoothly with my existing local LLM workflows and tooling." The two concrete blockers that make this currently impossible are both in `pyproject.toml`: the `[tool.uv] environments` list (`pyproject.toml:188`) excludes `sys_platform == 'win32'` entirely, so `uv sync` cannot resolve on native Windows at all, and `[tool.basedpyright] pythonPlatform` (`pyproject.toml:151`) is hardcoded to `"Darwin"`, so the documented type-check command analyzes against the wrong platform for a Windows contributor. This spec's solution fixes both narrowly (adding a Windows marker to the base `environments` list only, leaving every Darwin/Linux-only MLX/torch extra marker untouched) and then documents two clearly-scoped setup paths — native Windows (recommended default, real LAN discovery, no GPU inference yet) and WSL2 (best-effort, reuses the existing Linux/CUDA dependency path, but requires `.wslconfig` mirrored networking mode for LAN peer discovery since default NAT mode blocks the IPv6 UDP multicast discovery mechanism). The spec explicitly excludes the inference backend itself (spec 001), telemetry internals (spec 002), path relocation (spec 005), and service/tray packaging (spec 006), referencing them as dependencies rather than duplicating their scope.

Decomposed into 6 Factory units: `cfg1` (pyproject.toml platform-support fix), `net1` (networking mode & port reference doc), `pre1` (non-Nix pre-commit workflow doc), `win1` (native Windows setup script + docs), `wsl1` (WSL2 setup script + docs), and `meta1` (README.md Windows entry point). Execution order: Group 1 (parallel) `cfg1`, `net1`; Group 2 (parallel) `pre1`, `win1`, `wsl1`; Group 3 (sequential) `meta1`.

---
*This file is managed by the specify-meta skill.*
