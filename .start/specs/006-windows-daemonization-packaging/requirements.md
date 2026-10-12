---
title: "Windows Daemonization & Packaging"
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

| Field | Type | Value |
|-------|------|-------|
| specId | string | 006-windows-daemonization-packaging |
| title | string | Windows Daemonization & Packaging |
| status | enum | COMPLETE |
| sections | SectionStatus[] | see below |
| clarificationsRemaining | number | 0 |
| acceptanceCriteria | number | 22 |
| openQuestions | string[] | [] |

### SectionStatus

| name | status | detail |
|------|--------|--------|
| Product Overview | COMPLETE | — |
| User Personas | COMPLETE | — |
| User Journey Maps | COMPLETE | — |
| Feature Requirements | COMPLETE | — |
| Detailed Feature Specifications | COMPLETE | — |
| Success Metrics | COMPLETE | — |
| Constraints and Assumptions | COMPLETE | — |
| Risks and Mitigations | COMPLETE | — |
| Open Questions | COMPLETE | none remaining |
| Supporting Research | COMPLETE | — |

---

## Product Overview

### Vision
Installing exo on Windows should feel like installing any normal desktop background app: one installer, no terminal, and the dashboard is always reachable at `http://localhost:52415` after every reboot or login, exactly as it already is for macOS today.

### Problem Statement
Today exo only has two ways to run in the background: a native `.dmg` app on macOS, and a POSIX-only `--legacy-daemon` double-fork mode on Linux (`src/exo/main.py:290-319`) that depends on `python-daemon`'s `DaemonContext` and `/dev/null`-backed file descriptors — mechanisms that do not exist on Windows. `pyproject.toml:29` pins `python-daemon>=3.1.2` as the only daemonization dependency in the project, and there are no systemd unit files, launchd plists, or Windows service/installer assets anywhere in the repository. Windows users who want exo running unattended currently have exactly one option: keep a terminal window open and running `uv run exo` for as long as they want the cluster online. Closing that window, restarting the PC, or logging out kills the process, silently taking the dashboard and any in-flight inference with it.

### Value Proposition
An everyday Windows user should never need to see a terminal to run exo. A single installer sets up exo so it survives reboots and logouts (as a Windows Service) or restarts automatically at login with a familiar tray icon and dashboard window (as a System Tray app) — matching the "just works" bar already set by the macOS `.dmg` app and its Login Items integration, and giving Windows users the same always-on cluster participation Mac and Linux users already have.

## User Personas

### Primary Persona: Everyday Windows User
- **Demographics:** Home or small-office PC owner running Windows 10/11, ranges from hobbyist tinkerer to non-technical family member; comfortable double-clicking an installer and using the Start Menu/System Tray, but not comfortable with PowerShell, the registry, `sc.exe`, or editing config files.
- **Goals:** Install exo once, have it join the household/office exo cluster automatically every time the PC turns on, and never have to remember to "start" anything manually. Wants the dashboard to just be there at `http://localhost:52415` when needed.
- **Pain Points:** Existing background-run options require an open terminal (fragile — closes on logout, accidental Ctrl+C, or PC sleep) or manual re-launch after every reboot. No visible way to tell whether exo is currently running, or to stop/start it without a terminal.

### MECE Check: Personas
- [x] Each persona has distinct goals and pain points (no overlap) — single persona, no overlap possible by construction.
- [x] All user types who interact with this feature are represented (no gaps) — this spec is scoped entirely to the Windows end-user install/run/uninstall experience; the underlying inference/networking personas are covered by specs 001–005, not repeated here.

## User Journey Maps

