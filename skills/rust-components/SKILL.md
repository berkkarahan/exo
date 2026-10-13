---
name: rust-components
description: Develop and rebuild wEXO's Rust crates (zenoh networking, exo_rs PyO3 bindings, system custodian) and verify them with just/cargo/nix. Use when editing rust/, changing PyO3 bindings exposed to Python, or working on peer discovery and networking.
---

# Rust Components

Rust is a Cargo workspace under `rust/`:

- `rust/networking` - zenoh networking: gossipsub, peer discovery, connection messages.
- `rust/exo_rs` - PyO3 bindings exposing Rust to Python (`import exo_rs`).
- `rust/system_custodian` - privileged system-level operations.

## Rebuild after changing Rust or PyO3 signatures

After editing `exo_rs` (especially the Python-facing surface), regenerate stubs and reinstall the
extension so Python picks it up:

```bash
just rust-rebuild
# expands to:
#   PYO3_PYTHON="$(uv run python -c 'import sys; print(sys.executable)')" cargo run --bin stub_gen
#   uv sync --reinstall-package exo_rs
```

## Verify

```bash
cargo test              # crate-level tests
nix flake check         # format + lint + Rust tests, matching CI
nix flake show          # list buildable outputs, then `nix build .#<output>`
```

## Notes

- Keep the Python-facing surface typed and minimal; the Python side runs under strict `basedpyright`.
- After embedding changes, run the pre-commit gate (see the `pre-commit-checks` skill) so Python
  callers still type-check and pass.
- Dependencies: do not add new crates without asking (see `RULES.md`).
