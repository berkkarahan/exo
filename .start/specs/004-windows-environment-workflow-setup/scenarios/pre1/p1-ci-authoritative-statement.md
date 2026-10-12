---
unit: pre1
feature: windows-environment-workflow-setup
priority: P1
---
# Document states CI remains authoritative and names the formatting gap

## Scenario
Read the closing paragraph of `docs/windows-precommit.md`.

## Expected
The document explicitly states that `nix flake check` (run in CI) remains the authoritative gate.
The document names, by tool, which formatting passes the local non-Nix sequence does NOT cover (at minimum: rustfmt, prettier, taplo, shfmt), rather than a vague "some things aren't covered" statement.
