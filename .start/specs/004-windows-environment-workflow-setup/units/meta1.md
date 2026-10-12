---
id: meta1
title: README.md Windows entry point & cross-linking
type: feature
dependencies: [win1, wsl1, pre1]
---
# README.md Windows entry point & cross-linking

## Goal
Add a discoverable "Run from Source (Windows)" entry point to the top-level `README.md`, alongside the existing macOS and Linux sections, that presents the native-vs-WSL2 choice plainly and links out to the detailed docs produced by `win1`, `wsl1`, `net1`, and `pre1`.

## Requirements
- Add a new `### Run from Source (Windows)` section to `README.md`, positioned after the existing `### Run from Source (Linux)` section (matching the existing per-OS section pattern under `## Quick Start`).
- State, in the first two sentences of the new section, the support-posture guidance from requirements.md Feature 3: native Windows is the recommended default for LAN-integrated coordination; WSL2 is best-effort, recommended specifically for developers who need NVIDIA CUDA-backed inference.
- Link to `docs/windows-setup.md` (native, from `win1`), the WSL2 documentation (from `wsl1`), `docs/windows-networking.md` (from `net1`), and `docs/windows-precommit.md` (from `pre1`) — do not duplicate their content inline beyond a one-paragraph summary per path, matching the brevity of the existing macOS/Linux sections.
- Confirm (by reading, not running) that the new section does not alter any existing README.md content outside the new section's insertion point — the existing macOS and Linux sections, Environment Variables table, and API documentation must remain byte-identical.

## Constraints
- Follow existing patterns (see AGENTS.md) — match README.md's existing Markdown structure, heading levels, and code-block style exactly.
- Must not reorder or remove any existing README.md section.
- Must not introduce a table of contents change or anchor-link break to existing sections (e.g., `#run-from-source-linux` must remain a valid in-page anchor after this unit's edit).

## Interfaces
Consumes the file paths and section content produced by `win1` (`docs/windows-setup.md`, `scripts/windows/setup.ps1`), `wsl1` (WSL2 docs, `scripts/wsl2/setup.sh`), `net1` (`docs/windows-networking.md`), and `pre1` (`docs/windows-precommit.md`) as link targets; this unit does not modify any of those files' content, only `README.md`.
