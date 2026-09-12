import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "shevlogger"


def keys(value, prefix=""):
    return {
        item
        for key, child in value.items()
        for item in (
            keys(child, prefix + key + ".")
            if isinstance(child, dict)
            else [prefix + key]
        )
    }


class TranslationTests(unittest.TestCase):
    def test_all_locales_cover_the_same_editing_and_recovery_fields(self):
        source = json.loads((ROOT / "strings.json").read_text(encoding="utf-8"))
        for language in ("en", "uk"):
            translated = json.loads(
                (ROOT / "translations" / f"{language}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(keys(source), keys(translated))
            for step in ("reconfigure", "reauth_confirm"):
                self.assertEqual(
                    set(translated["config"]["step"][step]["data"]), {"host", "token"}
                )
            for reason in (
                "invalid_auth",
                "missing_bearer",
                "auth_rejected",
                "wrong_device",
            ):
                self.assertTrue(translated["config"]["error"][reason])


if __name__ == "__main__":
    unittest.main()
