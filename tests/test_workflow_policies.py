from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rubric_mapping_agent.workflow import (
    _part3_context,
    _sheet_max_workers,
    _stage_scope,
    _stage_prompt,
    run_complete_workflow,
)


class WorkflowPolicyTests(unittest.TestCase):
    def test_full_part3_context_is_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_part3_context(), "part1_part2")

    def test_stage_scope_defaults_preserve_current_behavior(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_stage_scope("part1"), "sheet")
            self.assertEqual(_stage_scope("part2"), "workbook")
            self.assertEqual(_stage_scope("part3"), "workbook")
            self.assertEqual(_sheet_max_workers(), 4)

    def test_each_stage_scope_is_independently_configurable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RUBRIC_MAP_PART1_SCOPE": "workbook",
                "RUBRIC_MAP_PART2_SCOPE": "sheet",
                "RUBRIC_MAP_PART3_SCOPE": "sheet",
                "RUBRIC_MAP_SHEET_MAX_WORKERS": "7",
            },
            clear=True,
        ):
            self.assertEqual(_stage_scope("part1"), "workbook")
            self.assertEqual(_stage_scope("part2"), "sheet")
            self.assertEqual(_stage_scope("part3"), "sheet")
            self.assertEqual(_sheet_max_workers(), 7)

    def test_invalid_scope_and_worker_count_fail_validation(self) -> None:
        with patch.dict(
            os.environ,
            {"RUBRIC_MAP_PART2_SCOPE": "row"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "RUBRIC_MAP_PART2_SCOPE"):
                _stage_scope("part2")
        with patch.dict(
            os.environ,
            {"RUBRIC_MAP_SHEET_MAX_WORKERS": "0"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "positive integer"):
                _sheet_max_workers()

    def test_stage_prompt_has_no_obsolete_policy_selector(self) -> None:
        python_files = {"input": "/mnt/data/input.xlsx"}
        part1 = _stage_prompt("part1", python_files, target_sheet="Model")
        part2 = _stage_prompt("part2", python_files)
        part3 = _stage_prompt("part3", python_files)

        self.assertNotIn("PART1_POLICY", part1)
        self.assertNotIn("PART3_EVIDENCE_POLICY", part3)
        self.assertNotIn("xlsx-rubric-mapping", part1)
        self.assertNotIn("xlsx-rubric-mapping", part3)
        self.assertIn("`sections` and `section_summaries`", part1)
        self.assertNotIn("evaluator", part1.lower())
        self.assertIn("/mnt/data/subsections.json", part2)
        self.assertIn("/mnt/data/subsection_index.json", part2)
        self.assertIn("Author both files\ndirectly", part2)
        self.assertIn("Do not create a combined envelope or a Markdown summary", part2)
        self.assertIn("EXECUTION_SCOPE: sheet", part1)
        self.assertIn("EXECUTION_SCOPE: workbook", part2)
        self.assertIn("EXECUTION_SCOPE: workbook", part3)

    def test_sheet_prompts_define_stage_specific_output_ownership(self) -> None:
        python_files = {"input": "/mnt/data/input.xlsx"}

        part2 = _stage_prompt("part2", python_files, target_sheet="Model")
        part3 = _stage_prompt("part3", python_files, target_sheet="Model")

        self.assertIn('TARGET_SHEET: "Model"', part2)
        self.assertIn("subsections only for Part 1", part2)
        self.assertIn('TARGET_SHEET: "Model"', part3)
        self.assertIn("Include every\nrubric item ID", part3)

    def _run_context(self, context: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "outputs"
            with (
                patch.dict(
                    os.environ,
                    {"RUBRIC_MAP_PART3_CONTEXT": context},
                    clear=True,
                ),
                patch(
                    "rubric_mapping_agent.workflow.create_overall_section"
                ) as part1,
                patch(
                    "rubric_mapping_agent.workflow.create_intermediate_sections"
                ) as part2,
                patch(
                    "rubric_mapping_agent.workflow.create_items_to_cells_mapping"
                ) as part3,
            ):
                outputs = run_complete_workflow(
                    "input.xlsx",
                    "complete.xlsx",
                    "instructions.md",
                    "rubric.json",
                    output_dir=output_dir,
                )
                return (
                    outputs,
                    part1.call_count,
                    part2.call_count,
                    part2.call_args,
                    part3.call_args,
                )

    def test_full_context_runs_and_attaches_part2(self) -> None:
        outputs, part1_calls, part2_calls, part2_call, part3_call = self._run_context(
            "part1_part2"
        )

        self.assertEqual(part1_calls, 1)
        self.assertEqual(part2_calls, 1)
        self.assertIn("section_summary", outputs)
        self.assertEqual(
            part2_call.args[4],
            outputs["section_summary"],
        )
        self.assertIn("subsections", outputs)
        self.assertIn("subsection_index", outputs)
        self.assertEqual(
            part2_call.kwargs["index_output_path"],
            outputs["subsection_index"],
        )
        self.assertIsNotNone(part3_call.kwargs["sections_path"])
        self.assertEqual(
            part3_call.kwargs["section_summary_path"],
            outputs["section_summary"],
        )
        self.assertIsNotNone(part3_call.kwargs["subsections_path"])
        self.assertEqual(
            part3_call.kwargs["subsection_index_path"],
            outputs["subsection_index"],
        )
        self.assertEqual(outputs["sections"].parent.name, "part1")
        self.assertEqual(outputs["subsections"].parent.name, "part2")

    def test_part1_context_skips_part2(self) -> None:
        outputs, _, part2_calls, _, part3_call = self._run_context("part1")

        self.assertEqual(part2_calls, 0)
        self.assertNotIn("subsections", outputs)
        self.assertIsNotNone(part3_call.kwargs["sections_path"])
        self.assertIsNotNone(part3_call.kwargs["section_summary_path"])
        self.assertIsNone(part3_call.kwargs["subsections_path"])
        self.assertIsNone(part3_call.kwargs["subsection_index_path"])

    def test_direct_context_attaches_no_upstream_artifacts(self) -> None:
        outputs, _, part2_calls, _, part3_call = self._run_context("none")

        self.assertEqual(part2_calls, 0)
        self.assertNotIn("subsections", outputs)
        self.assertIsNone(part3_call.kwargs["sections_path"])
        self.assertIsNone(part3_call.kwargs["section_summary_path"])
        self.assertIsNone(part3_call.kwargs["subsections_path"])
        self.assertIsNone(part3_call.kwargs["subsection_index_path"])


if __name__ == "__main__":
    unittest.main()
