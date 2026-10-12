---
id: auto1
title: Autostart Registration
type: feature
dependencies: [inst1]
---
# Autostart Registration

## Goal
Give the everyday user a GUI-discoverable, non-registry-editing way to control whether exo starts automatically — via the SCM's native Startup Type for Service mode, and a per-user Startup-folder shortcut for Tray mode — with the Tray app exposing an on/off toggle for its own mechanism.

## Requirements
- Provide `packaging/windows/installer/register-autostart.ps1`, invoked by the MSI installer (unit `inst1`) at install time: for Service mode, set the "exo" service's Startup Type to Automatic (Delayed Start) via the SCM (no separate autostart mechanism needed — this is the mechanism); for Tray mode, create a Startup-folder shortcut at `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\exo.lnk` pointing at `exo_tray.exe`.
- The Tray app's "Start with Windows" context-menu checkbox (built in unit `tray1`, but the toggle's underlying mechanism is owned here) creates/removes the same Startup-folder shortcut when checked/unchecked, so the tray UI and the installer-time registration use one consistent mechanism.
- Toggling "Start with Windows" off must not stop the currently running exo process — it only prevents the next automatic launch; the user can still start exo manually from the Start Menu shortcut.
- For Service mode, changing autostart is explicitly delegated to the standard `services.msc` Startup Type control (Automatic / Manual / Disabled) — this unit does not add a redundant custom toggle for Service mode, since `services.msc` already satisfies the "no registry editing" requirement.
- Autostart state must be independently verifiable after a reboot: when enabled, the process is running post-reboot/login without manual action; when disabled, it is not, and no residual Startup-folder shortcut or scheduled task exists.

## Constraints
- Follow existing patterns (see AGENTS.md).
- Must not use an HKCU `Run` registry key as the Tray autostart mechanism — the Startup-folder shortcut is the chosen mechanism (ADR-4) specifically because it's visible in Settings → Apps → Startup and File Explorer, unlike a Run key.
- Must not touch the Windows Service's Startup Type from within the Tray app — Service autostart is controlled exclusively via `services.msc`/SCM, not duplicated here.
- Full test coverage for all requirements (verify shortcut creation/removal is idempotent and does not error if the Startup folder already contains a stale/broken exo shortcut from a previous version).

## Interfaces
- Consumes: `exo_tray.exe` path (unit `tray1`), the "exo" service registration (unit `svc1`, invoked via `inst1`'s post-install sequence).
- Produces: the Startup-folder shortcut state and SCM Startup Type setting, both of which unit `unin1`'s uninstaller must remove/reset.
