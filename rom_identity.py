"""Exact NES ROM identification using verified, headerless PRG+CHR fingerprints.

The hashes cover the cartridge PRG ROM followed by CHR ROM (not the iNES header).
Known-dump references:
- Excitebike: NES Directory / Decomp Games.
- Wario's Woods: NES Directory, NesCartDB and VGPreise.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import zlib


@dataclass(frozen=True)
class RomFingerprint:
    game_id: str
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
    game_id: str
    title: str
    region: str
    mapper: int
    body_crc32: int
    body_sha1: str


class RomIdentityError(ValueError):
    """Raised when a selected file is not a verified dump for this launcher."""


# CRCs and SHA-1s are over the headerless PRG+CHR bytes in cartridge order.
# Excitebike (Japan/USA) has one known retail program/graphics image.
# Wario's Woods has separate North American and European retail images.
ROM_FINGERPRINTS: tuple[RomFingerprint, ...] = (
    RomFingerprint(
        "excitebike", "Excitebike", "Japan / USA (NTSC)", 0,
        16 * 1024, 8 * 1024,
        0x3A94FA0B, 0xE5F72401, 0x49AEB3A6,
        "ba8d9227a0d02b62ee6cb9e691fa5a5134c303a8",
    ),
    RomFingerprint(
        "warioswoods", "Wario's Woods", "USA (NTSC)", 4,
        256 * 1024, 256 * 1024,
        0x1AFB26D7, 0xEB133A6D, 0xF79A75D7,
        "602f640b3fe0ca47cf47de6688779419a75487ac",
    ),
    RomFingerprint(
        "warioswoods", "Wario's Woods", "Europe (PAL)", 4,
        256 * 1024, 256 * 1024,
        0xB24F0357, 0x0146D148, 0x668D1715,
        "1cec3b2e93e81f0353be25ad139addae881dc69a",
    ),
)

GAME_TITLES = {
    "excitebike": "Excitebike",
    "warioswoods": "Wario's Woods",
}


def _nes2_size(lsb: int, msb_nibble: int, unit: int) -> int:
    """Decode an NES 2.0 ROM size field."""
    if msb_nibble == 0x0F:
        exponent = lsb >> 2
        multiplier = lsb & 0x03
        return (1 << exponent) * (2 * multiplier + 1)
    return ((msb_nibble << 8) | lsb) * unit


def _rom_sizes(header: bytes) -> tuple[int, int]:
    is_nes2 = (header[7] & 0x0C) == 0x08
    if is_nes2:
        return (
            _nes2_size(header[4], header[9] & 0x0F, 16 * 1024),
            _nes2_size(header[5], header[9] >> 4, 8 * 1024),
        )
    return header[4] * 16 * 1024, header[5] * 8 * 1024


def _mapper_number(header: bytes) -> int:
    mapper = (header[6] >> 4) | (header[7] & 0xF0)
    if (header[7] & 0x0C) == 0x08:  # NES 2.0
        mapper |= (header[8] & 0x0F) << 8
    return mapper


def identify_nes_rom(path: str | Path, expected_game: str) -> RomIdentity:
    """Identify a supported game by its exact PRG+CHR contents, not filename.

    The selected ROM must have a valid iNES/NES 2.0 header, a supported mapper,
    exact declared PRG/CHR lengths, and matching PRG, CHR, combined CRC-32 and
    combined SHA-1 fingerprints.
    """
    if expected_game not in GAME_TITLES:
        raise ValueError(f"Unknown game profile: {expected_game}")

    rom_path = Path(path).expanduser()
    try:
        data = rom_path.read_bytes()
    except OSError as exc:
        raise RomIdentityError(f"Could not read the selected ROM: {exc}") from exc

    if len(data) < 16 or data[:4] != b"NES\x1a":
        raise RomIdentityError(
            "This file is not a complete iNES/NES 2.0 ROM. Select the NES game's "
            "original .nes cartridge image, not a SNES ROM, archive, or disc image."
        )

    header = data[:16]
    mapper = _mapper_number(header)
    prg_size, chr_size = _rom_sizes(header)
    trainer_size = 512 if (header[6] & 0x04) else 0
    body_start = 16 + trainer_size
    body = data[body_start:]

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

    matched = None
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
            matched = fingerprint
            break

    if matched is None:
        expected_title = GAME_TITLES[expected_game]
        expected_mappers = sorted({
            item.mapper for item in ROM_FINGERPRINTS if item.game_id == expected_game
        })
        mapper_text = ", ".join(str(value) for value in expected_mappers)
        raise RomIdentityError(
            f"This ROM was not recognized as a verified {expected_title} NES dump. "
            f"The file reports Mapper {mapper}, but mapper and filename alone do "
            f"not prove the game's identity. The supported {expected_title} image "
            f"uses Mapper {mapper_text}. Choose an unmodified supported regional ROM."
        )

    if matched.game_id != expected_game:
        expected_title = GAME_TITLES[expected_game]
        raise RomIdentityError(
            f"This file is a verified {matched.title} ROM ({matched.region}), "
            f"not {expected_title}. Select the correct game's NES ROM."
        )

    return RomIdentity(
        game_id=matched.game_id,
        title=matched.title,
        region=matched.region,
        mapper=matched.mapper,
        body_crc32=matched.body_crc32,
        body_sha1=matched.body_sha1,
    )
