#!/usr/bin/env python3
"""Verify the built-in NESRecomp packages staged for a generated game."""
from __future__ import annotations

import argparse
from pathlib import Path


def read_manifest(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"Required built-in package manifest is missing: {path}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", required=True, type=Path)
    args = parser.parse_args()

    roots = (args.build_dir, args.build_dir / "Release")
    package_files = {
        "replay": Path("mods/packages/nesrecomp.developer.replay/1.0.0/manifest.toml"),
        "chat": Path("mods/packages/nesrecomp.twitch-chat/1.0.0/manifest.toml"),
    }
    found: dict[str, Path] = {}
    for name, relative in package_files.items():
        candidate = next((root / relative for root in roots if (root / relative).is_file()), None)
        if candidate is None:
            raise SystemExit(f"NESRecomp {name} package was not staged under {args.build_dir}")
        found[name] = candidate

    replay = read_manifest(found["replay"])
    for required in (
        'id = "nesrecomp.developer.replay"',
        'name = "Replay Capture"',
        'game_id = "excitebike-nes"',
        'id = "replay-capture"',
        "default_enabled = true",
        'id = "nesrecomp.replay-capture"',
    ):
        if required not in replay:
            raise SystemExit(f"Replay Capture manifest is missing required field: {required}")

    chat = read_manifest(found["chat"])
    for required in (
        'id = "nesrecomp.twitch-chat"',
        'name = "Twitch Chat"',
        'game_id = "excitebike-nes"',
        'id = "chat"',
        "default_enabled = false",
        'id = "nesrecomp.twitch-chat"',
    ):
        if required not in chat:
            raise SystemExit(f"Twitch Chat manifest is missing required field: {required}")

    print("Verified bundled NESRecomp Mods packages:")
    print(f"  Replay Capture: {found['replay']}")
    print(f"  Twitch Chat:    {found['chat']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
