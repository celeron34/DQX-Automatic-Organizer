import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from support_utils import getCompatibleConfigValue, getRecruitingMessageDirectory


class RecruitingNameCompatibilityTests(unittest.TestCase):
    def test_canonical_config_key_has_precedence(self):
        config = {"recruiting": 1, "recluting": 2}
        self.assertEqual(getCompatibleConfigValue(config, "recruiting", "recluting"), 1)

    def test_legacy_config_key_is_a_fallback(self):
        self.assertEqual(getCompatibleConfigValue({"recluting": 2}, "recruiting", "recluting"), 2)

    def test_liteparty_key_is_canonical_with_legacy_fallback(self):
        self.assertEqual(getCompatibleConfigValue({"liteparty": 1, "lightparty": 2}, "liteparty", "lightparty"), 1)
        self.assertEqual(getCompatibleConfigValue({"lightparty": 2}, "liteparty", "lightparty"), 2)

    def test_prefers_corrected_directory_name(self):
        with TemporaryDirectory() as root:
            guild_dir = Path(root) / "123"
            (guild_dir / "recluitingMessage").mkdir(parents=True)
            (guild_dir / "recruitingMessage").mkdir()
            self.assertEqual(
                getRecruitingMessageDirectory(123, root),
                str(guild_dir / "recruitingMessage"),
            )

    def test_reads_legacy_directory_when_corrected_one_is_absent(self):
        with TemporaryDirectory() as root:
            legacy = Path(root) / "123" / "recluitingMessage"
            legacy.mkdir(parents=True)
            self.assertEqual(getRecruitingMessageDirectory(123, root), str(legacy))


if __name__ == "__main__":
    unittest.main()
