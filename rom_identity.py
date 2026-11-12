"""Exact Wario's Woods NES ROM identification using this project's own dump fingerprints.

Only Wario's Woods fingerprints are present in this module. It does not catalog
or identify any other game. Hashes cover headerless PRG+CHR bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import zlib


@dataclass(frozen=True)
class RomFingerprint:
    title: str
    region: str
    mapper: int
    prg_size: int
    chr_size: int
    prg_crc32: int
    chr_crc32: int
    body_crc32: int
    body_sha1: str


@dataclass(frozen=True)
class RomIdentity:
    title: str
    region: str
    mapper: int
    body_crc32: int
    body_sha1: str


class RomIdentityError(ValueError):
    """Raised when a selected file is not a verified dump for this launcher."""


GAME_TITLE = "Wario's Woods"
ROM_FINGERPRINTS: tuple[RomFingerprint, ...] = (
    RomFingerprint(
        "Wario's Woods", "USA (NTSC)", 4,
        262144, 262144,
        0x1AFB26D7, 0xEB133A6D, 0xF79A75D7,
        "602f640b3fe0ca47cf47de6688779419a75487ac",
    ),
    RomFingerprint(
        "Wario's Woods", "Europe (PAL)", 4,
        262144, 262144,
        0xB24F0357, 0x0146D148, 0x668D1715,
        "1cec3b2e93e81f0353be25ad139addae881dc69a",
    ),
)


def _nes2_size(lsb: int, msb_nibble: int, unit: int) -> int:
    """Decode an NES 2.0 ROM size field."""
    if msb_nibble == 0x0F:
        exponent = lsb >> 2
        multiplier = lsb & 0x03
        return (1 << exponent) * (2 * multiplier + 1)
    return ((msb_nibble << 8) | lsb) * unit


def _rom_sizes(header: bytes) -> tuple[int, int]:
    if (header[7] & 0x0C) == 0x08:
        return (
            _nes2_size(header[4], header[9] & 0x0F, 16 * 1024),
            _nes2_size(header[5], header[9] >> 4, 8 * 1024),
        )
    return header[4] * 16 * 1024, header[5] * 8 * 1024


def _mapper_number(header: bytes) -> int:
    mapper = (header[6] >> 4) | (header[7] & 0xF0)
    if (header[7] & 0x0C) == 0x08:
        mapper |= (header[8] & 0x0F) << 8
    return mapper


def identify_nes_rom(path: str | Path) -> RomIdentity:
    """Accept only exact known Wario's Woods PRG+CHR fingerprints."""
    rom_path = Path(path).expanduser()
    try:
        data = rom_path.read_bytes()
    except OSError as exc:
        raise RomIdentityError(f"Could not read the selected ROM: {exc}") from exc

    if len(data) < 16 or data[:4] != b"NES\x1a":
        raise RomIdentityError(
            "This file is not a complete iNES/NES 2.0 ROM. Select the original "
            "NES .nes cartridge image, not a SNES ROM, archive, or disc image."
        )

    header = data[:16]
    mapper = _mapper_number(header)
    prg_size, chr_size = _rom_sizes(header)
    trainer_size = 512 if (header[6] & 0x04) else 0
    body = data[16 + trainer_size:]

    if prg_size <= 0 or chr_size <= 0 or len(body) != prg_size + chr_size:
        raise RomIdentityError(
            "The ROM header's PRG/CHR sizes do not match the file. It may be "
            "truncated, modified, or not a supported clean NES dump."
        )

    prg = body[:prg_size]
    chr_rom = body[prg_size:]
    prg_crc = zlib.crc32(prg) & 0xFFFFFFFF
    chr_crc = zlib.crc32(chr_rom) & 0xFFFFFFFF
    body_crc = zlib.crc32(body) & 0xFFFFFFFF
    body_sha1 = hashlib.sha1(body).hexdigest().lower()

    for fingerprint in ROM_FINGERPRINTS:
        if (
            mapper == fingerprint.mapper
            and prg_size == fingerprint.prg_size
            and chr_size == fingerprint.chr_size
            and prg_crc == fingerprint.prg_crc32
            and chr_crc == fingerprint.chr_crc32
            and body_crc == fingerprint.body_crc32
            and body_sha1 == fingerprint.body_sha1
        ):
            return RomIdentity(
                title=fingerprint.title,
                region=fingerprint.region,
                mapper=fingerprint.mapper,
                body_crc32=fingerprint.body_crc32,
                body_sha1=fingerprint.body_sha1,
            )

    supported_mappers = ", ".join(
        str(value) for value in sorted({item.mapper for item in ROM_FINGERPRINTS})
    )
    raise RomIdentityError(
        f"This ROM was not recognized as a verified {GAME_TITLE} NES dump. "
        f"It reports Mapper {mapper}; this project's Wario's Woods fingerprints "
        f"use Mapper(s) {supported_mappers}. The PRG/CHR contents must match "
        "a supported clean regional dump. Unknown games, modified ROMs, and "
        "unlisted revisions are rejected."
    )
