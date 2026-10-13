---
name: sync-upstream
description: Sync new development from the upstream exo-explore/exo repository into this wEXO fork by merging upstream/main, resolving conflicts without breaking wEXO's intentional changes. Use when the user asks to pull in, merge, rebase on, or update from upstream/main or the main exo branch.
---

# Sync Upstream exo -> wEXO Fork

This repository is a fork of `exo-explore/exo` (wEXO). Keep it current with upstream while preserving
the fork's intentional differences.

## Remotes

- `origin` -> `https://github.com/berkkarahan/exo.git` (this fork; push here)
- `upstream` -> `https://github.com/exo-explore/exo.git` (the main exo branch; never push here)

Confirm before starting:

```bash
git remote -v
git branch --show-current   # expect: main
```

## Workflow

1. **Fetch** the latest:
   ```bash
   git fetch upstream
   git log --oneline --no-decorate HEAD..upstream/main | head
   ```
2. **Merge** (never rebase) upstream into the local branch:
   ```bash
   git merge upstream/main
   ```
3. **No conflicts** -> run the full gate, then push:
   ```bash
   uv run basedpyright && uv run ruff check && nix fmt && uv run pytest
   git push origin main
   ```
4. **Conflicts** -> do **not** guess or blindly take one side. For each conflicting file:
   - Inspect the upstream change and its intent:
     ```bash
     git log --oneline upstream/main -- <file> | head
     git diff HEAD...upstream/main -- <file>
     ```
   - **Launch sub-agents** (`explore` to understand each side, `general` to reconcile and implement)
     so the upstream change is preserved and functional **and** the fork's intentional wEXO changes
     remain intact.
   - Re-run the full gate, then push.

## Preserve the fork's intentional wEXO changes

These are deliberate rebrand/fork differences - keep them when resolving conflicts:

- wEXO branding and logos (e.g. `dashboard/wEXO-logo*.png`, `dashboard/static/`, dashboard titles,
  `wEXO-*` Tailwind color tokens in `dashboard/src/`).
- The wEXO home/data directory `~/.wexo` (`EXO_HOME=.wexo`, `src/exo/shared/constants.py`).
- Fork-specific packaging names (`wexo` in `packaging/pyinstaller/exo.spec`) and the macOS app
  (`app/EXO/`).
- The zenoh default namespace `wEXO` (`src/exo/main.py`).

If an upstream change appears to conflict with one of these, prefer the upstream behavior in the
engine/protocol and re-apply the wEXO presentation/identity layer on top - do not silently drop
either side.

## Guardrails

- Never force-push; never push to `upstream`.
- Verify `origin` points at `berkkarahan/exo` before pushing.
- Pause and confirm with the user before overwriting any fork-local-only change that looks intentional
  but is unclear.
- Do not leave the merge half-resolved: resolve, run the gate, or `git merge --abort` and report.
