"""Allow API tests to import exo without a separately built dashboard."""

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if "EXO_DASHBOARD_DIR" not in os.environ:
    os.environ["EXO_DASHBOARD_DIR"] = str(_REPO_ROOT / "dashboard")


def _remove_unreadable_path_entries() -> None:
    """Drop ``PATH`` entries that tinygrad's C-runtime discovery cannot stat.

    tinygrad walks every ``PATH`` entry when resolving the C library for its
    CPU compiler backend. Windows hosts may contain a system-profile WindowsApps
    entry whose ``stat`` raises ``PermissionError`` (WinError 5) instead of
    reporting not-a-directory, which aborts GGUF tensor realization. Only
    entries whose ``stat`` raises ``PermissionError`` are removed; this is
    test-host hygiene, not a change to inference behavior.
    """
    if os.name != "nt":
        return
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    readable: list[str] = []
    for part in path_parts:
        try:
            Path(part).stat()
        except PermissionError:
            continue
        except OSError:
            readable.append(part)
            continue
        readable.append(part)
    if readable != path_parts:
        os.environ["PATH"] = os.pathsep.join(readable)


_remove_unreadable_path_entries()
