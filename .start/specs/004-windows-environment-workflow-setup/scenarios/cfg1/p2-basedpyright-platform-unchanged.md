---
unit: cfg1
feature: windows-environment-workflow-setup
priority: P2
---
# basedpyright pythonPlatform stays Darwin, with a documented caveat comment

## Scenario
Inspect `[tool.basedpyright]` in `pyproject.toml`.

## Expected
`pythonPlatform` is still set to `"Darwin"` (unchanged value).
A comment immediately above or near `pythonPlatform = "Darwin"` explains that Windows contributors running `basedpyright` locally will see it analyze against Darwin semantics, with a pointer to the Windows documentation.
Running `uv run basedpyright` in CI (Darwin/Linux, per `flake.nix` systems) behaves identically to before this change — same error count, same platform.
