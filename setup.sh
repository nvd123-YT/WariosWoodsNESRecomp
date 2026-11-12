#!/usr/bin/env bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: Git is required." >&2
  exit 1
fi

echo "Initializing pinned NESRecomp, recomp-ui and SDL2 submodules..."
git submodule update --init --recursive

for required in \
  "nesrecomp/runner/cyc/project.cmake" \
  "recomp-ui/recomp_ui.cmake" \
  "recomp-ui/src/recomp_runtime_ui.h" \
  "SDL2/CMakeLists.txt" \
  "cmake/bundled-sdl2/SDL2Config.cmake"; do
  if [ ! -f "$required" ]; then
    echo "ERROR: required dependency file missing: $required" >&2
    exit 1
  fi
done

echo "Bootstrapping portable CMake and Python..."
bash "$ROOT/tools/bootstrap.sh"

echo "Setup complete. Use:"
echo "  bash tools/build.sh \"/path/to/Excitebike.nes\""
