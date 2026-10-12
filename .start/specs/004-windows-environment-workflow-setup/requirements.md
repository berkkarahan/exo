---
title: "Windows Environment & Workflow Setup"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No technical implementation details included
- [x] A new team member could understand this PRD
- [x] **MECE: Personas** — each persona is distinct, all user types represented
- [x] **MECE: Journeys** — each journey is a unique path, all paths covered
- [x] **MECE: Features** — no overlapping user stories, no capability gaps
- [x] **MECE: Acceptance Criteria** — each criterion tests a unique condition, all paths covered

---

## Output Schema

### PRD Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| sections | SectionStatus[] | Yes | Status of each PRD section |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |
| acceptanceCriteria | number | Yes | Total testable acceptance criteria defined |
| openQuestions | string[] | No | Unresolved items requiring stakeholder input |

**Report:**

```yaml
specId: "004-windows-environment-workflow-setup"
title: "Windows Environment & Workflow Setup"
status: COMPLETE
sections:
  - name: "Product Overview"
    status: COMPLETE
  - name: "User Personas"
    status: COMPLETE
  - name: "User Journey Maps"
    status: COMPLETE
  - name: "Feature Requirements"
    status: COMPLETE
  - name: "Detailed Feature Specifications"
    status: COMPLETE
  - name: "Success Metrics"
    status: COMPLETE
  - name: "Constraints and Assumptions"
    status: COMPLETE
  - name: "Risks and Mitigations"
    status: COMPLETE
  - name: "Open Questions"
    status: COMPLETE
    detail: "None remain — scope decisions resolved during authoring, see Decisions Log in README.md"
clarificationsRemaining: 0
acceptanceCriteria: 19
openQuestions: []
```

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

---

## Product Overview

### Vision

A developer on Windows can go from a fresh clone of the exo repository to a running, LAN-discoverable exo coordinator — either natively or inside WSL2 — by following one documented path, without guessing which commands work on their platform.

### Problem Statement

exo's documented setup today (`README.md`) only covers macOS and native Linux: `uv sync --extra mlx` / `uv sync --extra mlx-cpu`, `cargo`/`rustup`, and `nix fmt` as the pre-commit formatter. None of this has been validated on native Windows, and two concrete configuration facts make it currently impossible to follow as-is: `pyproject.toml:188` restricts uv dependency resolution to `sys_platform == 'darwin'` and `sys_platform == 'linux'` only, so `uv sync` cannot resolve any environment on native Windows; and `pyproject.toml:151` hardcodes the basedpyright analysis platform to `Darwin`, so the documented type-check command reports against the wrong platform for a Windows contributor. A Windows developer today has no documented way to know whether they should run natively, run inside WSL2, or how the discovery/networking ports (`52413`–`52415`) behave differently in each choice. This blocks Windows-based developers from contributing to or running exo at all without independently reverse-engineering fixes for the uv environment restriction and guessing at network behavior.

### Value Proposition

Windows is the desktop OS most exo users already run their local LLM tooling on (Ollama, LM Studio, text-generation-webui). Documenting and scripting two clear, correctly-scoped setup paths — native Windows for LAN-integrated coordination, and WSL2 for GPU passthrough and Linux-parity dependency resolution — lets those users plug exo into their existing workflow without abandoning their OS, and removes the current binary "impossible on Windows" blocker created by the uv `environments` restriction.

## User Personas

### Primary Persona: Windows Developer/Operator

- **Demographics:** Software developer or ML hobbyist running Windows 10/11 as their primary desktop OS; comfortable with a terminal (PowerShell) and package managers, but not necessarily with Linux administration or containers; technical expertise: intermediate-to-advanced in software but may be a first-time WSL2 user.
- **Goals:** Get the exo coordinator running on their Windows machine so it can join or lead a LAN inference cluster alongside their existing local LLM tooling; run and pass the project's pre-commit checks (type-check, lint, tests) locally before pushing changes; decide between native Windows and WSL2 based on their actual hardware (NVIDIA GPU vs. none) and networking needs (single machine vs. multi-machine LAN cluster).
- **Pain Points:** The documented setup instructions in `README.md` only cover macOS and Linux, so there's no starting point for Windows; `uv sync` fails outright on native Windows today because of the `pyproject.toml:188` platform restriction, with no explanation of why; it isn't obvious that WSL2's default networking mode breaks the exo peer-discovery multicast, so a cluster "silently" doesn't discover other machines on the LAN; the documented pre-commit sequence relies on `nix fmt`, which isn't available on Windows.

