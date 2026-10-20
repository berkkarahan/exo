import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _check_source(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    source_path = tmp_path / "backend_contract.py"
    _ = source_path.write_text(source, encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "basedpyright",
            "--project",
            str(PROJECT_ROOT / "pyproject.toml"),
            str(source_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_optional_backend_contracts_work_without_native_imports(tmp_path: Path) -> None:
    result = _check_source(
        tmp_path,
        """
from exo_rs import Pidfile
from onnxruntime_genai.models.builder import create_model

def check(pidfile: Pidfile) -> None:
    descriptor: int = pidfile.as_raw_fd()
    print(descriptor)
    create_model("llama", "input", "output", "int4", "cpu", "cache", int4_block_size=32)
""",
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("source", "diagnostic"),
    [
        (
            "from onnxruntime_genai.models.builder import create_model\n"
            "create_model(123, 'input', 'output', 'int4', 'cpu', 'cache')\n",
            "reportArgumentType",
        ),
    ],
)
def test_optional_backend_contracts_reject_wrong_types(
    tmp_path: Path, source: str, diagnostic: str
) -> None:
    result = _check_source(tmp_path, source)
    assert result.returncode != 0
    assert diagnostic in result.stdout, result.stdout + result.stderr
