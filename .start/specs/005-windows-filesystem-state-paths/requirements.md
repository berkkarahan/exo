---
title: "Windows Filesystem State Paths"
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

**Report for this document:**

| specId | title | status | clarificationsRemaining | acceptanceCriteria | openQuestions |
|--------|-------|--------|--------------------------|---------------------|----------------|
| 005-windows-filesystem-state-paths | Windows Filesystem State Paths | COMPLETE | 0 | 11 | [] |

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

| name | status | detail |
|------|--------|--------|
| Product Overview | COMPLETE | |
| User Personas | COMPLETE | |
| User Journey Maps | COMPLETE | |
| Feature Requirements | COMPLETE | |
| Detailed Feature Specifications | COMPLETE | |
| Success Metrics | COMPLETE | |
| Constraints and Assumptions | COMPLETE | |
| Risks and Mitigations | COMPLETE | |
| Open Questions | COMPLETE | none remaining |
| Supporting Research | COMPLETE | |

---

## Product Overview

### Vision

Every exo user sees their configuration, model weights, and logs land in the location their operating system's own conventions predict — `%APPDATA%`/`%LOCALAPPDATA%` on Windows, XDG directories on Linux, `~/.exo` on macOS — with no directory-hunting, no roaming-profile bloat, and no surprises when Windows Backup, antivirus scanners, or IT-managed roaming profiles inspect the user's home folder.

### Problem Statement

exo already runs on Windows today: the path-resolution code in `constants.py` has an explicit Linux branch (XDG Base Directory variables) and a fallback branch for "non-Linux" platforms that resolves everything to `~/.exo`. Windows falls into that fallback by omission, not by crash — it works, in the sense that exo starts and stores its files somewhere consistent. The problem is that "somewhere consistent" is not "somewhere correct" for Windows:

1. **OS-convention non-compliance.** `~/.exo` (i.e. `%USERPROFILE%\.exo`) is a Unix dotfile convention transplanted onto Windows. It is invisible to Windows Explorer's default view in a way that confuses users, is not where any Windows-native backup, roaming-profile, or antivirus-allowlisting tooling expects application state to live, and is not what a "new team member" familiar with Windows would predict.
2. **Roaming-profile risk.** On domain-joined Windows machines (common in enterprise and lab environments), `%USERPROFILE%` (and everything under it, including a stray `~/.exo`) can be part of a roaming profile that IT synchronizes to a central server on every logon/logoff. Model weights are tens to hundreds of gigabytes; if exo's default model directory ever lands inside that roaming scope, every login triggers copying that data across the network, which can make the machine unusable and can breach IT-imposed profile size quotas.
3. **Two genuinely broken parsers, not just misplaced conventions.** `EXO_MODELS_DIRS` and `EXO_MODELS_READ_ONLY_DIRS` are parsed by splitting on `:` (`src/exo/shared/constants.py:38-42`). A Windows path like `C:\Models` contains a `:` after the drive letter, so splitting on `:` breaks the path into `C` and `\Models` — silently producing a directory list that does not contain the directory the user configured. This is a functional bug, not a convention mismatch, and it reproduces on Windows regardless of where the default root lives.
4. **Long paths.** Hugging Face repository identifiers combined with nested snapshot directory structures (`models--org--repo/snapshots/<revision>/...`) can produce absolute paths that exceed Windows' traditional 260-character `MAX_PATH` limit, causing downloads or file opens to fail with hard-to-diagnose I/O errors.

None of this is "exo crashes on Windows." It is "exo's file placement and multi-path parsing on Windows silently violate OS and enterprise expectations, and one specific parser is outright incorrect there." Consequence of not fixing it: users file confused bug reports about disappearing configured model directories, IT administrators block or flag exo for placing large binaries somewhere their roaming-profile tooling did not expect, and long model names cause opaque download failures.

### Value Proposition

Users get exo behaving like a first-class Windows citizen — configuration in the roaming profile where user preferences belong, model weights and caches in the local-only profile where multi-gigabyte data belongs and where IT tooling already expects large local application data — without having to set any environment variable to get correct behavior, and without losing a single environment-variable override or default that already works today on Linux or macOS.

