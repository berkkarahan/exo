---
id: tray1
title: System Tray Application (WebView2 shell)
type: feature
dependencies: []
---
# System Tray Application (WebView2 shell)

## Goal
Ship a thin Windows tray application that launches/attaches to the exo process in the user's own login session and renders the existing dashboard (`http://localhost:52415`) in an embedded WebView2 window, with a tray icon and a small context menu — no new UI beyond that shell.

## Requirements
- Provide `packaging/windows/tray/exo_tray/__main__.py`: on launch, check whether an exo process already holds the PID-file lock (`EXO_PID_FILE`); if not, launch `exo.exe` as a foreground child process; if so, attach the tray UI to the already-running instance instead of starting a duplicate.
- Show a tray icon (`packaging/windows/tray/exo_tray/icon.ico`) immediately on launch, with three visual states — Starting, Running, Disconnected — matching the state diagram in solution.md.
- Left-click on the tray icon opens (or focuses, if already open) a WebView2 window navigated to `http://localhost:52415`; no separate browser window or console window may appear.
- Right-click on the tray icon shows a context menu with at minimum: "Open Dashboard", a "Start with Windows" checkbox reflecting current autostart state (delegates the actual toggle action to unit `auto1`'s mechanism), "Restart exo" (visible/enabled at least in the Disconnected state), and "Quit exo".
- "Quit exo" sends a graceful termination signal to the child `exo.exe` process, waits for it to exit, removes the tray icon, and exits the tray app itself.
- On WebView2 environment creation failure (Runtime not installed and no bootstrapper ran, or bootstrap failed), show a clear, non-crashing message directing the user to install the WebView2 Runtime rather than crashing or hanging.
- Closing the WebView2 window (the window's own X button) hides it back to the tray rather than terminating the exo process — the dashboard must remain reachable at `http://localhost:52415` afterward.

## Constraints
- Follow existing patterns (see AGENTS.md) — strict typing, descriptive names, immutability where applicable.
- Must not implement a second copy of the dashboard UI or proxy/rehost its HTTP responses — the WebView2 control navigates directly to the existing `http://localhost:52415` FastAPI-served dashboard (`src/exo/api/main.py:279-286`).
- Must not require elevation (UAC) to launch or operate — the tray app runs in the user's own unelevated session.
- Full test coverage for all requirements, including a fake/mock PID-file-lock scenario to exercise the "attach to existing instance" path without actually starting exo.

## Interfaces
- Consumes: `EXO_PID_FILE` lock state; `http://localhost:52415` (existing FastAPI dashboard route, unchanged); the "Start with Windows" toggle mechanism defined by unit `auto1`.
- Produces: the tray executable and its assets, consumed by unit `inst1`'s MSI packaging and unit `unin1`'s uninstaller (which must stop this process and remove its Startup-folder registration).
