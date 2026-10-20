"""Windows pidfile lock: held across write, released only by close."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="the Windows pidfile uses a Win32 file lock",
)

_CHILD_ACQUIRE_PIDFILE_SCRIPT: Final = textwrap.dedent(
    """
    import sys
    from pathlib import Path

    from wexo.utils.windows_pidfile import Pidfile, PidfileError

    path = Path(sys.argv[1])
    try:
        handle = Pidfile(path, 0o0600)
        handle.write()
        handle.close()
    except (OSError, PidfileError) as exception:
        print(f"Failed to acquire EXO pidfile at {path}: {exception}")
        raise SystemExit(73) from exception
    """
)


def _run_child_acquire_pidfile(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _CHILD_ACQUIRE_PIDFILE_SCRIPT, str(path)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_windows_pidfile_write_keeps_the_lock_until_close(tmp_path: Path) -> None:
    from wexo.utils.windows_pidfile import Pidfile

    path = tmp_path / "wexo.pid"
    handle = Pidfile(path, 0o0600)
    handle.write()
    assert path.read_text(encoding="utf-8") == str(os.getpid())

    blocked_child = _run_child_acquire_pidfile(path)
    assert blocked_child.returncode == 73
    assert "Failed to acquire EXO pidfile" in blocked_child.stdout
    assert path.read_text(encoding="utf-8") == str(os.getpid())

    handle.close()
    assert not path.exists()

    unblocked_child = _run_child_acquire_pidfile(path)
    assert unblocked_child.returncode == 0, unblocked_child.stderr
    assert unblocked_child.stdout == ""
    assert not path.exists()


def test_windows_pidfile_close_is_idempotent(tmp_path: Path) -> None:
    from wexo.utils.windows_pidfile import Pidfile

    path = tmp_path / "wexo.pid"
    handle = Pidfile(path, 0o0600)
    handle.write()
    handle.close()
    handle.close()
    assert not path.exists()
