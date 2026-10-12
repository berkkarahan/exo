---
unit: wp1
feature: Windows Platform & Packaging
priority: P1
---
# Conflicting Windows GPU extras are rejected

## Scenario
On a Windows machine, run `uv sync --extra onnx-cuda --extra onnx-directml` (requesting two conflicting Windows GPU extras at once) from the repository root.

## Expected
`uv` reports a conflict error rather than silently installing both or picking one arbitrarily.
The error message identifies the two conflicting extras by name.
