---
title: "Windows Environment & Workflow Setup"
status: pending
threshold: 0.90
max_iterations: 5
---
# Decomposition Manifest

## Units
- [ ] cfg1: Platform-support configuration fix (pyproject.toml) — no dependencies
- [ ] net1: Networking mode & port reference documentation — no dependencies
- [ ] pre1: Non-Nix pre-commit workflow documentation — after: cfg1
- [ ] win1: Native Windows setup (script + docs + README section) — after: cfg1, net1
- [ ] wsl1: WSL2 setup with GPU passthrough (script + docs + README section) — after: cfg1, net1
- [ ] meta1: README.md Windows entry point & cross-linking — after: win1, wsl1, pre1

## Execution Order
Group 1 (parallel): cfg1, net1
Group 2 (parallel): pre1, win1, wsl1
Group 3 (sequential): meta1
