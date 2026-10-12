---
unit: wp1
feature: Windows Platform & Packaging
priority: P1
---
# Windows DirectML extra installs successfully

## Scenario
On a Windows machine with an AMD or NVIDIA GPU, run `uv sync --extra onnx-directml` from the repository root.

## Expected
Command exits with status 0.
The installed environment includes an ONNX Runtime GenAI package and a DirectML execution-provider package.
`uv run exo` starts without error.
