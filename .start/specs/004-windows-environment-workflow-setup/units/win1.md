---
id: win1
title: Native Windows setup (script + docs)
type: feature
dependencies: [cfg1, net1]
---
# Native Windows setup (script + docs)

## Goal
Give a Windows developer an idempotent, detect-and-instruct PowerShell setup script plus documentation that gets them from a clean Windows 11/10 machine to a running, LAN-reachable exo coordinator.

## Requirements
- Create `scripts/windows/setup.ps1`: an idempotent PowerShell script that checks for Python 3.13 (exact minor version, matching `pyproject.toml:6`'s `==3.13.*` pin), uv, Node.js, and a Rust toolchain capable of building `exo_rs` with MSVC (`rust/exo_rs/pyproject.toml:1-3,20-22`). For each missing/mismatched prerequisite, print a clear message plus the exact `winget install --id <id> -e` command; only execute the `winget install` when the script is invoked with an explicit opt-in switch (e.g., `-InstallMissing`), per ADR-3 in solution.md.
- Detect the MSVC "Desktop development with C++" workload specifically (not just `cargo`/`rustc` presence), since a Rust toolchain can be installed without it and will fail to link `exo_rs`; document the specific fix instruction for this case (requirements.md Feature 1 Edge Case 2).
- Re-running the script after a successful run must re-report all prerequisites as present and exit 0 without side effects (idempotency, requirements.md Feature 1 Edge Case 3).
- Create the "Run from Source (Windows)" section of `docs/windows-setup.md`: dashboard build (`cd dashboard; npm install; npm run build; cd ..`, unmodified from the existing macOS/Linux instructions since Node/npm behave identically), `uv sync` (relying on `cfg1`'s fix), `uv run exo`, and the documented smoke check (`http://localhost:52415` loads, `curl http://localhost:52415/v1/models` responds).
- State plainly, in the same section, that `--legacy-daemon` (`src/exo/main.py:290-319`) is unsupported on native Windows because it depends on the POSIX-only `python-daemon` package (`pyproject.toml:29`), and that native Windows currently has no GPU-backed inference path (MLX is Darwin/Linux-only) — the coordinator runs CPU/coordinator-class until specs 001/003 land.
- Link to `docs/windows-networking.md` (from `net1`) for the LAN discovery/port behavior rather than re-describing it.

## Constraints
- Follow existing patterns (see AGENTS.md) — match the tone and structure of `README.md`'s existing macOS/Linux "Run from Source" sections.
- Full coverage for all requirements: every Must Have Gherkin criterion under requirements.md Feature 1 must be satisfiable by following this unit's documentation and script.
- Must not add Windows-native GPU inference support — document the CPU/coordinator-only limitation instead of working around it.

## Interfaces
Depends on `cfg1`'s `pyproject.toml` fix being in place for `uv sync` to succeed, and on `net1`'s `docs/windows-networking.md` for the port/mode reference it links to. `meta1` links to this unit's README.md section and `docs/windows-setup.md`.
