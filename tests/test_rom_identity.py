"""ROM identity tests use synthetic bytes; no commercial game data is included."""
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
                return rom_identity.identify_nes_rom(path, fingerprint.game_id)

    def test_known_excitebike_profile_is_accepted(self):
        fingerprint = next(x for x in rom_identity.ROM_FINGERPRINTS if x.game_id == "excitebike")
        identity = self.identify_synthetic_match(fingerprint)
        self.assertEqual(identity.title, "Excitebike")
        self.assertEqual(identity.region, "Japan / USA (NTSC)")

    def test_both_warios_woods_regions_are_accepted(self):
        profiles = [x for x in rom_identity.ROM_FINGERPRINTS if x.game_id == "warioswoods"]
        self.assertEqual({x.region for x in profiles}, {"USA (NTSC)", "Europe (PAL)"})
        for fingerprint in profiles:
            with self.subTest(region=fingerprint.region):
                identity = self.identify_synthetic_match(fingerprint)
                self.assertEqual(identity.title, "Wario's Woods")
                self.assertEqual(identity.region, fingerprint.region)

    def test_a_verified_other_game_is_rejected(self):
        fingerprint = next(x for x in rom_identity.ROM_FINGERPRINTS if x.game_id == "excitebike")
        header = make_header(fingerprint.mapper, fingerprint.prg_size, fingerprint.chr_size)
        synthetic = header + bytes(fingerprint.prg_size + fingerprint.chr_size)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "renamed-warios-woods.nes"
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
                with self.assertRaisesRegex(rom_identity.RomIdentityError, "verified Excitebike.*not Wario's Woods"):
                    rom_identity.identify_nes_rom(path, "warioswoods")

    def test_correct_mapper_and_size_are_not_enough(self):
        fingerprint = next(x for x in rom_identity.ROM_FINGERPRINTS if x.game_id == "warioswoods")
        header = make_header(fingerprint.mapper, fingerprint.prg_size, fingerprint.chr_size)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-warios-woods.nes"
            path.write_bytes(header + bytes(fingerprint.prg_size + fingerprint.chr_size))
            with self.assertRaisesRegex(rom_identity.RomIdentityError, "not recognized"):
                rom_identity.identify_nes_rom(path, "warioswoods")

    def test_invalid_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-file.nes"
            path.write_bytes(b"not an NES ROM")
            with self.assertRaisesRegex(rom_identity.RomIdentityError, "not a complete"):
                rom_identity.identify_nes_rom(path, "excitebike")


if __name__ == "__main__":
    unittest.main()
