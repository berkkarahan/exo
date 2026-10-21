#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    'Usage: bash build.sh [--help]' \
    'Build the standalone wexo runtime and archive in dist/ on macOS or Linux.'
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
esac
if [[ $# -ne 0 ]]; then
  usage >&2
  exit 2
fi

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

case "$(uname -s)" in
  Darwin) platform=macos ;;
  Linux) platform=linux ;;
  *) printf '%s\n' 'ERROR: Run build.bat on Windows; build.sh supports macOS and Linux.' >&2; exit 1 ;;
esac

for tool in uv node npm cargo rustc; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'ERROR: Required tool not found in PATH: %s\n' "$tool" >&2
    exit 1
  fi
done
if [[ "$platform" == macos ]] && ! command -v macmon >/dev/null 2>&1; then
  printf '%s\n' \
    'ERROR: Install the pinned macmon before building on macOS:' \
    'cargo install --git https://github.com/vladkens/macmon --rev a1cd06b6cc0d5e61db24fd8832e74cd992097a7d macmon --force' >&2
  exit 1
fi

printf '%s\n' '[1/4] Installing locked Python dependencies and building Rust bindings...'
uv sync --locked --group dev

printf '%s\n' '[2/4] Building the dashboard...'
(
  cd dashboard
  npm ci --include=dev
  npm run build
)

printf '%s\n' '[3/4] Building the standalone runtime...'
uv run --no-sync pyinstaller --noconfirm --clean --workpath dist/.build packaging/pyinstaller/exo.spec

printf '%s\n' '[4/4] Creating the distributable archive...'
uv run --no-sync python -c 'import platform, shutil, sys, tomllib; from pathlib import Path; bundle = Path("dist/wexo"); executable = bundle / "wexo"; assert executable.is_file(), f"Missing executable: {executable}"; shutil.copy2("LICENSE", bundle / "LICENSE"); version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]; name = f"dist/wexo-{version}-{sys.argv[1]}-{platform.machine().lower()}"; archive = shutil.make_archive(name, "gztar", root_dir="dist", base_dir="wexo"); print(f"Build complete: {Path(archive).resolve()}")' "$platform"
