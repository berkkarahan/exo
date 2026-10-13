---
name: pre-commit-checks
description: Run the required wEXO pre-commit gate (basedpyright, ruff, nix fmt, pytest) before committing, pushing, or opening a PR. Use when the user asks to commit, push, or open a PR, or when finishing a code change that must pass CI.
---

# Pre-Commit Checks

CI (`.github/workflows/pipeline.yml`) runs `nix flake check` (format + lint + Rust tests) plus pytest.
A change is not done until the local gate passes.

## Run the gate in order

```bash
uv run basedpyright        # strict type check - MUST be 0 errors
uv run ruff check          # lint - MUST pass
nix fmt                    # format (treefmt); use `just fmt` if nix is unavailable
uv run pytest              # tests (slow tests excluded by default)
```

One-liner:

```bash
uv run basedpyright && uv run ruff check && nix fmt && uv run pytest
```

Equivalent `just` targets: `just lint` (`ruff check --fix`), `just fmt`, `just check` (basedpyright), `just test`.

## Gotchas

- `nix fmt` may rewrite files. If it does, **stage the formatting changes** before committing.
- `uv run pytest` excludes slow tests; run everything with `uv run pytest -m ""`.
- Single test: `uv run pytest src/exo/shared/tests/test_election.py::test_name`.
- `nix fmt` needs the dev shell (`.envrc`/direnv). If unavailable, `just fmt` falls back to `treefmt` then `nix fmt`.
- CI only runs pytest on macOS; do not assume a green Linux run covers tests.
