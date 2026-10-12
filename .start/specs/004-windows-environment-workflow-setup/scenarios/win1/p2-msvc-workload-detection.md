---
unit: win1
feature: windows-environment-workflow-setup
priority: P2
---
# Missing MSVC C++ workload is detected and named specifically

## Scenario
On a machine with Rust/cargo installed but without the Visual Studio "Desktop development with C++" workload, run `scripts\windows\setup.ps1`.

## Expected
The script's output (or the linked troubleshooting documentation) names the specific missing workload ("Desktop development with C++") rather than only reporting a generic Rust/cargo linker failure.
The output gives the developer a concrete next step (e.g., which Visual Studio Installer component to check) rather than pointing only at the raw `cargo build` error text.
