---
unit: pe1
feature: Enable Windows package resolution
priority: P0
---
# uv lock resolves successfully on Windows

## Scenario
On a Windows machine with `uv` installed, from the repo root run `uv lock`.

## Expected
Command exits with status code 0.
The resulting `uv.lock` file includes resolved package entries for `sys_platform == 'win32'` (grep the lockfile for a `win32`-tagged marker/wheel entry).
No resolver error mentioning "no solution found" or "environment not supported" is printed.
</content>
