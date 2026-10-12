---
id: unin1
title: Clean Uninstaller
type: feature
dependencies: [inst1]
---
# Clean Uninstaller

## Goal
Provide a Windows uninstall path — reachable from Settings → Apps → Installed apps and as a standalone script — that stops any running exo process/service, and removes every trace of the service registration, autostart entry, firewall rule, and shortcuts, matching the completeness bar already set by `app/EXO/uninstall-exo.sh` on macOS.

## Requirements
- Provide `packaging/windows/installer/uninstall.ps1`, wired as the MSI's (unit `inst1`) uninstall action, so it also runs automatically when the user uninstalls via Settings → Apps.
- Stop the running exo process/service first: for Service mode, `sc stop exo` (or the wrapper's stop mechanism from unit `svc1`) with a bounded wait, falling back to a forced stop after a timeout; for Tray mode, gracefully terminate the running `exo_tray.exe`/`exo.exe` pair the same way the tray's own "Quit exo" menu item does.
- Delete the Windows Service registration entirely (`sc delete exo` or the wrapper's uninstall mechanism), so it no longer appears in `services.msc` at all (not just stopped/disabled).
- Remove the Tray Startup-folder shortcut created by unit `auto1` (`%APPDATA%\...\Startup\exo.lnk`), so Settings → Apps → Startup no longer lists exo.
- Remove the firewall rule provisioned for exo's ports (owned by spec 003) — this unit only deletes the existing rule (e.g., via `netsh advfirewall firewall delete rule name="exo"` or the equivalent rule name spec 003 defines), it does not create or modify firewall rules itself.
- Remove Start Menu shortcuts and the installed program files directory, and report to the user (console output or MSI UI, matching `app/EXO/uninstall-exo.sh`'s `echo_info`/`echo_warn` pattern at lines 61-71 and its final summary at lines 189-209) exactly what was and wasn't removed.
- Uninstall must succeed even if some components are already missing/partial (e.g., service already manually deleted, shortcut already removed by the user) — matching `uninstall-exo.sh`'s tolerant, idempotent style throughout (e.g., lines 87-92, 98-100, 112-114, 127-129).

## Constraints
- Follow existing patterns (see AGENTS.md) — mirror `app/EXO/uninstall-exo.sh`'s structure and tone (informational, warns on already-removed items, never hard-fails on a missing component) rather than inventing a new uninstall philosophy.
- Must run elevated (uninstalling a service and firewall rule requires Administrator), matching the install's elevation requirement.
- Must not delete the user's model cache or other data directories by default — mirror `uninstall-exo.sh`'s `--keep-models`-style carefulness; deciding the exact default (keep vs. prompt) for exo's Windows data directories is owned by spec 005, this unit only removes what it itself installed (service, autostart, firewall rule, shortcuts, program files).
- Full test coverage for all requirements (a dry-run mode that reports what would be removed without an actual uninstall is required to make this testable in CI without a real Windows Service).

## Interfaces
- Consumes: the "exo" service registration (`svc1`), the Startup-folder shortcut (`auto1`), the firewall rule provisioned by spec 003, the installed program files from `inst1`.
- Produces: a fully clean machine state verifiable by the scenarios below (no Services/Task Scheduler/Startup/Firewall entries remaining).
