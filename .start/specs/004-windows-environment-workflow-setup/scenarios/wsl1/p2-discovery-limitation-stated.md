---
unit: wsl1
feature: windows-environment-workflow-setup
priority: P2
---
# WSL2 documentation states the default-NAT discovery limitation and links the networking doc

## Scenario
Read the WSL2 setup documentation section produced by this unit.

## Expected
The section contains a one-line statement that peer discovery from WSL2 to other LAN machines requires mirrored networking mode, without re-describing the full port/mode matrix inline.
The section links to `docs/windows-networking.md` for the full explanation rather than duplicating it.
