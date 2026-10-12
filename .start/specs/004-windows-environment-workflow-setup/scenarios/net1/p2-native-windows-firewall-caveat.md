---
unit: net1
feature: windows-environment-workflow-setup
priority: P2
---
# Native Windows Firewall caveat is documented

## Scenario
Read the native Windows subsection of `docs/windows-networking.md`.

## Expected
The document states that a Windows Firewall prompt may appear the first time exo runs on native Windows, and that the developer must allow the prompt for LAN peer discovery to function.
This caveat is scoped only to the native Windows subsection, not duplicated into the WSL2 subsections.
