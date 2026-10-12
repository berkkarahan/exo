---
id: inst1
title: PyInstaller Windows Build & MSI Installer
type: feature
dependencies: [svc1, tray1]
---
# PyInstaller Windows Build & MSI Installer

## Goal
Extend the existing, cross-platform `packaging/pyinstaller/exo.spec` with a Windows (`win32`) branch that freezes both the service-hosted `exo.exe` and the tray `exo_tray.exe` built by units `svc1`/`tray1`, and package the result into a single WiX-built, per-machine MSI installer that lets the user's chosen delivery mode be registered at install time.

## Requirements
- Add a `sys.platform == "win32"` branch to `packaging/pyinstaller/exo.spec`, following the existing `sys.platform == "darwin"` branch (`exo.spec:72-84`) as the pattern: no second freezing tool, same `Analysis`/`DATAS`/`HIDDEN_IMPORTS` pipeline (`exo.spec:56-91`), with an added `EXE()` target for the windowless tray build (`console=False`) alongside the existing console-mode `exo.exe` target used by the service (`console=True`, since the service wrapper owns log redirection).
- Ensure the frozen Windows entrypoint (`src/exo/__main__.py`, the existing `ENTRYPOINT` at `exo.spec:12`) calls `multiprocessing.freeze_support()` before any spawn-capable code runs, per solution.md's Implementation Example — coordinate with unit `svc1`'s `main.py` guard so both land in the same module without duplication.
- Provide `packaging/windows/installer/exo.wxs`: WiX source defining an MSI with per-machine install scope, an upgrade code (so re-running a newer installer performs an in-place upgrade rather than a side-by-side install), and feature selection for the Service and Tray delivery modes (installing the frozen executables from this unit plus the config/scripts from `svc1` and `tray1`).
- Provide `packaging/windows/installer/build-msi.ps1`: invokes the WiX Toolset (`heat`/`candle`/`light`, or the modern `wix build` CLI) against `exo.wxs` and the PyInstaller `COLLECT` output to produce the final `.msi`, mirroring the staged-build shape of `packaging/dmg/create-dmg.sh` (stage → package → verify output).
- The MSI must set the installed application's version from `pyproject.toml`'s `[project].version` (currently `0.3.70`, `pyproject.toml:3`) so it appears correctly versioned in Windows Settings → Apps → Installed apps.
- The MSI's post-install sequence must invoke `install-service.ps1` (unit `svc1`) and/or the Tray Startup-folder registration (unit `auto1`) depending on the feature(s) selected, and must invoke neither destructively if the other feature is deselected.

## Constraints
- Follow existing patterns (see AGENTS.md) — no new Python dependency for freezing; WiX is a build-time-only tool, not a runtime dependency added to `pyproject.toml`.
- Must not remove or alter the existing `darwin`/default behavior of `exo.spec` — the `win32` branch is strictly additive, exactly as the `darwin` branch is scoped only to `sys.platform == "darwin"` (`exo.spec:72-84`).
- Installer must request Administrator/UAC elevation (per-machine install + service registration require it); must not silently attempt an unelevated per-machine install.
- Full test coverage for all requirements (spec-file branch logic and MSI feature-selection logic should be exercised, e.g., via a dry-run/verify mode of `build-msi.ps1`).

## Interfaces
- Consumes: `packaging/windows/service/*` (unit `svc1`), `packaging/windows/tray/*` (unit `tray1`), `pyproject.toml`'s version field.
- Produces: the built `.msi` and the frozen `exo.exe`/`exo_tray.exe` binaries, consumed by units `auto1` and `unin1`.