## User Personas

### Primary Persona: Priya, the Windows AI Enthusiast

- **Demographics:** 25–45, hobbyist or professional developer running a small local-inference cluster (1–4 Windows desktops/laptops, sometimes mixed with a Mac or Linux box), comfortable with the command line but not a Windows internals expert.
- **Goals:** Run `uv run exo` on her Windows gaming PC and have it "just work" the way any well-behaved Windows application does — config and downloaded model weights in predictable places she can find in Explorer or clean up if she needs disk space back.
- **Pain Points:** Today she has to know to look inside a hidden `.exo` folder under her user profile to find multi-hundred-gigabyte model downloads; nothing about that location matches where any other Windows app she uses stores data, so she cannot use standard Windows tools (Storage Sense, "Manage app data") to manage it.

### Secondary Personas

**Deepak, the IT Administrator on a Domain-Joined Fleet.** Manages Windows workstations with roaming user profiles enforced by group policy, including profile-size quotas. His goal is that no application under his purview writes large, frequently-changing data into the roaming (`%APPDATA%`) portion of the profile, because that data gets synchronized over the network on every logon/logoff and can blow through quota or slow down logon for the whole team. His pain point today: he cannot audit or trust that a third-party tool like exo respects the roaming-vs-local distinction, because exo currently does not use either convention on Windows at all.

### MECE Check: Personas

- [x] Each persona has distinct goals and pain points (no overlap) — Priya cares about find-ability and cleanup as an end user; Deepak cares about roaming-profile network/quota impact as an administrator of many machines.
- [x] All user types who interact with this feature are represented (no gaps) — end user (direct exo operator) and IT/administrator (indirect, policy-constrained environment) cover every human role affected by where exo puts files. Existing macOS/Linux users are out of scope for this feature (their behavior is explicitly unchanged) and are not separate personas here.

## User Journey Maps

### Primary User Journey: Priya installs exo for the first time on a new Windows machine

1. **Awareness:** Priya reads exo's README, sees Windows is a supported "Run from Source" platform, and clones the repo.
2. **Consideration:** She checks whether exo will scatter files across her system or contain itself to well-known locations, since she has been burned by badly-behaved Windows ports before.
3. **Adoption:** She runs `uv run exo` for the first time. Without setting any environment variable, exo creates its config file under `%APPDATA%\exo\config.toml` and starts downloading a model into `%LOCALAPPDATA%\exo\models\...`.
4. **Usage:** She opens `%LOCALAPPDATA%\exo` in Explorer when she wants to check how much disk space her downloaded models are using, exactly the way she would for any other Windows application's local cache.
5. **Retention:** Because file placement matches her mental model of "well-behaved Windows app," she keeps using exo instead of writing it off as a Unix tool with a rough Windows port.

### Secondary User Journeys

**Deepak audits a machine that already ran the old, pre-fix build of exo.** He finds a `.exo` folder under a user's profile from before this change shipped, containing several model weight directories. After the fix ships and that user's exo is upgraded, exo detects the pre-existing `~/.exo` and continues reading and writing there in place — it does not move the data and does not create a second, empty `%LOCALAPPDATA%\exo` next to it — and it logs a single line stating where its data currently lives so Deepak can find it during an audit without guessing.

### MECE Check: Journeys

- [x] Each journey describes a distinct path (no two journeys cover the same actions for the same persona) — first-run-on-fresh-machine (Priya) versus audit-of-pre-existing-installation (Deepak) are non-overlapping scenarios.
- [x] All primary, secondary, and error/recovery paths are mapped (no gaps) — fresh install (happy path) and upgrade-with-legacy-data (recovery/compatibility path) cover the two ways a Windows machine can reach this feature; there is no third path, since exo has no separate installer/uninstaller flow that touches these directories.
- [x] Every persona has at least one journey — Priya has the primary journey, Deepak has the secondary journey.

## Feature Requirements

### Must Have Features

#### Feature 1: Windows-Native Directory Placement

