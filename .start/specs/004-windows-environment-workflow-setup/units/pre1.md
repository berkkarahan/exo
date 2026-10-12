---
id: pre1
title: Non-Nix pre-commit workflow documentation
type: feature
dependencies: [cfg1]
---
# Non-Nix pre-commit workflow documentation

## Goal
Document a non-Nix pre-commit command sequence for Windows contributors that approximates `nix fmt` / `nix flake check`, while stating plainly that CI remains authoritative.

## Requirements
- Create `docs/windows-precommit.md` documenting the sequence: `uv run basedpyright`, `uv run ruff check`, `uv run pytest` (citing the exact commands from AGENTS.md's "Pre-Commit Checks" section), plus `uv run ruff format` / `uv run ruff check --fix` as the closest non-Nix approximation to `nix fmt`'s ruff-format pass.
- State explicitly, per ADR-5 in solution.md, that this sequence does not cover the rustfmt, prettier, taplo, or shfmt passes that `nix fmt` runs (`flake.nix:107-131`), and that `nix flake check` in CI remains the authoritative gate for formatting and Rust tests.
- Document the `basedpyright` platform caveat: since `pyproject.toml:151` pins `pythonPlatform = "Darwin"`, running `uv run basedpyright` on Windows analyzes against Darwin semantics rather than Windows; state this is a known, accepted limitation (ADR-4) and not a bug to work around locally.
- Provide one copy-pasteable PowerShell one-liner chaining the three commands with early exit on failure (e.g., using `;` with `$LASTEXITCODE` checks or `&&`-equivalent), matching the style of AGENTS.md's existing bash "Run all checks in sequence" one-liner.

## Constraints
- Follow existing patterns (see AGENTS.md) — reuse the exact command strings already documented there; do not invent new flags.
- Must not claim the non-Nix sequence is equivalent to `nix flake check` — the "CI remains authoritative" statement is required content, not optional framing.

## Interfaces
`meta1` links to `docs/windows-precommit.md` from the README.md Windows section's contribution-workflow subsection.