### Primary User Journey: Silent Background Install
1. **Awareness:** User has already been running exo from source or wants exo to join their household cluster permanently instead of manually starting it in a terminal each time.
2. **Consideration:** User compares "keep a terminal open forever" against "install it like a normal Windows app"; a downloadable installer with a Start Menu entry and a tray icon is the expected bar (set by every other background Windows app they use — Discord, Dropbox, etc.).
3. **Adoption:** User downloads and runs the exo Windows installer, accepts the UAC elevation prompt once, and finishes the installer wizard.
4. **Usage:** After install, exo is silently running in the background (as a Service or from the tray depending on the chosen delivery mode) and `http://localhost:52415` responds in a browser with no visible console window. The user reboots or logs off/on at will; exo comes back automatically.
5. **Retention:** exo keeps working invisibly across reboots. If the user ever wants to check status, stop it, or remove it, there is a discoverable, GUI-based way to do so (Services console or tray menu, and "Apps & Features" for uninstall) — no PowerShell or registry editing required.

### Secondary User Journey: Clean Removal
1. **Awareness:** User no longer wants exo running, or is troubleshooting and wants a fresh install.
2. **Consideration:** User expects uninstalling exo to behave like any other Windows app: findable in "Apps & Features", and leaves nothing running or auto-starting afterward.
3. **Adoption:** User opens "Apps & Features" (or runs the bundled uninstaller) and removes exo.
4. **Usage:** The uninstaller stops the running service/tray process, removes the autostart registration, removes the exo firewall rule (provisioned per spec 003), and removes the Start Menu/tray shortcuts.
5. **Retention:** Re-installing exo afterward behaves like a first-time install — no leftover services, scheduled tasks, or registry Run entries interfere.

### MECE Check: Journeys
- [x] Each journey describes a distinct path (no two journeys cover the same actions for the same persona) — install vs. uninstall are disjoint action sets.
- [x] All primary, secondary, and error/recovery paths are mapped (no gaps) — install, uninstall, and (within Feature Requirements below) the crash-recovery and autostart-toggle paths are all covered by acceptance criteria.
- [x] Every persona has at least one journey — the single persona has two.

## Feature Requirements

### Must Have Features

#### Feature 1: Background Install with No Terminal Window
- **User Story:** As an everyday Windows user, I want to install exo once and have it always running in the background, so that I never have to open or keep open a terminal window.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given the user has downloaded and run the exo Windows installer to completion, When the installer finishes, Then exo is running in the background and no terminal or console window is visible anywhere on screen.
  - [x] Given exo was installed and the default delivery mode is active, When the user restarts their PC, Then `http://localhost:52415` responds in a browser within a reasonable time after the desktop becomes usable, without the user launching anything manually.
  - [x] Given exo is running in the background, When the user opens Task Manager, Then they can identify that exo is running without needing to know internal process or class names (a clearly labeled "exo" entry is visible under Services or Apps as appropriate to the delivery mode).

#### Feature 2: System Tray Application
- **User Story:** As an everyday Windows user, I want a tray icon that opens the exo dashboard in its own window, so that I have a familiar, visual way to check on and interact with my cluster without opening a browser tab manually.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given exo is installed and the user has logged into Windows, When Windows finishes loading the desktop, Then an exo icon appears in the system tray automatically, with no manual launch step.
  - [x] Given the exo tray icon is visible, When the user clicks it, Then a window opens showing the exo dashboard (the same dashboard served at `http://localhost:52415`), with no separate browser window or console window appearing.
  - [x] Given the exo tray icon is visible, When the user right-clicks it, Then a menu appears offering at least "Open Dashboard" and "Quit exo", and selecting "Quit exo" stops the exo process and removes the tray icon.

#### Feature 3: Windows Service (Background, No Login Required)
- **User Story:** As an everyday Windows user who wants exo to keep running even when nobody is logged in (e.g., a spare PC used as an always-on cluster node), I want to install exo as a Windows Service, so that it starts before login and survives logoff.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given exo is installed with the Windows Service delivery mode, When the PC is rebooted and left at the Windows lock screen (nobody logs in), Then `http://localhost:52415` responds from another device on the network within a reasonable time after boot.
  - [x] Given the exo Windows Service is running, When the user opens the Windows Services console (`services.msc`) and stops the "exo" service, Then the exo process and any child processes it spawned are no longer visible in Task Manager, and `http://localhost:52415` stops responding.
  - [x] Given the exo Windows Service is running and the exo process crashes unexpectedly, When the crash occurs, Then the service automatically restarts exo within a bounded time window (with backoff on repeated crashes) and `http://localhost:52415` becomes reachable again without any user action.

