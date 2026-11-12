#!/usr/bin/env python3
"""Create the self-contained, ROM-free payload used by platform builder apps."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = ("nesrecomp", "recomp-ui", "SDL2")
ROOT_FILES = ("CMakeLists.txt", "game.toml")
REQUIRED_DEPENDENCY_FILES = (
    "nesrecomp/runner/cyc/project.cmake",
    "nesrecomp/runner/cyc/cyc.cmake",
    "recomp-ui/recomp_ui.cmake",
    "recomp-ui/src/recomp_launcher.h",
    "recomp-ui/src/third_party/imgui/imgui.cpp",
)
TOOL_DIRECTORIES = (".tools/cmake", ".tools/python")
SKIP_DIRECTORIES = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules",
    "CMakeFiles", "build", "build-ci", "dist", "pyinstaller-work",
}
SKIP_SUFFIXES = {
    ".nes", ".unf", ".unif", ".fds", ".qd", ".rom", ".sav", ".cycstate",
    ".ips", ".dsv", ".state",
}


def revision(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def iter_files(directory: Path):
    for current, dirs, files in os.walk(directory):
        dirs[:] = sorted(
            name for name in dirs
            if name not in SKIP_DIRECTORIES and name not in {"downloads", "uv"}
        )
        base = Path(current)
        for name in sorted(files):
            item = base / name
            if name == ".git" or item.is_symlink():
                continue
            if item.suffix.lower() in SKIP_SUFFIXES:
                continue
            if item.is_file():
                yield item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    required = [ROOT / name for name in ROOT_FILES]
    required.extend(ROOT / name for name in DEPENDENCIES)
    required.extend(ROOT / name for name in TOOL_DIRECTORIES)
    required.extend(ROOT / name for name in REQUIRED_DEPENDENCY_FILES)
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Cannot package launcher; required source/tools missing: " + ", ".join(missing))

    for name in DEPENDENCIES:
        if not any((ROOT / name).iterdir()):
            raise SystemExit(f"Pinned dependency checkout is empty: {name}")

    entries: list[tuple[Path, str]] = []
    for name in ROOT_FILES:
        entries.append((ROOT / name, f"project/{name}"))

    for name in ("cmake", "src", "nesrecomp", "recomp-ui", "SDL2"):
        for source in iter_files(ROOT / name):
            relative = source.relative_to(ROOT)
            entries.append((source, "project/" + relative.as_posix()))

    for name in TOOL_DIRECTORIES:
        for source in iter_files(ROOT / name):
            relative = source.relative_to(ROOT)
            entries.append((source, "project/" + relative.as_posix()))

    metadata = [
        "Excitebike Recompiled local-build launcher resources",
        "No ROM, ROM-derived native game code, saves, or built game executable is included.",
        "The user selects a compatible local ROM in the launcher; code generation and game compilation happen on that user's computer.",
        "Bundled build tools: portable CMake and managed Python runtime.",
        "Platform compiler/SDK is supplied by the host operating system.",
        "",
        "The full NESRecomp and recomp-ui source trees are bundled, including the NESRecomp mod runtime/package generators and recomp-ui launcher assets/ImGui sources.",
        "The game build stages NESRecomp Replay Capture (default on) and Twitch Chat (default off) manifests beside the generated executable.",
        "",
        "Pinned dependency revisions:",
    ]
    for name in DEPENDENCIES:
        metadata.append(f"{name}: {revision(ROOT / name)}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(
        args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=4
    ) as archive:
        for source, target in entries:
            archive.write(source, target)
            count += 1
        archive.writestr("project/BUILD-RESOURCES.txt", os.linesep.join(metadata) + os.linesep)

    with zipfile.ZipFile(args.output) as archive:
        unsafe = [
            name for name in archive.namelist()
            if Path(name).suffix.lower() in SKIP_SUFFIXES
        ]
        if unsafe:
            args.output.unlink(missing_ok=True)
            raise SystemExit("Refusing to bundle ROM/save-like files: " + ", ".join(unsafe[:5]))
        required_members = {
            "project/nesrecomp/runner/cyc/project.cmake",
            "project/nesrecomp/runner/cyc/cyc.cmake",
            "project/recomp-ui/recomp_ui.cmake",
            "project/recomp-ui/src/recomp_launcher.h",
            "project/recomp-ui/src/third_party/imgui/imgui.cpp",
        }
        missing_members = sorted(required_members.difference(archive.namelist()))
        if missing_members:
            args.output.unlink(missing_ok=True)
            raise SystemExit("The payload is missing required NESRecomp/recomp-ui package files: " + ", ".join(missing_members))

    print(f"Created builder payload with {count} source/tool files.")
    print(f"Payload size: {args.output.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
