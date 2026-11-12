"""Tests for this project's own ROM fingerprint allowlist; no commercial ROMs included."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

import rom_identity


def make_header(mapper: int, prg_size: int, chr_size: int) -> bytes:
    header = bytearray(16)
    header[:4] = b"NES\x1a"
    header[4] = prg_size // (16 * 1024)
    header[5] = chr_size // (8 * 1024)
    header[6] = (mapper & 0x0F) << 4
    header[7] = mapper & 0xF0
    return bytes(header)


class RomIdentityTests(unittest.TestCase):
    def identify_synthetic_match(self, fingerprint: rom_identity.RomFingerprint):
        header = make_header(fingerprint.mapper, fingerprint.prg_size, fingerprint.chr_size)
        synthetic = header + bytes(fingerprint.prg_size + fingerprint.chr_size)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.nes"
            path.write_bytes(synthetic)
            with (
                mock.patch(
                    "rom_identity.zlib.crc32",
                    side_effect=[
                        fingerprint.prg_crc32,
                        fingerprint.chr_crc32,
                        fingerprint.body_crc32,
                    ],
                ),
                mock.patch("rom_identity.hashlib.sha1") as sha1,
            ):
                sha1.return_value.hexdigest.return_value = fingerprint.body_sha1
                return rom_identity.identify_nes_rom(path)

    def test_only_this_games_fingerprints_are_catalogued(self):
        self.assertEqual(len(rom_identity.ROM_FINGERPRINTS), 2)
        self.assertTrue(all(item.title == rom_identity.GAME_TITLE for item in rom_identity.ROM_FINGERPRINTS))
        self.assertEqual(rom_identity.GAME_TITLE, "Wario's Woods")

    def test_known_regional_images_are_accepted(self):
        for fingerprint in rom_identity.ROM_FINGERPRINTS:
            with self.subTest(region=fingerprint.region):
                identity = self.identify_synthetic_match(fingerprint)
                self.assertEqual(identity.title, rom_identity.GAME_TITLE)
                self.assertEqual(identity.region, fingerprint.region)
                self.assertEqual(identity.mapper, fingerprint.mapper)

    def test_same_mapper_and_sizes_without_matching_contents_are_rejected(self):
        fingerprint = rom_identity.ROM_FINGERPRINTS[0]
        header = make_header(fingerprint.mapper, fingerprint.prg_size, fingerprint.chr_size)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "renamed-game.nes"
            path.write_bytes(header + bytes(fingerprint.prg_size + fingerprint.chr_size))
            with self.assertRaisesRegex(rom_identity.RomIdentityError, "not recognized as a verified"):
                rom_identity.identify_nes_rom(path)

    def test_wrong_mapper_is_rejected(self):
        fingerprint = rom_identity.ROM_FINGERPRINTS[0]
        wrong_mapper = (fingerprint.mapper + 1) % 15
        header = make_header(wrong_mapper, fingerprint.prg_size, fingerprint.chr_size)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-mapper.nes"
            path.write_bytes(header + bytes(fingerprint.prg_size + fingerprint.chr_size))
            with self.assertRaisesRegex(rom_identity.RomIdentityError, "not recognized as a verified"):
                rom_identity.identify_nes_rom(path)

    def test_invalid_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-file.nes"
            path.write_bytes(b"not an NES ROM")
            with self.assertRaisesRegex(rom_identity.RomIdentityError, "not a complete"):
                rom_identity.identify_nes_rom(path)


if __name__ == "__main__":
    unittest.main()
