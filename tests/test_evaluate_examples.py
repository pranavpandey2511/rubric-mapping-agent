from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_examples import prediction_path


class EvaluateExamplesTests(unittest.TestCase):
    def test_stage_scoped_prediction_is_preferred_with_legacy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "keysight" / "sections.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("{}\n", encoding="utf-8")

            self.assertEqual(
                prediction_path(root, "keysight", "part1", "sections.json"),
                legacy,
            )

            staged = root / "keysight" / "part1" / "sections.json"
            staged.parent.mkdir(parents=True)
            staged.write_text("{}\n", encoding="utf-8")

            self.assertEqual(
                prediction_path(root, "keysight", "part1", "sections.json"),
                staged,
            )


if __name__ == "__main__":
    unittest.main()
