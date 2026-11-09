"""Free live smoke tests against https://aigifmaker.ai. No generation runs.

    python tests/smoke_live.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import aigifmaker  # noqa: E402


class LiveSmoke(unittest.TestCase):
    def setUp(self):
        os.environ.pop("AIGIFMAKER_API_KEY", None)

    def test_invalid_key_is_auth_error(self):
        with self.assertRaises(aigifmaker.AuthError):
            aigifmaker.credits(api_key="sk-invalidtest000")

    def test_no_key_hits_wall(self):
        with self.assertRaises(aigifmaker.AuthError):
            aigifmaker.submit("smoke test: a blinking star")


if __name__ == "__main__":
    unittest.main(verbosity=2)
