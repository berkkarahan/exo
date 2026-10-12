---
id: iw1
title: Windows network interface classification
type: feature
dependencies: []
---
# Windows network interface classification

## Goal
Report accurate `ethernet`/`wifi` interface types for Windows network adapters, replacing the current behavior where every non-macOS interface classifies as `"unknown"`.

## Requirements
- `get_network_interfaces()` (`src/exo/utils/info_gatherer/system_info.py:93-117`) gains a Windows (`sys.platform == "win32"`) branch that populates `interface_types` with real classifications, mirroring the shape of the existing `_get_interface_types_from_networksetup()` helper (`system_info.py:59-90`) which currently only runs on `darwin`.
- The new Windows branch (e.g. `_get_interface_types_from_windows()`) returns a `dict[str, InterfaceType]` keyed by the same interface name `psutil.net_if_addrs()` already returns on Windows, so it merges into the existing `interface_types.get(iface, "unknown")` call site (`system_info.py:111`) unchanged.
- Adapters the OS identifies as Ethernet-class report `"ethernet"`; adapters identified as 802.11 wireless report `"wifi"`; anything else (virtual adapters, VPN TAP adapters, etc.) falls back to `"unknown"` rather than raising.
- The WMI (or equivalent Windows adapter metadata) query used for classification does not block exo's async event loop (must run off-loop, e.g. via a thread-pool executor, consistent with how macOS's `run_process` subprocess calls are already handled asynchronously in the same file).

## Constraints
- Follow existing patterns (see AGENTS.md) — reuse the existing `InterfaceType`/`NetworkInterfaceInfo` types (`system_info.py:9`) unchanged; do not add new `Literal` variants.
- Do not modify the macOS (`_get_interface_types_from_networksetup`) or default/Linux behavior.
- New Windows-only dependency (e.g. `wmi`) must be scoped so it is not installed or imported on macOS/Linux (import guarded behind the `win32` branch, and/or declared as a Windows-only optional dependency once `pe1` extends `pyproject.toml`'s environments).
- Full test coverage for all requirements.

## Interfaces
Consumes `psutil.net_if_addrs()` interface names (unchanged, existing) and produces `dict[str, InterfaceType]` merged into `NetworkInterfaceInfo.interface_type`, which flows unchanged into `src/exo/master/placement_utils.py:find_ip_prioritised` (line ~358-378) — this unit changes no downstream consumer, only the data quality Windows nodes report.
</content>