- **User Story:** As a Windows exo user, I want exo's configuration, model weights, caches, and logs to live under `%APPDATA%` and `%LOCALAPPDATA%` respectively, so that my file system stays organized the way every other well-behaved Windows application organizes itself.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [ ] Given a Windows machine with no `EXO_HOME` or XDG-style overrides set and no pre-existing `~/.exo` folder, When exo starts, Then its configuration file is created under the user's roaming application-data folder and its model, cache, and log directories are created under the user's local application-data folder.
  - [ ] Given a Linux machine, When exo starts, Then its configuration, data, and cache directories continue to resolve exactly as they did before this change (XDG variables, then `~/.config` / `~/.local/share` / `~/.cache` defaults).
  - [ ] Given a macOS machine, When exo starts, Then its configuration, data, and cache directories continue to resolve to `~/.exo` exactly as they did before this change.
  - [ ] Given `EXO_HOME` is set on any platform, When exo starts, Then `EXO_HOME` continues to override the config, data, and cache roots exactly as it does today.

#### Feature 2: Correct Multi-Path Environment Variable Parsing on Windows

- **User Story:** As a Windows exo user, I want to be able to list additional model directories (e.g. on a second drive) via `EXO_MODELS_DIRS`, so that a Windows drive letter in my path does not get mistaken for a list separator.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [ ] Given `EXO_MODELS_DIRS` is set to a single Windows path containing a drive letter (e.g. `D:\exo-models`), When exo parses it, Then it resolves to exactly one directory entry equal to that full path, not two malformed fragments.
  - [ ] Given `EXO_MODELS_DIRS` or `EXO_MODELS_READ_ONLY_DIRS` lists multiple Windows paths, When exo parses them, Then every listed path is recovered intact as a separate entry.
  - [ ] Given `EXO_MODELS_DIRS` or `EXO_MODELS_READ_ONLY_DIRS` lists multiple POSIX paths on Linux or macOS, When exo parses them, Then behavior is unchanged from today (colon-separated parsing continues to work).

### Should Have Features

#### Feature 3: Legacy Data Detection and Reuse-in-Place

- **User Story:** As a Windows user who already ran exo before this change, I want exo to keep using my existing `~/.exo` data after upgrading, so that I do not lose downloaded models or have exo silently start a second, empty data directory.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [ ] Given a Windows machine where `~/.exo` already exists from a prior exo version and no `EXO_HOME` override is set, When exo starts, Then it continues to resolve config, data, and cache roots to the existing `~/.exo` directory instead of the new `%APPDATA%`/`%LOCALAPPDATA%` locations.
  - [ ] Given that legacy-reuse path is taken, When exo starts, Then it logs exactly one line stating that it is using the pre-existing `~/.exo` location and where that is.
  - [ ] Given a Windows machine where `~/.exo` does not exist, When exo starts, Then it uses the new `%APPDATA%`/`%LOCALAPPDATA%` locations and does not create a `~/.exo` folder.

### Could Have Features

#### Feature 4: Long Path Awareness for Deep Model Snapshot Directories

- **User Story:** As a Windows exo user downloading a model with a long Hugging Face repository id, I want the resulting nested snapshot path to not fail purely because of Windows' historical 260-character path limit, so that my download succeeds the same way it would on macOS or Linux.
- **Acceptance Criteria (Gherkin Format):**

  Criteria:
  - [ ] Given a packaged (frozen) Windows build of exo, When it is built, Then the build declares itself long-path-aware so Windows does not enforce the legacy `MAX_PATH` limit against it.
  - [ ] Given a source (`uv run exo`) install on Windows where the OS-level long-paths setting is disabled, When a user hits a long-path failure, Then exo's documentation tells them the specific Windows setting to enable, rather than leaving them with an unexplained I/O error.

### Won't Have (This Phase)

