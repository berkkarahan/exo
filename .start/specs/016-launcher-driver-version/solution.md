# Solution: Launcher Driver Version

## Approach

`opencl_driver_versions` enumerates GPU devices and returns name/version pairs. It does not run the numeric probe. Failures become an empty tuple.

`driver_version_for_adapter_name` keeps a version only when every match for that name agrees. `windows_device_choices` stores it on the row. The saved label stays `name (VRAM)`. The menu caption and status line append the version.

## Files

- `src/exo/backends/tinygrad_opencl.py` — enumeration pairs.
- `src/exo/windows/launcher.py` — row, caption, and status line.
- Tests beside those modules.