#### Feature 4: Clean, Discoverable Uninstall
- **User Story:** As an everyday Windows user, I want to remove exo the same way I remove any other Windows app, so that nothing keeps running or auto-starting after I'm done with it.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given exo is installed, When the user opens Windows Settings → Apps → Installed apps and uninstalls exo, Then the exo process/service stops running during the uninstall and no exo process remains in Task Manager afterward.
  - [x] Given exo has just been uninstalled, When the user checks the Windows Services console, Task Scheduler, and Startup Apps (Settings → Apps → Startup), Then no exo entries remain in any of them.
  - [x] Given exo has just been uninstalled, When the user checks Windows Defender Firewall's allowed-apps list, Then no exo firewall rule remains (the rule provisioned per spec 003 is removed by the uninstaller).

### Should Have Features

#### Feature 5: Autostart Toggle Without Editing the Registry
- **User Story:** As an everyday Windows user, I want a simple on/off switch for "start exo automatically", so that I can control this without editing the registry or Task Scheduler by hand.
- **Acceptance Criteria (Gherkin Format):**
  - [x] Given exo is running as a tray application, When the user opens the tray menu, Then a "Start with Windows" toggle is visible and reflects the current autostart state.
  - [x] Given the user turns off "Start with Windows" from the tray menu, When the PC is next restarted, Then exo does not start automatically, but the user can still launch it manually from the Start Menu.
  - [x] Given exo is running as a Windows Service, When the user opens `services.msc`, Then the exo service's Startup Type (Automatic / Manual / Disabled) is the documented, supported way to control autostart for that delivery mode.

### Could Have Features

- Switching between Windows Service mode and System Tray mode after install, via a settings toggle, without a full reinstall.
- A visible status indicator (tray icon color/badge) reflecting whether the local node is currently the cluster master, a worker, or offline.
- Code-signing the installer and executables with an EV certificate to avoid Windows SmartScreen warnings on first run (functionally optional for this spec; a signed build is the production goal but an unsigned/self-signed build is acceptable for initial delivery).

### Won't Have (This Phase)

- Relocating exo's config/data/cache/log directories on Windows — already specified and owned by spec 005 (windows-filesystem-state-paths); this spec only requires that the service/tray host can write to whatever locations spec 005 defines.
- Provisioning the Windows Defender Firewall inbound rule for the exo ports — already specified and owned by spec 003 (windows-networking-peer-discovery); this spec's uninstaller only needs to remove that rule, not create it.
- Any telemetry or crash-reporting integration for the service/tray host — owned by spec 002 (windows-system-telemetry).
- Porting or validating the MLX/inference backend itself on Windows — owned by spec 001 (windows-inference-backend-abstraction). This spec packages and daemonizes whatever backend those specs deliver; it does not change inference behavior.
- A Microsoft Store (MSIX/UWP-sandboxed) distribution channel — out of scope; the installer format decided in this spec is a conventional desktop installer, not a Store submission.
- Multi-cluster / multi-node remote management UI in the tray app — the tray app only renders the existing local dashboard; it does not add new cross-node management surfaces.

### MECE Check: Features
- [x] No two user stories describe the same capability (no overlap across MoSCoW categories) — Feature 2 (Tray) and Feature 3 (Service) are the two distinct Must-Have delivery mechanisms; Feature 1 and Feature 4 are cross-cutting install/uninstall behaviors that apply to both.
- [x] All capabilities needed to solve the problem for every persona are present (no gaps) — install, run-in-background (both modes), autostart control, and uninstall are all covered.
- [x] Every feature has testable acceptance criteria — all five features have Gherkin criteria above.
- [x] "Won't Have" explicitly accounts for capabilities that could be confused with in-scope features — firewall provisioning, path relocation, telemetry, and the inference backend are each named and pointed at their owning spec.

