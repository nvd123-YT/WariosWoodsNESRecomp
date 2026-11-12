#!/usr/bin/env python3
"""Verify that the SDL presentation smoke test produced a wide NES frame."""
from __future__ import annotations

import argparse
import glob
import struct
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise SystemExit(f"Not a valid PNG image: {path}")
    return struct.unpack(">II", header[16:24])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path, help="--present-out base path (numbered PNGs are also accepted)")
    parser.add_argument("--width", type=int, default=426)
    parser.add_argument("--height", type=int, default=240)
    args = parser.parse_args()

    candidates = [args.base] if args.base.is_file() else []
    if not candidates:
        pattern = str(args.base.with_name(args.base.stem + "_*" + args.base.suffix))
        candidates = [Path(name) for name in sorted(glob.glob(pattern))]
    if not candidates:
        raise SystemExit(f"No presentation PNG was created from base path: {args.base}")

    for path in candidates:
        dimensions = png_dimensions(path)
        width, height = dimensions
        scale_x = width // args.width if args.width > 0 else 0
        scale_y = height // args.height if args.height > 0 else 0
        if (
            scale_x >= 1
            and scale_x == scale_y
            and width == args.width * scale_x
            and height == args.height * scale_y
        ):
            print(
                f"Verified widescreen output: {path} "
                f"({width}x{height}, {scale_x}x logical {args.width}x{args.height})"
            )
            return 0
    observed = ", ".join(f"{p.name}={png_dimensions(p)[0]}x{png_dimensions(p)[1]}" for p in candidates)
    raise SystemExit(
        f"No widescreen frame had the expected {args.width}x{args.height} size; got {observed}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
