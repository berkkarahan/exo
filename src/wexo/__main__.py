from __future__ import annotations

import sys
from collections.abc import Sequence
from multiprocessing import freeze_support
from typing import Final

from wexo.main import main

INLINE_CODE_FLAG: Final[str] = "-c"
RUNTIME_ARGUMENT: Final[str] = "--exo-runtime"


def _maybe_run_inline_code(argv: Sequence[str]) -> bool:
    """
    Reproduce the bare minimum of Python's `-c` flag so multiprocessing
    helper processes (for example the resource tracker) can execute.
    """

    try:
        flag_index = argv.index(INLINE_CODE_FLAG)
    except ValueError:
        return False

    code_index = flag_index + 1
    if code_index >= len(argv):
        return False

    inline_code = argv[code_index]
    sys.argv = ["-c", *argv[code_index + 1 :]]
    namespace: dict[str, object] = {"__name__": "__main__"}
    exec(inline_code, namespace, namespace)
    return True


def _without_runtime_argument(argv: Sequence[str]) -> list[str]:
    """Drop the Windows shell marker before argparse sees the server command."""
    return [argument for argument in argv if argument != RUNTIME_ARGUMENT]


if __name__ == "__main__":
    if _maybe_run_inline_code(sys.argv):
        sys.exit(0)
    freeze_support()
    frozen_windows_shell = (
        sys.platform == "win32"
        and bool(getattr(sys, "frozen", False))
        and RUNTIME_ARGUMENT not in sys.argv
    )
    if frozen_windows_shell:
        from wexo.windows.launcher import main as windows_shell

        windows_shell()
    else:
        if RUNTIME_ARGUMENT in sys.argv:
            sys.argv = _without_runtime_argument(sys.argv)
        main()