## Detailed Feature Specifications

### Feature: Windows Service (Background, No Login Required)
**Description:** exo is registered as a standard Windows Service that starts automatically at boot (before any user logs in), supervises the existing `exo` console process in the foreground (the same process that `uv run exo` starts today, without `--legacy-daemon`), restarts it if it crashes, and stops it cleanly — including any child runner processes it spawned — when the service is stopped.

**User Flow:**
1. User installs exo choosing (or accepting the default for) the Windows Service delivery mode.
2. System registers a Windows Service with the Service Control Manager (SCM), configured to start automatically at boot.
3. User reboots (or the service starts immediately after install).
4. System's SCM starts the service, which launches and supervises the exo process; the dashboard becomes reachable at `http://localhost:52415`.

**Business Rules:**
- Rule 1: The service must never rely on `--legacy-daemon`'s double-fork mechanism (`src/exo/main.py:290-319`) — that mechanism is POSIX-only. On Windows, the supervisor process itself provides the "runs without a visible window" and "restarts on crash" behavior; exo runs as a normal foreground process underneath it, matching the precedent set for systemd/launchd in `README.md:211-215` ("systemd/launchd should instead run exo in the FOREGROUND").
- Rule 2: When the service is stopped (via SCM stop, reboot, or shutdown), the supervisor must send a graceful termination signal to exo and wait for it to exit before reporting "stopped" to the SCM, so that in-flight requests are not abruptly killed and the runner process tree (`src/exo/worker/runner/supervisor.py:181-274`) is not orphaned.
- Rule 3: On unexpected exo process exit (crash), the service must restart it automatically, with a backoff between repeated failures, so that a single crash doesn't require manual intervention but a crash loop doesn't spin the CPU.

**Edge Cases:**
- Scenario 1: exo is already running from a terminal (`uv run exo`) when the service tries to start → Expected: the existing PID-file lock (`Pidfile(EXO_PID_FILE, ...)` in `src/exo/main.py:284`) causes the second instance to fail to acquire the lock and exit cleanly; the service reports the failure rather than silently succeeding with two exo processes.
- Scenario 2: The service account cannot access the GPU or the user's normal profile-relative model cache location → Expected: this is the documented trade-off that makes Windows Service a Should-Have default rather than Must-Have-default (see Feature 3's relationship to the System Tray default in Assumptions below); it is not silently hidden from the user.

## Success Metrics

### Key Performance Indicators
- **Adoption:** Of everyday Windows users who download the installer, the percentage who successfully reach a working dashboard at `http://localhost:52415` without opening a terminal or reading troubleshooting docs.
- **Engagement:** Percentage of installs where exo is still registered as auto-starting (service running or tray autostart enabled) 7 days after install, indicating the background-run promise held.
- **Quality:** Rate of support reports describing "exo doesn't come back after reboot" or "I can't find how to stop/uninstall exo" — target near zero given this spec's explicit acceptance criteria.
- **Business Impact:** Increase in the number of Windows nodes that stay online long enough to meaningfully participate in a cluster (i.e., are reachable for inference), since always-on nodes are what make the "multiple devices as a cluster" value proposition work at all on Windows.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| installer_completed | delivery_mode (service/tray), install_scope (per-machine/per-user), version | Measure successful installs and which delivery mode users end up with |
| service_or_tray_autostart_verified | delivery_mode, success (bool) | Confirm the process actually came back after the next reboot/login (measured by the process itself reporting a clean start, not by the installer) |
| uninstall_completed | components_removed (service, autostart entry, firewall rule, tray) | Confirm uninstall did not leave partial state |
| crash_restart_triggered | delivery_mode, restart_count_in_window | Detect crash-loop situations that need investigation |

