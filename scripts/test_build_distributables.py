import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPTS = ["build.sh", "build.bat"] if sys.platform == "win32" else ["build.sh"]


@pytest.mark.parametrize(
    "source_path", ["packaging/pyinstaller/exo.spec", "src/wexo/windows/shell.py"]
)
def test_windows_icon_references_use_checked_in_resources(source_path: str) -> None:
    source = ast.parse((PROJECT_ROOT / source_path).read_text(encoding="utf-8"))
    icons = [
        node.value
        for node in ast.walk(source)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.endswith(".ico")
    ]
    assert icons
    for icon in icons:
        assert (PROJECT_ROOT / "resources" / icon).is_file(), icon


def test_packaging_includes_tinygrad_runtime_source_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PyInstaller.utils import hooks

    for directory in ("dashboard/build", "resources", "src/wexo/shared/models"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "src/wexo/__main__.py").touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(hooks, "collect_submodules", lambda _name: [])
    monkeypatch.setattr(shutil, "which", lambda _name: sys.executable)
    spec = (PROJECT_ROOT / "packaging/pyinstaller/exo.spec").read_text(encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(spec.split("\na = Analysis(")[0], "exo.spec", "exec"), namespace)
    data_files = namespace["DATAS"]
    assert isinstance(data_files, list)
    assert any(
        Path(source).name == "ops_cpu.py"
        and Path(destination).as_posix() == "tinygrad/runtime"
        for source, destination in data_files
    )


def _find_bash() -> str | None:
    if sys.platform == "win32":
        for candidate in (
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Git/bin/bash.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Git/bin/bash.exe",
            Path(os.environ.get("USERPROFILE", "")) / "scoop/apps/git/current/bin/bash.exe",
        ):
            if candidate.is_file():
                return str(candidate)
        found = shutil.which("bash")
        if found and "system32" in found.lower():
            return None
        return found
    return shutil.which("bash")


@pytest.mark.parametrize("script_name", BUILD_SCRIPTS)
def test_build_help_works_outside_repository_without_build_tools(
    tmp_path: Path, script_name: str
) -> None:
    script = PROJECT_ROOT / script_name
    assert script.is_file(), f"Missing distributable build script: {script_name}"
    environment = dict(os.environ, PATH="")
    if script.suffix == ".bat":
        command = [os.environ["COMSPEC"], "/d", "/c", str(script), "--help"]
    else:
        bash = _find_bash()
        if bash is None:
            pytest.skip("A Unix-compatible bash was not found on this system")
        command = [bash, script.as_posix(), "--help"]
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Usage:" in result.stdout
    assert "dist" in result.stdout
    assert not (tmp_path / "dist").exists()


@pytest.mark.parametrize(
    "script_name, operating_system",
    [("build.sh", "Linux"), ("build.sh", "Darwin")]
    + ([("build.bat", "Windows")] if sys.platform == "win32" else []),
)
@pytest.mark.parametrize(
    "failure_stage", [None, "sync", "ci", "build", "pyinstaller", "missing_executable"]
)
def test_build_creates_archive_from_any_working_directory(
    tmp_path: Path, script_name: str, operating_system: str, failure_stage: str | None
) -> None:
    if script_name == "build.sh" and sys.platform == "win32":
        pytest.skip("build.sh platform simulation is only tested on Unix platforms")
    repository = tmp_path / "checkout with spaces"
    repository.mkdir()
    shutil.copy2(PROJECT_ROOT / script_name, repository / script_name)
    shutil.copy2(PROJECT_ROOT / "pyproject.toml", repository / "pyproject.toml")
    shutil.copy2(PROJECT_ROOT / "LICENSE", repository / "LICENSE")
    (repository / "dashboard").mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    log = tmp_path / "commands.jsonl"
    helper = tools / "command.py"
    helper.write_text(
        "import json, os, pathlib, subprocess, sys\n"
        "tool, *arguments = sys.argv[1:]\n"
        "with open(os.environ['BUILD_TEST_LOG'], 'a') as log:\n"
        "    log.write(json.dumps([tool, str(pathlib.Path.cwd()), arguments]) + '\\n')\n"
        "if os.environ.get('BUILD_TEST_FAILURE') in arguments:\n"
        "    sys.exit(17)\n"
        "if tool == 'uv' and arguments[:2] == ['run', '--no-sync']:\n"
        "    if arguments[2] == 'pyinstaller':\n"
        "        if os.environ.get('BUILD_TEST_FAILURE') == 'missing_executable':\n"
        "            sys.exit(0)\n"
        "        bundle = pathlib.Path('dist/wexo')\n"
        "        bundle.mkdir(parents=True, exist_ok=True)\n"
        "        (bundle / 'wexo.exe').write_text('test executable')\n"
        "        (bundle / 'wexo').write_text('test executable')\n"
        "    elif arguments[2] == 'python':\n"
        "        sys.exit(subprocess.call([sys.executable, *arguments[3:]]))\n",
        encoding="utf-8",
    )
    for tool in ("uv", "npm", "node", "cargo", "rustc", "macmon"):
        if script_name.endswith(".bat"):
            (tools / f"{tool}.cmd").write_text(
                f'@"{sys.executable}" "{helper}" {tool} %*\n@exit /b %errorlevel%\n',
                encoding="utf-8",
            )
        else:
            executable = tools / tool
            executable.write_text(
                f'#!/usr/bin/env bash\nexec "{Path(sys.executable).as_posix()}" '
                f'"{helper.as_posix()}" {tool} "$@"\n',
                encoding="utf-8",
            )
            executable.chmod(0o755)
    environment = dict(
        os.environ,
        PATH=str(tools) + os.pathsep + os.environ["PATH"],
        BUILD_TEST_LOG=str(log),
        BUILD_TEST_FAILURE=failure_stage or "",
    )
    if script_name.endswith(".bat"):
        command = [os.environ["COMSPEC"], "/d", "/c", str(repository / script_name)]
    else:
        bash = _find_bash()
        if bash is None:
            pytest.skip("A Unix-compatible bash was not found on this system")
        command = [bash, (repository / script_name).as_posix()]
        # Stub platform detection, not a claim of a native Unix build.
        uname = tools / "uname"
        uname.write_text(
            f'#!/usr/bin/env bash\nprintf "{operating_system}\\n"\n', encoding="utf-8"
        )
        uname.chmod(0o755)
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if failure_stage is not None:
        assert result.returncode != 0, result.stdout + result.stderr
        assert not list((repository / "dist").glob("wexo-*"))
        return
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(
        item[0] == "uv" and item[2][:2] == ["sync", "--locked"] for item in commands
    )
    dashboard_commands = [item for item in commands if item[0] == "npm"]
    assert [item[2] for item in dashboard_commands] == [
        ["ci", "--include=dev"],
        ["run", "build"],
    ]
    assert all(Path(item[1]) == repository / "dashboard" for item in dashboard_commands)
    archives = list((repository / "dist").glob("wexo-*"))
    assert len(archives) == 1
    extracted = tmp_path / "extracted"
    if archives[0].suffix == ".zip":
        shutil.unpack_archive(str(archives[0]), str(extracted))
    else:
        shutil.unpack_archive(str(archives[0]), str(extracted), filter="data")
    assert (extracted / "wexo" / "LICENSE").is_file()
    executable_name = "wexo.exe" if script_name.endswith(".bat") else "wexo"
    assert (extracted / "wexo" / executable_name).is_file()
