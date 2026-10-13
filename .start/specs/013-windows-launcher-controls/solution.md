# Solution: Windows Launcher Controls

## Approach

`LauncherController` owns the child process, the validation message, and the output tail. Start saves `LauncherSettings` as JSON under the config directory. Stop calls `stop_process_tree`, which on Windows runs `taskkill /T /F` so runner children exit with the parent. The window reads that status into three lines and a log box. The API line comes from a short request to `http://127.0.0.1:52415/state` while the process is running.

## Files

- `src/exo/windows/launcher.py` — settings, tree stop, controller, and window buttons.
- `src/exo/windows/tests/test_launcher.py` — restore rules, status lines, and a Windows tree stop.