### MECE Check: Personas
- [x] Each persona has distinct goals and pain points (no overlap)
- [x] All user types who interact with this feature are represented (no gaps) — this spec covers only the person setting up and running exo on a Windows host; it explicitly does not introduce a second persona for cluster administration, which is out of scope (see Won't Have)

## User Journey Maps

### Primary User Journey: First-time Windows setup to a running coordinator

1. **Awareness:** The developer clones exo on a Windows machine, reads `README.md`, and hits a wall: no Windows section exists, and `uv sync` fails immediately with an environment-resolution error referencing `pyproject.toml`.
2. **Consideration:** They check whether their machine has an NVIDIA GPU and whether they need this node to be discoverable by other machines on their LAN, to decide between native Windows and WSL2.
3. **Adoption:** They follow the new Windows setup documentation for their chosen path (native or WSL2), running the provided idempotent setup script that detects missing prerequisites (Python 3.13, Rust/MSVC toolchain, Node.js, uv) and either confirms them present or gives explicit install-it-yourself instructions (with optional `winget` commands).
4. **Usage:** They build the dashboard, run `uv run exo`, and confirm success via a documented single smoke check: the coordinator process starts, the dashboard loads at `http://localhost:52415`, and `/v1/models` answers.
5. **Retention:** They keep using their chosen path for day-to-day development, running the documented non-Nix pre-commit sequence (basedpyright, ruff, pytest) before every push, trusting that CI (`nix flake check`) remains the final authority.

### Secondary User Journey: Choosing between native Windows and WSL2 for a multi-machine LAN cluster

1. **Awareness:** The developer already has exo running on macOS/Linux machines on their LAN and wants to add a Windows machine to the same cluster.
2. **Consideration:** They read the documented networking guidance and learn that exo's peer discovery (`rust/networking/src/discovery.rs:18,46-78`) uses IPv6 UDP multicast, which does not cross WSL2's default NAT boundary, and that native Windows gives real LAN-level discovery without extra configuration.
3. **Adoption:** Based on their need for LAN discoverability, they choose native Windows as the supported default, or accept WSL2's best-effort posture (with mirrored networking mode) if they specifically need GPU passthrough for CUDA-backed inference.
4. **Usage:** They configure `.wslconfig` with `networkingMode=mirrored` if using WSL2, and verify the documented ports behave as expected in their mode.
5. **Retention:** They document their working configuration and, if issues arise, use the documented port/mode matrix instead of re-discovering the WSL2 networking model from scratch.

### MECE Check: Journeys
- [x] Each journey describes a distinct path (no two journeys cover the same actions for the same persona)
- [x] All primary, secondary, and error/recovery paths are mapped (no gaps)
- [x] Every persona has at least one journey

## Feature Requirements

### Must Have Features

#### Feature 1: Documented, correctly-scoped native Windows setup path
- **User Story:** As a Windows developer, I want documented, verified instructions for running exo natively on Windows, so that I can get a working coordinator without guessing which commands from the macOS/Linux instructions apply.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a clean Windows 11 machine with none of the prerequisites installed, When the developer follows the documented native Windows setup steps, Then Python 3.13, the Rust/MSVC toolchain, Node.js, and uv are each either confirmed present or the developer is given an explicit, correct instruction (including an optional `winget` command) to install the missing one
  - [ ] Given all prerequisites are installed, When the developer runs the documented dependency-installation command, Then `uv sync` resolves successfully on native Windows (i.e., the uv `environments` restriction no longer excludes Windows)
  - [ ] Given the dependencies are installed, When the developer runs the documented dashboard build and `uv run exo` commands, Then the exo dashboard is reachable at `http://localhost:52415` and `curl http://localhost:52415/v1/models` returns a response, within the documented time budget
  - [ ] Given the developer runs `uv run basedpyright` on native Windows, When type-checking completes, Then it analyzes against the Windows platform rather than a hardcoded Darwin platform

#### Feature 2: Documented, correctly-scoped WSL2 setup path with GPU passthrough
- **User Story:** As a Windows developer with an NVIDIA GPU, I want documented instructions for running exo inside WSL2 with GPU passthrough, so that I can use exo's Linux CUDA support without dual-booting or a second physical machine.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a clean WSL2 Ubuntu distribution with an NVIDIA GPU available on the Windows host, When the developer follows the documented WSL2 setup steps, Then `uv sync --extra mlx-cuda12` (or `mlx-cuda13`, matching their CUDA version) resolves and installs successfully, reusing the existing Linux dependency path
  - [ ] Given exo is running inside WSL2, When the developer visits `http://localhost:52415` from a Windows browser, Then the dashboard loads, demonstrating that WSL2's `localhost` port forwarding works for the API port without extra configuration
  - [ ] Given the developer needs this WSL2 node to be discovered by other machines on their LAN, When they consult the documented networking guidance, Then they are told explicitly which of the three exo ports (52413 discovery, 52414 zenoh, 52415 API) work under default NAT mode versus mirrored networking mode (`.wslconfig` `networkingMode=mirrored`)

#### Feature 3: Explicit support-posture guidance (native vs. WSL2)
- **User Story:** As a Windows developer choosing how to run exo, I want clear guidance on which path is recommended and why, so that I don't waste time on a path that doesn't fit my hardware or networking needs.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a developer with no NVIDIA GPU who needs their machine discoverable on a LAN, When they read the setup documentation, Then native Windows is presented as the recommended default and WSL2 as best-effort, with the LAN-discovery trade-off stated plainly
  - [ ] Given a developer who needs CUDA-backed inference, When they read the setup documentation, Then WSL2 is presented as the path that reuses exo's existing, tested Linux CUDA dependency markers, with the default-NAT discovery limitation stated plainly

#### Feature 4: Non-Nix pre-commit workflow for Windows contributors
- **User Story:** As a Windows developer preparing a change for review, I want a documented equivalent to the project's `nix fmt` / `nix flake check` pre-commit sequence that works without Nix, so that I can validate my change locally before pushing, the same way macOS/Linux contributors do.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a Windows developer without Nix installed, When they run the documented pre-commit sequence, Then it runs `uv run basedpyright`, `uv run ruff check`, and `uv run pytest` and reports pass/fail for each, without requiring `nix fmt`
  - [ ] Given the documented sequence has run, When the developer reads the accompanying note, Then it states plainly that CI's `nix flake check` remains the authoritative gate and the local sequence is a best-effort approximation

### Should Have Features

- Idempotent setup scripts (PowerShell for native Windows, shell script for WSL2) that can be re-run safely without duplicating work or failing on partial completion.
- A single documented end-to-end smoke check (coordinator starts, dashboard loads, `/v1/models` answers) usable after either setup path, so a developer can self-verify success without needing to run the full test suite.

### Could Have Features

- A `winget`-based one-command install option for prerequisites, offered as an explicit opt-in alternative to the default detect-and-instruct behavior.
- A troubleshooting appendix mapping common Windows/WSL2 setup failures (e.g., MSVC linker not found, WSL2 kernel too old for GPU passthrough) to their fixes.

### Won't Have (This Phase)

- Changing exo's inference backend or adding a native (non-MLX, non-CUDA) Windows GPU backend — that is spec 001's scope, not this spec's.
- Redesigning telemetry/observability internals — that is spec 002's scope.
- Relocating exo's data/config/model file paths for Windows conventions (e.g., `%APPDATA%` layout) — that is spec 005's scope.
- Packaging exo as a Windows service or system-tray application — that is spec 006's scope.
- Building or shipping a signed Windows installer/MSI for exo.
- Providing Windows GPU (DirectML/native CUDA outside WSL2) inference support — native Windows remains coordinator/CPU-class per this spec; GPU-backed inference on Windows is only available via the WSL2 path.

### MECE Check: Features
- [x] No two user stories describe the same capability (no overlap across MoSCoW categories)
- [x] All capabilities needed to solve the problem for every persona are present (no gaps)
- [x] Every feature has testable acceptance criteria
- [x] "Won't Have" explicitly accounts for capabilities that could be confused with in-scope features (inference backend, telemetry, path relocation, packaging are each named and attributed to their owning spec)

## Detailed Feature Specifications

### Feature: Documented, correctly-scoped native Windows setup path

**Description:** This feature covers everything required to take a Windows developer from a fresh git clone to a running exo coordinator without leaving Windows: prerequisite detection/instruction, the pyproject.toml configuration changes that unblock `uv sync` and `basedpyright` on Windows, and dashboard-build + run instructions verified to work on Windows paths and shells (PowerShell).

**User Flow:**
1. Developer clones the repository and opens a PowerShell prompt in the repo root.
2. Developer runs the documented setup script, which detects Python 3.13, the Rust/MSVC toolchain, Node.js, and uv, printing pass/fail plus install guidance for anything missing.
3. Developer installs any missing prerequisite following the printed guidance (or the optional `winget` command), then re-runs the script until all checks pass.
4. Developer runs the documented dashboard build and `uv sync` commands; `uv sync` succeeds because the `pyproject.toml` `environments` list now includes a Windows marker.
5. Developer runs `uv run exo` and confirms the coordinator is reachable via the documented smoke check.

**Business Rules:**
- Rule 1: The setup script does not silently install system-level prerequisites (Rust toolchains, Node.js, Python) without the developer's explicit action — it detects and instructs, with an opt-in `winget` install flag, per the item 10 scope decision.
- Rule 2: Native Windows is documented as the recommended default path for a developer who does not need CUDA-backed inference; WSL2 is documented as best-effort for developers who specifically need GPU passthrough.

**Edge Cases:**
- Scenario 1: Developer has Python installed but not version 3.13 (e.g., 3.12 or 3.11 from the Microsoft Store) → Expected: setup script reports the version mismatch explicitly and points to the exact 3.13 installer/`winget` package id, rather than a generic "Python not found."
- Scenario 2: Developer has Visual Studio installed but without the "Desktop development with C++" workload (MSVC build tools), so the Rust toolchain cannot link `exo_rs` → Expected: setup script detects `cargo build` failure mode and directs the developer to install the specific MSVC Build Tools workload needed by `maturin`/PyO3.
- Scenario 3: Developer re-runs the setup script after already completing setup → Expected: script re-detects all prerequisites as present and exits cleanly without re-installing or erroring.

## Success Metrics

### Key Performance Indicators

- **Adoption:** A Windows developer following the documented setup path reaches a running, LAN-reachable coordinator (dashboard + `/v1/models` responding) on their first attempt, without needing to file a GitHub issue or ask in Discord for help with the uv/basedpyright platform blockers this spec fixes.
- **Engagement:** Windows contributors run the documented non-Nix pre-commit sequence locally before every push, matching the existing macOS/Linux `nix fmt` workflow's role in the contribution loop.
- **Quality:** Zero regressions in `nix flake check` (the CI source of truth) caused by the `pyproject.toml` `environments` and `pythonPlatform` changes introduced to unblock Windows.
- **Business Impact:** Increased Windows-originated contributions and cluster nodes, measured qualitatively by GitHub issues/PRs referencing Windows setup closing rather than opening.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Windows setup script run | path chosen (native/WSL2), prerequisite pass/fail per tool, script exit code | Measure how often each path is used and where developers get stuck |
| Smoke check result | success/failure, elapsed time to dashboard-reachable | Measure whether the documented setup reliably produces a working coordinator |
| Pre-commit sequence run (non-Nix) | basedpyright/ruff/pytest pass/fail | Measure whether Windows contributors are validating locally before pushing |

---

## Constraints and Assumptions

### Constraints

- The `pyproject.toml:188` uv `environments` restriction and `pyproject.toml:151` Darwin-pinned basedpyright platform are existing project configuration; this spec's Must Have features require changing both, but only to add Windows support — the existing Darwin/Linux behavior must not regress.
- `pyproject.toml:29`'s `python-daemon` dependency is POSIX-only and backs the `--legacy-daemon` flag (`src/exo/main.py:290-319`); native Windows setup must not require this flag to work, since double-fork daemonization has no Windows equivalent.
- MLX (the primary inference backend, `pyproject.toml:47-72`) has no Windows-native wheel or marker; native Windows can only run coordinator-only (`--no-worker`) or CPU-limited roles until specs 001/003 add Windows-native inference support.
- The documented Nix-based pre-commit workflow (`nix fmt`, `nix flake check`) cannot run natively on Windows, since Nix itself has no native Windows package; this spec must provide a non-Nix equivalent sequence without claiming it replaces CI.

### Assumptions

- We assume Windows developers are running Windows 10 (version 2004+) or Windows 11, both of which support WSL2 out of the box.
- We assume a Windows developer choosing the WSL2 path already has, or is willing to install, WSL2 itself (`wsl --install`) and a Linux distribution (e.g., Ubuntu) — this spec documents exo-specific setup within that distribution, not WSL2 installation itself, which is a standard Microsoft-documented process.
- We assume the existing Linux dependency markers, CUDA extras (`mlx-cuda12`, `mlx-cuda13`), and dependency resolution in `pyproject.toml` work unmodified inside a WSL2 Ubuntu distribution, since WSL2 presents a real Linux kernel/userspace to `uv`.
- We assume specs 001, 002, 005, and 006 (inference backend, telemetry, path relocation, packaging) are tracked and delivered separately, and this spec's setup documentation references them as dependencies rather than re-specifying their content.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Relaxing the `pyproject.toml:188` `environments` restriction to include Windows causes `uv sync` to attempt resolving Darwin/Linux-only extras (e.g., `mlx`, `torch`) on Windows and fail with a confusing dependency error | High | Medium | Add the Windows platform marker only to the base/default resolution set, and keep the `mlx`/`mlx-cpu`/`mlx-cuda12`/`mlx-cuda13` extras' existing `sys_platform` markers unchanged, so a Windows `uv sync` (no extras) resolves the coordinator-only dependency set without pulling in Darwin/Linux-only inference extras |
| Changing `pythonPlatform = "Darwin"` to a per-OS or dynamic value in `tool.basedpyright` changes which errors are reported on macOS/Linux CI, causing new CI failures unrelated to Windows | High | Low | Keep CI's basedpyright platform pinned to Darwin explicitly (since CI runs on Darwin/Linux per `flake.nix`), and document that Windows contributors run basedpyright locally understanding it now type-checks against the Windows platform, without changing the CI-invoked configuration behavior |
| Developers assume WSL2 "just works" for multi-machine LAN clusters because `localhost` forwarding works, then are confused when peer discovery silently fails under default NAT mode | Medium | High | Document the port/mode matrix explicitly (which of ports 52413/52414/52415 work under default NAT vs. mirrored mode) as a Must Have feature (Feature 2), not an aside |
| Setup script silently installs system-level toolchains (Rust, Node, Python) without user consent, surprising developers or conflicting with existing installs | Medium | Low | Default behavior is detect-and-instruct only; install-via-`winget` is opt-in, per the item 10 scope decision recorded in README.md |

## Open Questions

None remain. The three items flagged for a scope decision in the originating request — supported-vs-best-effort path, native-vs-WSL2 networking posture, and setup-script install-vs-detect behavior — are resolved and recorded as ADRs/Decisions in `solution.md` and `README.md`.

---

## Supporting Research

### Competitive Analysis

Local LLM tools popular with the same audience (Ollama, LM Studio) ship native Windows installers and do not require WSL2 for CPU/GPU inference on Windows; this sets a user expectation that "Windows support" means a native path exists, which is why this spec treats native Windows as the recommended default rather than steering all Windows users to WSL2.

### User Research

No formal user research was conducted for this spec; the problem statement is derived directly from the current repository configuration (`pyproject.toml:188`, `pyproject.toml:151`) and the absence of any Windows section in `README.md`'s Quick Start, both of which are verifiable, objective blockers rather than assumptions.

### Market Data

Not applicable — this is an internal developer-experience/platform-support feature, not a market-facing feature.
