---
id: cfg1
title: Platform-support configuration fix
type: fix
dependencies: []
---
# Platform-support configuration fix

## Goal
Unblock `uv sync` on native Windows by adding a Windows marker to `pyproject.toml`'s `[tool.uv] environments` list, without changing which extras resolve on which platform.

## Requirements
- Add `"sys_platform == 'win32'"` to the `environments` list at `pyproject.toml:188`, alongside the existing `"sys_platform == 'darwin'"` and `"sys_platform == 'linux'"` entries.
- Do not modify any `sys_platform` marker on the `mlx`, `mlx-cpu`, `mlx-cuda12`, or `mlx-cuda13` extras (`pyproject.toml:47-111`) — they must remain resolvable only on `darwin`/`linux` exactly as today.
- Do not modify `pyproject.toml:151-152` (`tool.basedpyright.pythonPlatform = "Darwin"`) — CI's basedpyright platform stays pinned to Darwin per ADR-4 in solution.md.
- Add a short comment above `pythonPlatform = "Darwin"` noting that Windows contributors running `basedpyright` locally will see it analyze against Darwin semantics, with a pointer to `docs/windows-setup.md` for the explanation (comment only, no behavior change).
- Verify (by reading, not running `uv sync` — no build/test commands allowed per task constraints) that the base dependency list (`pyproject.toml:7-30`) has no `sys_platform`-gated entries that would break on Windows resolution; document any found as a known gap rather than silently working around them.

## Constraints
- Follow existing patterns (see AGENTS.md) — strict, minimal diff; this is a two-line `pyproject.toml` change plus one comment, not a refactor.
- Must not change `python-daemon` (`pyproject.toml:29`) or any other existing dependency line.
- Must not add a new `mlx`-family extra or Windows-specific inference dependency — that is out of scope (specs 001/003).
- No build/test commands may be run to verify this unit within spec authoring; verification is by direct file inspection matching solution.md's Implementation Examples diff.

## Interfaces
Downstream units (`win1`, `wsl1`) depend on this unit's `environments` list change being present before their `uv sync` / `uv sync --extra ...` documentation and scripts reference it as working.
