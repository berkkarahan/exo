---
unit: wp1
feature: Windows Platform & Packaging
priority: P0
---
# Windows CPU-only extra installs successfully

## Scenario
On a clean Windows 10/11 checkout of the exo repository, run `uv sync --extra onnx-cpu` from the repository root.

## Expected
Command exits with status 0.
No error mentioning unresolvable platform markers, `sys_platform`, or `win32`.
`uv run exo` subsequently starts and serves `http://localhost:52415` without crashing.
