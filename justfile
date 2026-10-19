export NIX_CONFIG := "extra-experimental-features = nix-command flakes"

# Run Windows recipes in PowerShell so they don't depend on Git Bash's sh.
[windows]
set shell := ["powershell.exe", "-NoLogo", "-Command"]

# ---- dev: format / lint / test / type-check ----------------------------------

# fmt shells out to treefmt/nix, which are unix-only.
[unix]
default: lint fmt

[unix]
all: lint fmt check

[unix]
fmt:
    treefmt || nix fmt

lint:
    uv run ruff check --fix

test:
    uv run pytest src

check:
    uv run basedpyright --project pyproject.toml

# ---- dependencies ------------------------------------------------------------

sync:
    python scripts/sync_gpu.py

sync-clean:
    python scripts/sync_gpu.py --force-reinstall --no-cache

# Select PyTorch CUDA or ROCm on Windows when an appropriate GPU is present.
sync-windows:
    python scripts/sync_gpu.py

sync-clean-windows:
    python scripts/sync_gpu.py --force-reinstall --no-cache

[unix]
rust-rebuild:
    PYO3_PYTHON="$(uv run python -c 'import sys; print(sys.executable)')" cargo run --bin stub_gen
    uv sync --reinstall-package exo_rs

# A fresh PowerShell per line means PYO3_PYTHON must be set on the same line as cargo.
[windows]
rust-rebuild:
    $env:PYO3_PYTHON = uv run python -c 'import sys; print(sys.executable)'; cargo run --bin stub_gen
    uv sync --reinstall-package exo_rs

# ---- build -------------------------------------------------------------------

# `npm install --prefix dashboard` does not redirect npm to dashboard/ — npm
# resolves the project from the working directory instead (npm/cli#5462).

# Build the dashboard into dashboard/build/.
[working-directory: 'dashboard']
build-dashboard:
    npm install
    npm run build

[unix]
package: build-dashboard
    uv run pyinstaller packaging/pyinstaller/exo.spec
    rm -rf build

[windows]
package: build-dashboard
    uv run pyinstaller packaging/pyinstaller/exo.spec
    Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue

# macOS: full clean build of the Swift app. Xcode bundles dist/wexo into the .app.
[macos]
build-app: rust-rebuild sync-clean package
    env -u LD xcodebuild build -project app/EXO/EXO.xcodeproj -scheme EXO -configuration Debug -derivedDataPath app/EXO/build
    @echo "Build complete. Run with:"
    @echo "  open {{ justfile_directory() }}/app/EXO/build/Build/Products/Debug/EXO.app"

[macos]
dmg: build-app
    bash packaging/dmg/create-dmg.sh app/EXO/build/Build/Products/Debug/EXO.app dist/EXO.dmg EXO

# Windows: full clean build of the launcher executable (launcher + server).
[windows]
build-app: rust-rebuild sync-clean-windows package
    @echo "Build complete: {{ justfile_directory() }}/dist/wexo/wexo.exe"

# ---- clean -------------------------------------------------------------------

[unix]
clean:
    rm -rf **/__pycache__
    rm -rf target/
    rm -rf .venv
    rm -rf dashboard/node_modules
    rm -rf dashboard/.svelte-kit
    rm -rf dashboard/build
