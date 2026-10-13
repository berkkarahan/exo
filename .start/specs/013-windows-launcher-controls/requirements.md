# Requirements: Windows Launcher Controls

## User Stories

### Story: Stop and start exo from the window

A person opens the Windows launcher, starts exo on a chosen GPU, closes the window, and later opens it again. The same device and memory limit are selected. Stop ends exo and the processes it started. Restart starts again with the current settings.

## Acceptance Criteria

1. [x] The window offers Start, Stop, Restart, and Close.
2. [x] Stop ends the exo process and every process it started. The status then says the process is stopped.
3. [x] Restart stops a running process and starts again with the current device and memory limit.
4. [x] Close stops a running process and then closes the window.
5. [x] A successful start writes the device name, the dropdown label, and the memory limit. The next open selects that row and fills the memory box.
6. [x] A saved label that is no longer present falls back to a row with the same device name, then to the first row.
7. [x] The status shows the process, whether the local API answers, and the selected device as separate lines. The last output lines are visible.

## Out of Scope

- Windows firewall rules and peer-discovery checks.
- Driver version text beyond the adapter name already shown in the device row.
- Progress deadlines and cluster reconnect behavior.
