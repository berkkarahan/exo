---
title: "Windows Daemonization & Packaging"
status: pending
threshold: 0.90
max_iterations: 5
---
# Decomposition Manifest

## Units

- [ ] svc1: Windows Service Host & Process Supervisor — no dependencies
- [ ] tray1: System Tray Application (WebView2 shell) — no dependencies
- [ ] inst1: PyInstaller Windows Build & MSI Installer — after: svc1, tray1
- [ ] auto1: Autostart Registration (Service startup type / Tray Startup-folder toggle) — after: inst1
- [ ] unin1: Clean Uninstaller (service, autostart, firewall rule, shortcuts) — after: inst1

## Execution Order

Group 1 (parallel): svc1, tray1
Group 2 (sequential): inst1
Group 3 (parallel): auto1, unin1