- Automatically and silently moving a user's existing multi-gigabyte `~/.exo` model directories to the new `%LOCALAPPDATA%` location. (Explicit choice: reuse-in-place instead — see Feature 3.)
- Any custom Windows ACL (access control list) manipulation code. Standard per-user ACL inheritance from `%LOCALAPPDATA%`/`%APPDATA%` already prevents world-writable directories; adding a bespoke ACL layer would duplicate what the OS already guarantees.
- Changing where the `huggingface_hub` library itself caches downloaded snapshots (its own `HF_HOME`-driven default). exo's own directories move; the third-party library's internal cache convention is left exactly as it already behaves on every platform, including Windows.
- Fixing the `--legacy-daemon` double-fork / `Pidfile` file-locking mechanism to work natively on Windows. That code path is POSIX-specific for reasons unrelated to file *placement* (it depends on `fcntl`-style locking and process forking) and is out of scope for a path-resolution refactor; the PID file's *location* still resolves correctly under the new Windows cache root.
- A GUI installer or Windows-specific packaging distribution mechanism (MSI/MSIX). This feature only changes where an already-running exo process stores its files.

### MECE Check: Features

- [x] No two user stories describe the same capability (no overlap across MoSCoW categories) — directory placement (F1), path-list parsing (F2), legacy migration (F3), and long-path support (F4) each address a distinct, non-overlapping failure mode identified in the Problem Statement.
- [x] All capabilities needed to solve the problem for every persona are present (no gaps) — F1 solves Priya's find-ability goal and Deepak's roaming-quota concern; F3 solves Deepak's audit concern for already-deployed machines; F2 and F4 close the two concrete parsing/path-length bugs called out in the Problem Statement.
- [x] Every feature has testable acceptance criteria — see Gherkin blocks above.
- [x] "Won't Have" explicitly accounts for capabilities that could be confused with in-scope features — silent auto-migration (vs. Feature 3's reuse-in-place), custom ACL code (vs. Feature 1's "appropriate permissions" framing), and Hugging Face's own cache location (vs. exo's own directories) are each explicitly excluded so they are not mistaken for included scope.

## Detailed Feature Specifications

### Feature: Windows-Native Directory Placement

**Description:** On Windows, exo's three root directories — configuration, data, and cache — stop falling through to the generic "non-Linux" `~/.exo` default and instead resolve to the conventional Windows split: small, user-following configuration under the roaming profile (`%APPDATA%`), and everything else (model weights, event logs, caches, log files) under the local-only profile (`%LOCALAPPDATA%`), which is never synchronized by roaming-profile infrastructure. Every existing environment-variable override (`EXO_HOME`, `EXO_DEFAULT_MODELS_DIR`, `EXO_MODELS_DIRS`, `EXO_MODELS_READ_ONLY_DIRS`, `HF_HOME`, `HF_TOKEN`, `EXO_DASHBOARD_DIR`, `EXO_LOG`) keeps working exactly as it does today, on every platform, including Windows.

**User Flow:**
1. User starts exo on a Windows machine with no relevant environment variables set.
2. System resolves configuration to the user's roaming profile and model/cache/log data to the user's local profile.
3. User later inspects those folders directly through Windows Explorer to check disk usage or back up their config.

**Business Rules:**
- Rule 1: If `EXO_HOME` is set, it continues to override all three roots on every platform, unchanged from today's behavior.
- Rule 2: If no override is set and the platform is Linux, XDG resolution is used, unchanged from today's behavior.
- Rule 3: If no override is set and the platform is Windows, and no pre-existing `~/.exo` directory is found, configuration resolves under `%APPDATA%\exo` and data/cache resolve under `%LOCALAPPDATA%\exo`.
- Rule 4: If no override is set and the platform is anything else non-Linux (currently macOS), the existing `~/.exo` fallback is used, unchanged from today's behavior.

**Edge Cases:**
- Scenario 1: `%APPDATA%` or `%LOCALAPPDATA%` environment variables are missing or empty on a non-standard Windows setup → Expected: fall back to `Path.home() / "AppData" / "Roaming"` / `Path.home() / "AppData" / "Local"` respectively, matching what Windows itself sets those variables to by default, so exo never crashes for lack of the variable.
- Scenario 2: A user sets `EXO_DEFAULT_MODELS_DIR` to an absolute Windows path with a drive letter → Expected: used exactly as given, unaffected by the roaming/local split (this override already bypasses the split entirely today).

## Success Metrics

### Key Performance Indicators

