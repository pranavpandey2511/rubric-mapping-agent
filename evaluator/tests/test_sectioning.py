from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rubric_mapping_eval.common import EvaluationError
from rubric_mapping_eval.sectioning import (
    build_grouped_pairs,
    evaluate_section_files,
    evaluate_sections,
    parse_sections,
)


class SectioningTests(unittest.TestCase):
    def test_build_grouped_pairs_includes_self_pairs(self) -> None:
        sections = parse_sections(
            {
                "sections": [
                    {
                        "section_id": "one",
                        "sheet": "Model",
                        "cells": ["A1", "A2", "A3"],
                    }
                ]
            }
        )

        pairs = build_grouped_pairs(sections)

        self.assertEqual(len(pairs), 6)
        rendered = {
            ((left.sheet, left.address), (right.sheet, right.address))
            for left, right in pairs
        }
        self.assertIn((("Model", "A1"), ("Model", "A1")), rendered)
        self.assertIn((("Model", "A1"), ("Model", "A3")), rendered)

    def test_evaluate_sections_matches_documented_example(self) -> None:
        gold = parse_sections(
            {
                "sections": [
                    {
                        "section_id": "gold",
                        "sheet": "Model",
                        "cells": ["A1", "A2", "A3"],
                    }
                ]
            }
        )
        predicted = parse_sections(
            {
                "sections": [
                    {
                        "section_id": "predicted",
                        "sheet": "Model",
                        "cells": ["A1", "A2"],
                    }
                ]
            }
        )

        result = evaluate_sections(predicted, gold)
        metrics = result["metrics"]

        self.assertEqual(result["evaluation"], "sectioning")
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertAlmostEqual(metrics["f1"], 2 / 3)
        self.assertEqual(metrics["counts"]["true_positive"], 3)
        self.assertEqual(metrics["counts"]["false_negative"], 3)

    def test_overlapping_sections_do_not_duplicate_pairs(self) -> None:
        sections = parse_sections(
            {
                "sections": [
                    {"section_id": "one", "sheet": "M", "cells": ["A1", "A2"]},
                    {"section_id": "two", "sheet": "M", "cells": ["A1", "A2"]},
                ]
            }
        )
        self.assertEqual(len(build_grouped_pairs(sections)), 3)

    def test_empty_predicted_sections_score_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            predicted_path = root / "predicted.json"
            gold_path = root / "gold.json"
            predicted_path.write_text(json.dumps({"sections": []}), encoding="utf-8")
            gold_path.write_text(
                json.dumps(
                    {
                        "sections": [
                            {
                                "section_id": "gold",
                                "sheet": "Model",
                                "cells": ["A1"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = evaluate_section_files(predicted_path, gold_path)

        self.assertEqual(result["metrics"]["precision"], 0.0)
        self.assertEqual(result["metrics"]["recall"], 0.0)
        self.assertEqual(result["metrics"]["f1"], 0.0)
        self.assertEqual(result["metrics"]["counts"]["predicted"], 0)
        self.assertEqual(result["metrics"]["counts"]["gold"], 1)

    def test_empty_gold_sections_remain_invalid(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "at least one section"):
            parse_sections({"sections": []}, context="gold")

    def test_rejects_noncanonical_address(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "canonical uppercase A1"):
            parse_sections(
                {
                    "sections": [
                        {"section_id": "one", "sheet": "M", "cells": ["a1"]}
                    ]
                }
            )

    def test_rejects_duplicate_cell_within_section(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "duplicate address"):
            parse_sections(
                {
                    "sections": [
                        {
                            "section_id": "one",
                            "sheet": "M",
                            "cells": ["A1", "A1"],
                        }
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
