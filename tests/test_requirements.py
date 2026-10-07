from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RequirementsTests(unittest.TestCase):
    def test_xgboost_pin_is_valid_for_supported_python(self) -> None:
        requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
        xgboost_line = next(
            line.strip() for line in requirements.splitlines() if line.strip().startswith("xgboost")
        )
        self.assertEqual(xgboost_line, "xgboost==3.2.0")


if __name__ == "__main__":
    unittest.main()
