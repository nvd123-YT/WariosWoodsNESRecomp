#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ $# -lt 1 ]; then
  echo "Usage: $0 /absolute/path/to/Excitebike.nes" >&2
  exit 2
fi
ROM="$1"
[ -f "$ROM" ] || { echo "ROM not found: $ROM" >&2; exit 2; }

bash "$ROOT/setup.sh"
CMAKE_BIN="$(cat "$ROOT/.tools/cmake-path.txt")"
PYTHON_BIN="$(cat "$ROOT/.tools/python-path.txt")"
export PATH="$(dirname "$PYTHON_BIN"):$PATH"

"$CMAKE_BIN" -S "$ROOT" -B "$ROOT/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DNESRECOMP_ROM="$ROM"
"$CMAKE_BIN" --build "$ROOT/build" --parallel 4

echo "Launching Excitebike..."
exec "$ROOT/build/ExcitebikeRecomp" "$ROM"
