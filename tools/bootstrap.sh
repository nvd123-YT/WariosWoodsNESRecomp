#!/usr/bin/env bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
DOWNLOADS="$TOOLS/downloads"
CMAKE_VERSION="3.31.6"
UV_VERSION="0.6.14"
PYTHON_VERSION="3.12.9"

mkdir -p "$TOOLS/bin" "$DOWNLOADS" "$TOOLS/uv" "$TOOLS/python"

fail() { echo "ERROR: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Required system command not found: $1"; }
need curl
need tar
need git

OS="$(uname -s)"
ARCH="$(uname -m)"

clear_macos_quarantine() {
  [ "$OS" = "Darwin" ] || return 0
  command -v xattr >/dev/null 2>&1 || return 0
  for tool_dir in "$@"; do
    if [ -d "$tool_dir" ]; then
      echo "[macOS] Clearing Gatekeeper quarantine from verified tool folder: $tool_dir"
      xattr -dr com.apple.quarantine "$tool_dir" 2>/dev/null || true
    fi
  done
}

case "$OS-$ARCH" in
  Darwin-arm64)
    UV_ARCHIVE="uv-aarch64-apple-darwin.tar.gz"
    ;;
  Darwin-x86_64)
    UV_ARCHIVE="uv-x86_64-apple-darwin.tar.gz"
    ;;
  Linux-x86_64)
    CMAKE_ARCHIVE="cmake-$CMAKE_VERSION-linux-x86_64.tar.gz"
    UV_ARCHIVE="uv-x86_64-unknown-linux-gnu.tar.gz"
    ;;
  Linux-aarch64|Linux-arm64)
    CMAKE_ARCHIVE="cmake-$CMAKE_VERSION-linux-aarch64.tar.gz"
    UV_ARCHIVE="uv-aarch64-unknown-linux-gnu.tar.gz"
    ;;
  *)
    fail "Unsupported platform $OS-$ARCH. Use setup.bat on Windows."
    ;;
esac

UV_URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$UV_ARCHIVE"

echo "[1/4] Preparing portable uv $UV_VERSION..."
UV_BIN="$(find "$TOOLS/uv" -type f -name uv -perm -111 -print -quit 2>/dev/null || true)"
if [ -z "$UV_BIN" ]; then
  TMP="$DOWNLOADS/$UV_ARCHIVE"
  curl -fL --retry 3 --retry-delay 2 "$UV_URL" -o "$TMP"
  curl -fL --retry 3 --retry-delay 2 "$UV_URL.sha256" -o "$TMP.sha256"
  EXPECTED="$(awk '{print $1; exit}' "$TMP.sha256")"
  if command -v shasum >/dev/null 2>&1; then
    ACTUAL="$(shasum -a 256 "$TMP" | awk '{print $1}')"
  else
    ACTUAL="$(sha256sum "$TMP" | awk '{print $1}')"
  fi
  [ "$ACTUAL" = "$EXPECTED" ] || fail "uv archive checksum mismatch"
  tar -xzf "$TMP" -C "$TOOLS/uv"
  UV_BIN="$(find "$TOOLS/uv" -type f -name uv -perm -111 -print -quit)"
fi
[ -x "$UV_BIN" ] || fail "Portable uv was not found after extraction"
clear_macos_quarantine "$TOOLS/uv"
printf '%s\n' "$UV_BIN" > "$TOOLS/uv-path.txt"

echo "[2/4] Installing managed Python $PYTHON_VERSION into .tools..."
export UV_PYTHON_INSTALL_DIR="$TOOLS/python"
export UV_PYTHON_BIN_DIR="$TOOLS/bin"
"$UV_BIN" python install "$PYTHON_VERSION"
PYTHON_BIN="$("$UV_BIN" python find "$PYTHON_VERSION")"
[ -x "$PYTHON_BIN" ] || fail "Managed Python executable not found"
clear_macos_quarantine "$TOOLS/python"
printf '%s\n' "$PYTHON_BIN" > "$TOOLS/python-path.txt"
"$PYTHON_BIN" --version

