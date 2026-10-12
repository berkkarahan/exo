---
id: svc1
title: Windows Service Host & Process Supervisor
type: feature
dependencies: []
---
# Windows Service Host & Process Supervisor

## Goal
Register exo as a Windows Service that starts before login, supervises the existing `exo` foreground process (launched via the `exo = "exo.main:main"` entrypoint, never through `--legacy-daemon`), restarts it on crash with backoff, and shuts it down cleanly (including its child runner processes) when the service stops.

## Requirements
- Provide `packaging/windows/service/exo-service.xml`: a service-wrapper config (per ADR-1, an off-the-shelf wrapper such as WinSW) that names the service `exo`, points at the frozen `exo.exe` entrypoint, sets Startup Type to Automatic (Delayed Start), configures on-failure restart with increasing backoff (capped, not infinite-instant), and redirects the wrapped process's stdout/stderr to the spec-005-relocated log directory instead of a wrapper-local log file.
- Provide `packaging/windows/service/install-service.ps1`, a PowerShell script (run elevated, invoked by the MSI installer per unit `inst1`) that registers the service with the SCM using the config above, and is idempotent (re-running it on an already-registered service updates the registration rather than erroring).
- On service stop (SCM stop, reboot, or shutdown), the wrapper must send a graceful termination signal to `exo.exe` and wait for it to exit (bounded timeout) before reporting "stopped" to the SCM, so `RunnerSupervisor`'s teardown path (`src/exo/worker/runner/supervisor.py:245-274`) gets a chance to terminate child runner processes cleanly rather than being hard-killed.
- Add a guard in `src/exo/main.py` so that `--legacy-daemon` on `sys.platform == "win32"` exits immediately with a clear, human-readable error (see solution.md's Implementation Example) instead of attempting POSIX-only `DaemonContext`/`os.devnull` behavior.
- The Windows-frozen entrypoint must call `multiprocessing.freeze_support()` before any code path that can spawn a runner subprocess, so `mp.set_start_method("spawn", force=True)` (`src/exo/main.py:337`) works correctly under a frozen build (coordinate with unit `inst1`, which owns the frozen entrypoint's build config — this unit owns the entrypoint's source-level guard itself in `src/exo/__main__.py` / `src/exo/main.py`).
- The service must rely on the existing PID-file lock (`Pidfile(EXO_PID_FILE, ...)` at `src/exo/main.py:284`) as the single-instance guarantee; if the lock is already held (e.g., exo already running from a terminal), the service must fail its start attempt visibly (surfaced in the Windows Event Log / SCM start failure) rather than silently retrying forever.

## Constraints
- Follow existing patterns (see AGENTS.md) — strict typing on any new Python code, descriptive names, no bypassing the type checker.
- Do not add a second daemonization mechanism inside `src/exo/main.py`; all Windows-specific process-lifecycle logic lives in the external service wrapper (`packaging/windows/service/`), not in exo's own Python code.
- Must not modify `src/exo/worker/runner/supervisor.py`'s teardown logic — this unit only needs to give it enough time to run, not change it.
- Full test coverage for all requirements (the guard added to `main.py` needs a unit test on non-Windows platforms simulating `sys.platform == "win32"`).

## Interfaces
- Consumes: `exo = "exo.main:main"` console entrypoint (`pyproject.toml:32-33`); `EXO_PID_FILE`, `EXO_LOG_DIR` (`src/exo/shared/constants.py:68-94`, as relocated by spec 005 on Windows).
- Produces: `packaging/windows/service/exo-service.xml`, `packaging/windows/service/install-service.ps1` — consumed by unit `inst1`'s MSI installer and by unit `unin1`'s uninstaller (which must reverse this registration).
