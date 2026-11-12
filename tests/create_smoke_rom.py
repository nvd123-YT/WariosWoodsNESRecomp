#!/usr/bin/env python3
"""Create a tiny synthetic NROM image for CI smoke tests (not a commercial game)."""
from __future__ import annotations

import argparse
from pathlib import Path


def make_test_rom() -> bytes:
    header = bytearray(16)
    header[0:4] = b"NES\x1a"
    header[4] = 1  # 16 KiB PRG-ROM
    header[5] = 1  # 8 KiB CHR-ROM
    header[6] = 0  # NROM, horizontal mirroring
    header[7] = 0

    prg = bytearray([0xEA] * 0x4000)
    # Reset/NMI/IRQ vectors all point to an infinite JMP $8000 loop.
    prg[0:3] = bytes((0x4C, 0x00, 0x80))
    for offset in (0x3FFA, 0x3FFC, 0x3FFE):
        prg[offset : offset + 2] = bytes((0x00, 0x80))

    chr_rom = bytes(0x2000)
    return bytes(header) + bytes(prg) + chr_rom


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(make_test_rom())
    print(f"Created synthetic NROM CI fixture: {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
