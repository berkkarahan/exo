---
id: wsl1
title: WSL2 setup with GPU passthrough (script + docs)
type: feature
dependencies: [cfg1, net1]
---
# WSL2 setup with GPU passthrough (script + docs)

## Goal
Give a Windows developer with an NVIDIA GPU an idempotent, detect-and-instruct Bash setup script plus documentation that gets them from a clean WSL2 Ubuntu distribution to a running exo coordinator with GPU passthrough, reusing exo's existing Linux dependency path.

## Requirements
- Create `scripts/wsl2/setup.sh`: an idempotent Bash script (run inside WSL2 Ubuntu) that checks for Python 3.13, uv, Node.js, and a Rust toolchain (matching the existing README.md Linux instructions' `curl ... rustup.rs` install), and detects an NVIDIA GPU via `nvidia-smi` to recommend `uv sync --extra mlx-cuda12` or `mlx-cuda13` (matching the developer's installed CUDA version) versus `uv sync --extra mlx-cpu` if no GPU is detected.
- Re-running the script after a successful run must re-report all prerequisites as present and exit 0 without side effects (idempotency, mirroring requirements.md Feature 1 Edge Case 3's expectation applied to the WSL2 path).
- Create the "Run from Source (WSL2)" section of `docs/windows-setup.md` (or `docs/wsl2-setup.md`, linked from `docs/windows-setup.md`): WSL2 distribution prerequisite (standard `wsl --install`, referenced not duplicated per requirements.md Assumptions), GPU passthrough prerequisite (current NVIDIA CUDA driver for WSL2 on the Windows host, exposing `/dev/dxg`), dashboard build (unmodified), `uv sync --extra mlx-cuda12`/`mlx-cuda13`/`mlx-cpu`, `uv run exo`, and the documented smoke check reachable from the Windows host browser via `localhost` forwarding.
- Cite `src/exo/utils/info_gatherer/info_gatherer.py:372-383` as the existing NVML-based CUDA detection code exo already uses, confirming no exo code changes are needed for GPU passthrough to work once the WSL2 NVIDIA driver is present.
- Link to `docs/windows-networking.md` (from `net1`) for the WSL2 default-NAT-vs-mirrored-mode port matrix rather than re-describing it; state in this unit's section only the one-line summary that "peer discovery from WSL2 to other LAN machines requires mirrored networking mode — see docs/windows-networking.md."

## Constraints
- Follow existing patterns (see AGENTS.md) — match the tone and structure of `README.md`'s existing Linux "Run from Source" section, since WSL2 Ubuntu setup is nearly identical to it.
- Full coverage for all requirements: every Must Have Gherkin criterion under requirements.md Feature 2 must be satisfiable by following this unit's documentation and script.
- Must not modify `src/exo/utils/info_gatherer/info_gatherer.py` or any GPU-detection code — this unit is documentation/scripting only, reusing existing detection.

## Interfaces
Depends on `cfg1`'s `pyproject.toml` fix (irrelevant to the CUDA extras themselves, which already resolve on Linux/WSL2, but consistent base-environment behavior) and on `net1`'s `docs/windows-networking.md`. `meta1` links to this unit's documentation section.
