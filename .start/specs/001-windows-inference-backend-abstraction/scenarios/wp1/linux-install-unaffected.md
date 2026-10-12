---
unit: wp1
feature: Windows Platform & Packaging
priority: P2
---
# Existing Linux mlx-cpu install is unaffected

## Scenario
On a Linux machine, run `uv sync --extra mlx-cpu` from the repository root, exactly as documented in the existing `README.md` Linux install instructions.

## Expected
Command exits with status 0, identical to pre-change behavior.
No new Windows-only dependency (onnxruntime-genai, onnxruntime-directml, onnxruntime-gpu) is installed.
`uv run exo` starts and serves `http://localhost:52415` as before.