echo "[3/4] Preparing portable CMake $CMAKE_VERSION..."
if [ "$OS" = "Darwin" ]; then
  # Avoid nesting Kitware's CMake.app inside the Excitebike app bundle.
  # The universal2 PyPI wheel carries the relocatable CLI binary and CMake data.
  CMAKE_BIN="$TOOLS/cmake/cmake/data/bin/cmake"
  if [ ! -f "$CMAKE_BIN" ]; then
    rm -rf "$TOOLS/cmake"
    mkdir -p "$TOOLS/cmake"
    echo "[macOS] Installing the universal2 CMake command-line wheel (no nested CMake.app)..."
    "$UV_BIN" pip install --python "$PYTHON_BIN" --target "$TOOLS/cmake" --no-deps "cmake==$CMAKE_VERSION"
  fi
  CMAKE_BIN="$TOOLS/cmake/cmake/data/bin/cmake"
  [ -f "$CMAKE_BIN" ] || fail "The standalone CMake wheel did not contain cmake/data/bin/cmake"
  chmod +x "$CMAKE_BIN"
  [ ! -d "$TOOLS/cmake/CMake.app" ] || fail "Unexpected nested CMake.app found in portable macOS CMake bundle"
  clear_macos_quarantine "$TOOLS/cmake"
else
  mkdir -p "$TOOLS/cmake"
  CMAKE_URL="https://github.com/Kitware/CMake/releases/download/v$CMAKE_VERSION/$CMAKE_ARCHIVE"
  CMAKE_CHECKS_URL="https://github.com/Kitware/CMake/releases/download/v$CMAKE_VERSION/cmake-$CMAKE_VERSION-SHA-256.txt"
  CMAKE_BIN="$(find "$TOOLS/cmake" -type f -name cmake -perm -111 -print -quit 2>/dev/null || true)"
  if [ -z "$CMAKE_BIN" ]; then
    TMP="$DOWNLOADS/$CMAKE_ARCHIVE"
    curl -fL --retry 3 --retry-delay 2 "$CMAKE_URL" -o "$TMP"
    curl -fL --retry 3 --retry-delay 2 "$CMAKE_CHECKS_URL" -o "$DOWNLOADS/cmake-checksums.txt"
    EXPECTED="$(awk -v n="$CMAKE_ARCHIVE" '$2 == n || $2 == "*" n {print $1; exit}' "$DOWNLOADS/cmake-checksums.txt")"
    [ -n "$EXPECTED" ] || fail "Could not find CMake checksum for $CMAKE_ARCHIVE"
    if command -v shasum >/dev/null 2>&1; then
      ACTUAL="$(shasum -a 256 "$TMP" | awk '{print $1}')"
    else
      ACTUAL="$(sha256sum "$TMP" | awk '{print $1}')"
    fi
    [ "$ACTUAL" = "$EXPECTED" ] || fail "CMake archive checksum mismatch"
    tar -xzf "$TMP" -C "$TOOLS/cmake"
    CMAKE_BIN="$(find "$TOOLS/cmake" -type f -name cmake -perm -111 -print -quit)"
  fi
  [ -x "$CMAKE_BIN" ] || fail "Portable CMake was not found after extraction"
fi

[ -x "$CMAKE_BIN" ] || fail "Portable CMake executable is not runnable"
printf '%s\n' "$CMAKE_BIN" > "$TOOLS/cmake-path.txt"
"$CMAKE_BIN" --version | head -1

echo "[4/4] Checking pinned source dependencies..."
for required in \
  "$ROOT/nesrecomp/runner/cyc/project.cmake" \
  "$ROOT/recomp-ui/recomp_ui.cmake" \
  "$ROOT/SDL2/CMakeLists.txt" \
  "$ROOT/cmake/bundled-sdl2/SDL2Config.cmake"; do
  [ -f "$required" ] || fail "Missing $required. Run git submodule update --init --recursive."
done

if [ ! -x /usr/bin/clang ] && ! command -v cc >/dev/null 2>&1; then
  fail "A native C/C++ compiler is required. Install Xcode Command Line Tools or your platform's compiler."
fi

echo "Bootstrap complete."
echo "Portable CMake: $CMAKE_BIN"
echo "Managed Python: $PYTHON_BIN"
echo "SDL2, NESRecomp and recomp-ui source are pinned in the repository."
echo "Native platform compiler/SDK remains an OS prerequisite."
