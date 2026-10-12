---
id: wp1
title: Windows Platform & Packaging
type: feature
dependencies: []
---
# Windows Platform & Packaging

## Goal

Make `uv sync` resolve and install exo's inference dependencies on Windows, and add the new `Backend` capability enum members that every other unit depends on.

## Requirements

- `pyproject.toml`'s `[tool.uv] environments` (currently `["sys_platform == 'darwin'", "sys_platform == 'linux'"]`, `pyproject.toml:188`) includes `"sys_platform == 'win32'"`, without removing or altering the existing Darwin/Linux entries.
- New optional-dependency extras are added for Windows: `onnx-directml`, `onnx-cuda`, `onnx-cpu` (mirroring the shape of the existing `mlx-cpu`/`mlx-cuda12`/`mlx-cuda13` extras at `pyproject.toml:62-72`), each installing `onnxruntime-genai` plus the matching execution-provider package (`onnxruntime-directml` or `onnxruntime-gpu`), gated to `sys_platform == 'win32'`.
- The new Windows extras are added to the existing `[tool.uv] conflicts` group (`pyproject.toml:190-197`) alongside `mlx-cuda13`/`mlx-cuda12`/`mlx-cpu`/`mlx-none`, so a user cannot select two conflicting Windows GPU extras at once.
- `src/exo/shared/types/backends.py`'s `Backend` enum gains three new members: `OnnxDirectMl`, `OnnxCuda`, `OnnxCpu`, added after the existing `Vllm` member without renaming or removing any existing member.
- Existing Darwin/Linux `uv sync --extra mlx*` installs continue to work exactly as before (no regression).
- `uv run exo` on a Windows machine with no GPU extras installed (or with `onnx-cpu` installed) starts the process, serves the dashboard and API at `http://localhost:52415`, and does not crash due to a missing or unsupported backend.

## Constraints

- Follow existing patterns (see AGENTS.md) — Pydantic/enum style, `str, Enum` base matching the existing `Backend` definition exactly.
- Do not modify `pyproject.toml`'s `mlx`/`mlx-lm`/`mflux` source overrides or their Darwin/Linux markers.
- Do not add any new Windows dependency to the default (non-extra) `[project] dependencies` list — Windows inference packages must be opt-in extras only, same as `mlx`.
- Full test coverage for all requirements: at minimum, a test asserting the three new `Backend` enum members exist with the expected string values.

## Interfaces

`Backend` (str, Enum) in `src/exo/shared/types/backends.py` gains: `OnnxDirectMl = "OnnxDirectMl"`, `OnnxCuda = "OnnxCuda"`, `OnnxCpu = "OnnxCpu"`. Every downstream unit (bd1, wc1, we1, br1, pc1) imports these three new members from this exact module.
