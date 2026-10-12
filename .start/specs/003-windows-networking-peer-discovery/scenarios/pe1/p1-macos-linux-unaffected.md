---
unit: pe1
feature: Enable Windows package resolution
priority: P1
---
# macOS and Linux dependency resolution is unaffected

## Scenario
On a macOS machine and separately on a Linux machine, from the repo root run `uv lock` followed by `uv sync --extra mlx` (macOS) / `uv sync --extra mlx-cpu` (Linux) with the modified `pyproject.toml` from this unit.

## Expected
Both commands exit with status code 0 on their respective platforms, identical to their pre-change behavior.
The set of resolved packages for `sys_platform == 'darwin'` and `sys_platform == 'linux'` is unchanged from before this unit's `pyproject.toml` edit (no new or removed packages on those platforms).
</content>