---

## Constraints and Assumptions

### Constraints
- exo's console entry point remains `exo = "exo.main:main"` (`pyproject.toml:32-33`); the Windows delivery mechanisms must invoke this existing entrypoint rather than duplicating its startup logic.
- `python-daemon` (`pyproject.toml:29`) is POSIX-only; nothing in this spec may depend on it for Windows behavior.
- PyInstaller is the established freezing tool (`packaging/pyinstaller/exo.spec`) and already has a Darwin-specific branch (`exo.spec:72-84`); Windows packaging must extend this file rather than introduce a second freezing mechanism.
- The dashboard is served in-process by the FastAPI API (`src/exo/api/main.py:279-286`), mounted from `DASHBOARD_DIR` — there is no separate Node.js server to manage at runtime; a Windows tray/service host only needs to keep the one exo process alive and point a browser/WebView at its port.
- exo uses Python multiprocessing with the `spawn` start method (`src/exo/main.py:337`), which behaves differently when frozen on Windows and requires the entrypoint to correctly re-execute for child runner processes.

### Assumptions
- We assume the everyday user has local administrator rights on their own PC to run the installer (required for installing a Windows Service or writing firewall rules), consistent with how most consumer Windows software (including exo's own macOS app) is installed today.
- We assume users on a shared/always-on PC (no one routinely logged in) will choose or be defaulted to the Windows Service mode, while users on their personal daily-driver PC will choose or be defaulted to the System Tray mode; this spec's Solution Design records which mode is the recommended default and why.
- We assume Windows 10 (21H2+) and Windows 11 are the supported OS versions, consistent with WebView2 Runtime availability and modern Windows Service APIs.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Windows Service account cannot access the same GPU/profile context as the logged-in user, degrading inference performance or breaking model cache access | High | Medium | Document this trade-off explicitly and make System Tray (which runs in the user's own session) the Must-Have default; Windows Service is Should-Have, positioned for headless/always-on nodes where GPU access is less critical. |
| Unsigned installer triggers Windows SmartScreen warnings, scaring away non-technical users | Medium | High (until code-signing is in place) | Code-signing is called out as a Could-Have in this spec; ship with a clear, honest SmartScreen "More info → Run anyway" note in installer UX copy until signing is added. |
| Multiprocessing `spawn` re-execution breaks under a frozen/service-hosted Windows build, causing runner subprocesses to silently fail to start | High | Medium | Documented as an implementation gotcha in the Solution Design's Risks and Technical Debt section; the Windows entrypoint must call `multiprocessing.freeze_support()` before any process spawning. |
| Uninstaller leaves partial state (service registered but stopped, stale firewall rule, orphaned Startup entry), matching the exact failure the macOS app's `uninstall-exo.sh` was written to fix | Medium | Medium | Use `app/EXO/uninstall-exo.sh` as the completeness bar; the uninstall unit's acceptance scenarios explicitly check Services, Task Scheduler/Startup, and the firewall rule list. |

## Open Questions

None — all decisions required to complete this specification (service-vs-tray default, installer format, and installer scope) are recorded as confirmed ADRs in `solution.md` and logged in `README.md`.

---

## Supporting Research

### Competitive Analysis
Comparable "always-on local background app with a dashboard" products on Windows (e.g., Docker Desktop, Ollama, Plex Media Server) universally ship as a signed installer that registers either a Windows Service or a tray-resident autostart app, and provide a standard uninstaller reachable from "Apps & Features" — this spec adopts that same shape rather than inventing a new one.

### User Research
No formal user research was conducted for this spec; the requirements are derived directly from the existing behavior gap (no working background-run option on Windows at all) and the precedent already established by exo's own macOS app and Linux `--legacy-daemon`/systemd documentation (`README.md:211-215`).

### Market Data
Not applicable — this is an internal platform-parity feature (bringing Windows up to the background-run capability macOS and Linux already have), not a new market-facing capability requiring market sizing.
