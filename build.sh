#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    'Usage: bash build.sh [--help]' \
    'Build the standalone wexo runtime, archive, and DMG (macOS) in dist/ on macOS or Linux.'
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
if [[ "$platform" == macos ]]; then
  if ! command -v macmon >/dev/null 2>&1; then
    printf '%s\n' \
      'ERROR: Install the pinned macmon before building on macOS:' \
      'cargo install --git https://github.com/vladkens/macmon --rev a1cd06b6cc0d5e61db24fd8832e74cd992097a7d macmon --force' >&2
    exit 1
  fi
  if [[ -d "app/EXO/EXO.xcodeproj" ]] && ! command -v xcodebuild >/dev/null 2>&1; then
    printf 'ERROR: Required macOS tool not found in PATH: xcodebuild\n' >&2
    exit 1
  fi
fi

total_steps=4
if [[ "$platform" == macos ]] && [[ -d "app/EXO/EXO.xcodeproj" ]]; then
  total_steps=5
fi

printf '%s\n' "[1/${total_steps}] Installing locked Python dependencies and building Rust bindings..."
uv sync --locked --group dev

printf '%s\n' "[2/${total_steps}] Building the dashboard..."
(
  cd dashboard
  npm ci --include=dev
  npm run build
)

printf '%s\n' "[3/${total_steps}] Building the standalone runtime..."
uv run --no-sync pyinstaller --noconfirm --clean --workpath dist/.build packaging/pyinstaller/exo.spec

printf '%s\n' "[4/${total_steps}] Creating the distributable archive..."
uv run --no-sync python -c 'import platform, shutil, sys, tomllib; from pathlib import Path; bundle = Path("dist/wexo"); executable = bundle / "wexo"; assert executable.is_file(), f"Missing executable: {executable}"; shutil.copy2("LICENSE", bundle / "LICENSE"); version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]; name = f"dist/wexo-{version}-{sys.argv[1]}-{platform.machine().lower()}"; archive = shutil.make_archive(name, "gztar", root_dir="dist", base_dir="wexo"); print(f"Archive complete: {Path(archive).resolve()}")' "$platform"

if [[ "$platform" == macos ]] && [[ -d "app/EXO/EXO.xcodeproj" ]]; then
  printf '%s\n' "[5/${total_steps}] Building macOS application and creating DMG package..."
  configuration="${EXO_BUILD_CONFIGURATION:-Debug}"
  env -u LD xcodebuild build \
    -project app/EXO/EXO.xcodeproj \
    -scheme EXO \
    -configuration "$configuration" \
    -derivedDataPath app/EXO/build \
    CODE_SIGNING_ALLOWED=NO
  app_path="app/EXO/build/Build/Products/${configuration}/EXO.app"
  if [[ ! -d "$app_path" ]]; then
    printf 'ERROR: Built application not found: %s\n' "$app_path" >&2
    exit 1
  fi
  dmg_path="dist/EXO.dmg"
  bash packaging/dmg/create-dmg.sh "$app_path" "$dmg_path" "EXO"
  uv run --no-sync python -c 'import platform, shutil, tomllib; from pathlib import Path; version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]; src = Path("dist/EXO.dmg"); dst = Path(f"dist/wexo-{version}-macos-{platform.machine().lower()}.dmg"); shutil.copy2(src, dst); print(f"DMG complete: {dst.resolve()}")'
fi
