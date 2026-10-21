@echo off
setlocal EnableExtensions DisableDelayedExpansion
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h" goto :usage
if not "%~1"=="" (
    call :usage
    exit /b 2
)

pushd "%~dp0" || exit /b 1
for %%T in (uv node npm cargo rustc) do (
    where %%T >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Required tool not found in PATH: %%T 1>&2
        goto :failed
    )
)

echo [1/4] Installing locked Python dependencies and building Rust bindings...
call uv sync --locked --group dev
if errorlevel 1 goto :failed

echo [2/4] Building the dashboard...
pushd dashboard || goto :failed
call npm ci --include=dev
if errorlevel 1 goto :dashboard_failed
call npm run build
if errorlevel 1 goto :dashboard_failed
popd

echo [3/4] Building the standalone runtime...
call uv run --no-sync pyinstaller --noconfirm --clean --workpath dist/.build packaging/pyinstaller/exo.spec
if errorlevel 1 goto :failed

echo [4/4] Creating the distributable archive...
call uv run --no-sync python -c "import platform, shutil, tomllib; from pathlib import Path; bundle = Path('dist/wexo'); executable = bundle / 'wexo.exe'; assert executable.is_file(), f'Missing executable: {executable}'; shutil.copy2('LICENSE', bundle / 'LICENSE'); version = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version']; name = f'dist/wexo-{version}-windows-{platform.machine().lower()}'; archive = shutil.make_archive(name, 'zip', root_dir='dist', base_dir='wexo'); print(f'Build complete: {Path(archive).resolve()}')"
if errorlevel 1 goto :failed
popd
exit /b 0

:dashboard_failed
popd

:failed
echo ERROR: wexo build failed. See the output above. 1>&2
popd
exit /b 1

:usage
echo Usage: build.bat [--help]
echo Build the standalone wexo runtime and archive in dist\ on Windows.
exit /b 0
