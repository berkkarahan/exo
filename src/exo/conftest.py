"""Allow API tests to import exo without a separately built dashboard."""

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if "EXO_DASHBOARD_DIR" not in os.environ:
    os.environ["EXO_DASHBOARD_DIR"] = str(_REPO_ROOT / "dashboard")
