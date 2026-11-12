#!/usr/bin/env python3
"""Create a source-only release with pinned NESRecomp, recomp-ui and SDL2 sources.

No Excitebike ROM, ROM-derived generated code, executable, save or local build
product is placed in the archive.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "ExcitebikeNESRecompiled"
ROOT_FILES = (
    ".gitmodules",
    ".gitignore",
    "README.md",
    "CMakeLists.txt",
    "game.toml",
    "setup.sh",
    "setup.bat",
    "cmake/bundled-sdl2/SDL2Config.cmake",
    "tools/bootstrap.sh",
    "tools/bootstrap.ps1",
    "tools/build.sh",
    "tools/build.ps1",
    "tools/package_source.py",
    "tests/create_smoke_rom.py",
    ".github/workflows/source-release.yml",
)
DEPENDENCIES = ("nesrecomp", "recomp-ui", "SDL2")
REQUIRED_DEPENDENCY_FILES = {
    "nesrecomp": "runner/cyc/project.cmake",
    "recomp-ui": "recomp_ui.cmake",
    "SDL2": "CMakeLists.txt",
}
SKIP_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "venv",
    "node_modules", "CMakeFiles", "cmake-build-debug", "cmake-build-release",
    "build", "build-debug", "build-release",
}
SKIP_SUFFIXES = {
    ".nes", ".unf", ".unif", ".fds", ".qd", ".rom", ".sav", ".cycstate",
    ".ips", ".dsv", ".state",
}


def git_revision(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def dependency_files(root: Path):
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        base = Path(directory)
        for name in sorted(files):
            path = base / name
            if name == ".git" or path.is_symlink():
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            if path.is_file():
                yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    for name in ROOT_FILES:
        if not (ROOT / name).is_file():
            raise SystemExit(f"Required source file is missing: {name}")

    for dependency, required in REQUIRED_DEPENDENCY_FILES.items():
        if not (ROOT / dependency / required).is_file():
            raise SystemExit(f"Pinned dependency is incomplete: {dependency}/{required}")

    revisions = [
        f"{name}: {git_revision(ROOT / name)}"
        for name in DEPENDENCIES
    ]

    entries: list[tuple[Path, str]] = []
    for name in ROOT_FILES:
        source = ROOT / name
        entries.append((source, f"{ARCHIVE_ROOT}/{name}"))

    for name in DEPENDENCIES:
        for source in dependency_files(ROOT / name):
            relative = source.relative_to(ROOT)
            entries.append((source, f"{ARCHIVE_ROOT}/{relative.as_posix()}"))

    metadata = (
        "ExcitebikeNESRecompiled source release\n"
        "Source-only package. It includes pinned dependency sources and local "
        "build/bootstrap scripts.\n"
        "No Excitebike ROM, ROM-derived generated C source, playable binary, "
        "save, or local build output is included.\n\n"
        "Pinned dependency revisions:\n"
        + "\n".join(revisions)
        + "\n"
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for source, archive_name in entries:
            archive.write(source, archive_name)
        archive.writestr(
            f"{ARCHIVE_ROOT}/SOURCE-DEPENDENCIES.txt", metadata
        )

    with zipfile.ZipFile(args.output) as archive:
        names = archive.namelist()
        forbidden = [
            name for name in names
            if Path(name).suffix.lower() in SKIP_SUFFIXES
        ]
        if forbidden:
            args.output.unlink(missing_ok=True)
            raise SystemExit(
                "Refusing to publish source archive containing ROM/save-like "
                f"files: {forbidden[:5]}"
            )

    print(f"Created source-only release: {args.output}")
    print(f"Included {len(entries)} files")
    print("Pinned dependencies: " + ", ".join(revisions))
    print(f"Archive size: {args.output.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