- **Adoption:** Zero increase in Windows-specific "where did my files go" or "my model directory setting is ignored" issue reports after this change ships, relative to the prior release.
- **Engagement:** No change expected or targeted — this is a correctness/compliance fix, not an engagement feature.
- **Quality:** 100% of the existing Darwin/Linux regression suite (`src/exo/shared/tests/test_xdg_paths.py`) continues to pass unmodified; a new, equally-sized Windows regression suite passes with zero flakes across 10 consecutive CI runs.
- **Business Impact:** Reduced support burden from confused Windows users and reduced risk of exo being blocked by IT policy on domain-joined machines due to roaming-profile bloat.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Windows legacy path detected at startup | `platform=windows`, `legacy_root_found=true/false` (log line, not telemetry) | Confirms the reuse-in-place path (Feature 3) is exercised in the field and gives support/IT a grep-able log line during an audit |
| Startup path resolution log | `config_home`, `data_home`, `cache_home` (log line, not telemetry) | Lets a user or administrator see exactly which roots exo chose without needing to read source code |

---

## Constraints and Assumptions

### Constraints

- exo has no analytics/telemetry pipeline for path resolution; "tracking" above means structured log lines (via the existing `loguru`-based logging in `src/exo/shared/logging.py`), not a remote metrics system.
- The change must not alter any currently-passing behavior of `src/exo/shared/tests/test_xdg_paths.py:10-110` on Linux or macOS.
- The change must not introduce a new third-party dependency; `%APPDATA%`/`%LOCALAPPDATA%` resolution and long-path awareness are achievable with the Python standard library (`os.environ`, `pathlib`) and, for the frozen build, PyInstaller's own manifest options.
- No git, build, or test commands may be run as part of authoring this specification; verification that behavior is correct is deferred to implementation.

### Assumptions

- We assume `%APPDATA%` and `%LOCALAPPDATA%` are present in the environment on every supported Windows version (they are set by Windows itself for every interactive user session since Windows Vista), with a documented fallback if they are ever absent.
- We assume Windows users of exo run it either from source (`uv run exo`) or via a future PyInstaller-frozen build using the same `packaging/pyinstaller/exo.spec` used for other platforms; no separate Windows installer exists yet.
- We assume "appropriate Windows file permissions" (per the epic's technical context) is satisfied by standard per-user NTFS ACL inheritance from `%LOCALAPPDATA%`/`%APPDATA%`, since both are already private-to-the-owning-user by default on a standard Windows installation.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| A Windows user already has a large `~/.exo` model cache and the fix silently starts a second, empty `%LOCALAPPDATA%\exo\models`, appearing to "lose" their downloads | High | Medium | Feature 3 (legacy detection and reuse-in-place) exists specifically to prevent this; it is a Should Have, not deferred indefinitely |
| The Windows drive-letter-vs-colon parsing fix accidentally changes parsing behavior on Linux/macOS | High | Low | The fix uses the platform-appropriate path-list separator so POSIX behavior (`:`) is byte-for-byte unchanged; regression tests cover both platforms |
| Long-path fixes are perceived as "the feature" and scope-creep into rewriting the download pipeline | Medium | Low | Feature 4 is explicitly a Could Have limited to build-manifest opt-in and documentation, not a rewrite of `download_utils.py` |

## Open Questions

None remaining. All decisions required to implement this feature (the `%APPDATA%`/`%LOCALAPPDATA%` split, the legacy-migration strategy, and the multi-path parsing fix) are resolved in `solution.md`.

---

## Supporting Research

### Competitive Analysis

Most cross-platform developer tools that already support Windows follow the same roaming/local split used here: e.g. VS Code stores user settings under `%APPDATA%\Code` and larger caches under `%LOCALAPPDATA%`; Git for Windows and most Electron-based apps follow the same convention. exo already follows the equivalent Linux convention (XDG Base Directory Specification); this feature brings Windows to parity with that existing design intent rather than inventing a new one.

### User Research

No formal user research was conducted for this specification; the problem statement is grounded directly in reading exo's own path-resolution source (`src/exo/shared/constants.py`) and its existing test suite (`src/exo/shared/tests/test_xdg_paths.py`), which together make the current Windows fallback behavior and the colon-parsing bug directly observable in code rather than inferred.

### Market Data

Not applicable — this is an internal engineering correctness fix for an existing supported platform, not a market-facing feature.
