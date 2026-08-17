from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rubric_mapping_eval.batch import evaluate_batch_manifest


class BatchTests(unittest.TestCase):
    def test_relative_manifest_paths_and_macro_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write(name: str, payload: dict) -> None:
                (root / name).write_text(json.dumps(payload), encoding="utf-8")

            write(
                "sections.json",
                {
                    "sections": [
                        {"section_id": "one", "sheet": "M", "cells": ["A1", "A2"]}
                    ]
                },
            )
            write(
                "rubric.json",
                {
                    "criteria": {
                        "criterion_1": {
                            "criterion_id": 1,
                            "grading": [{"item_id": "1.1"}],
                        }
                    }
                },
            )
            write(
                "items.json",
                {
                    "items": [
                        {
                            "item_id": "1.1",
                            "cells": [{"sheet": "M", "address": "A1"}],
                        }
                    ]
                },
            )
            write(
                "manifest.json",
                {
                    "tasks": [
                        {
                            "task_id": "task",
                            "sectioning": {
                                "predicted": "sections.json",
                                "gold": "sections.json",
                            },
                            "i2c_mapping": {
                                "predicted": "items.json",
                                "gold": "items.json",
                                "rubric": "rubric.json",
                            },
                        }
                    ]
                },
            )

            result = evaluate_batch_manifest(root / "manifest.json")

            self.assertEqual(result["summary"]["sectioning"]["macro_average"]["f1"], 1.0)
            self.assertEqual(
                result["summary"]["i2c_mapping"]["criterion_macro_average"]["f1"],
                1.0,
            )
            self.assertIn("task", result["tasks"])


if __name__ == "__main__":
    unittest.main()
