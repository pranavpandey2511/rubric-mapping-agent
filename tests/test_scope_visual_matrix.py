from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.run_scope_visual_matrix import (
    MODELS,
    TASKS,
    VARIANTS,
    aggregate_results,
    build_run_specs,
)


class ScopeVisualMatrixTests(unittest.TestCase):
    def test_matrix_order_and_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            specs = build_run_specs(Path(temp_dir))

        self.assertEqual(len(specs), len(VARIANTS) * len(MODELS) * len(TASKS))
        self.assertEqual(
            [(spec.variant_id, spec.model_label, spec.task) for spec in specs[:3]],
            [
                (VARIANTS[0].variant_id, "sol", "keysight"),
                (VARIANTS[0].variant_id, "sol", "textron-1"),
                (VARIANTS[0].variant_id, "sol", "topbuild"),
            ],
        )
        self.assertTrue(all(spec.model == "openai:gpt-5.6-sol" for spec in specs))
        self.assertTrue(all(spec.environment["RUBRIC_MAP_VISUAL_BACKEND"] == "off" for spec in specs[:9]))
        self.assertTrue(all(spec.environment["RUBRIC_MAP_VISUAL_BACKEND"] == "libreoffice_pdf" for spec in specs[9:]))
        self.assertTrue(all(spec.environment["RUBRIC_MAP_SHEET_MAX_WORKERS"] == "1" for spec in specs))
        self.assertTrue(all(spec.environment["RUBRIC_MAP_PART3_CONTEXT"] == "part1_part2" for spec in specs))

    def test_empty_aggregates_preserve_all_groups(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            specs = build_run_specs(Path(temp_dir))

        aggregates = aggregate_results(specs, {})

        self.assertEqual(len(aggregates), len(VARIANTS) * len(MODELS))
        self.assertTrue(all(row["completed_tasks"] == 0 for row in aggregates))
        self.assertTrue(all(row["invalid_output_rate"] == 1.0 for row in aggregates))
        self.assertTrue(all(row["part3_micro"]["f1"] is None for row in aggregates))


if __name__ == "__main__":
    unittest.main()
