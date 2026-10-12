---
id: fw1
title: Windows firewall setup CLI
type: feature
dependencies: []
---
# Windows firewall setup CLI

## Goal
Ship a standalone, opt-in, idempotent `exo-setup-firewall` command that provisions the Windows Defender Firewall inbound rules exo needs, requesting elevation only for itself and never for the main `exo` process.

## Requirements
- A new console-script entry point (e.g. `exo-setup-firewall`) creates 4 named inbound Windows Firewall rules: TCP allow for the API port (default `52415`, `src/exo/main.py:384,427-432`), TCP allow for the Zenoh port (default `52414`, `main.py:474-479`), UDP allow for the discovery port (default `52413`, `main.py:481-486`), and one program-scoped rule keyed to the exo interpreter/binary path covering the dynamic ephemeral ports used by ring/JACCL/prefill listeners (`src/exo/utils/ports.py:4-6`, `src/exo/worker/runner/runner.py:157-160`, `src/exo/worker/disaggregated/server.py:86-100`).
- Before requesting elevation, the command prints a plain-text summary of exactly which 4 rules it is about to create.
- The command is idempotent: running it again when the rules already exist creates zero duplicates and exits successfully.
- If the operator declines the UAC elevation prompt, the command exits with a non-zero status and an explanatory message, creating zero rules.
- Running `uv run exo` normally never requires or requests elevation, regardless of whether this setup command has been run.
- If the setup command has never been run, `uv run exo` still starts successfully (discovery may simply find zero peers, surfaced by unit `dg1`'s diagnostic).

## Constraints
- Follow existing patterns (see AGENTS.md) — read default port values from the same source `main.py`'s `Args` defaults use, do not hardcode a second copy of magic port numbers where avoidable.
- Firewall rules must be named distinctly and scoped to specific ports/program (never a blanket "allow all inbound" rule).
- Must not modify the exo runtime's own startup path (`main.py`) to request elevation.
- Full test coverage for all requirements.

## Interfaces
Standalone CLI, invoked out-of-process via `netsh advfirewall` or `New-NetFirewallRule`-equivalent Windows firewall APIs — no in-process interface shared with the `exo` runtime beyond reading the same default port constants.
</content>
