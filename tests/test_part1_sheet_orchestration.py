from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from rubric_mapping_agent.workflow import create_overall_section


@patch.dict(os.environ, {"RUBRIC_MAP_PART1_SCOPE": "sheet"})
class Part1SheetOrchestrationTests(unittest.TestCase):
    def _workbook(
        self,
        path: Path,
        sheets: list[str],
        *,
        hidden: set[str] | None = None,
    ) -> None:
        workbook = Workbook()
        workbook.active.title = sheets[0]
        for sheet_name in sheets[1:]:
            workbook.create_sheet(sheet_name)
        for sheet_name in hidden or set():
            workbook[sheet_name].sheet_state = "hidden"
        workbook.save(path)
        workbook.close()

    def _sources(
        self,
        root: Path,
        input_sheets: list[str],
        complete_sheets: list[str],
        *,
        hidden: set[str] | None = None,
    ) -> tuple[Path, Path, Path, Path]:
        input_path = root / "input.xlsx"
        complete_path = root / "complete.xlsx"
        instructions_path = root / "instructions.md"
        output_path = root / "sections.json"
        self._workbook(input_path, input_sheets, hidden=hidden)
        self._workbook(complete_path, complete_sheets, hidden=hidden)
        instructions_path.write_text("Build the model.", encoding="utf-8")
        return input_path, complete_path, instructions_path, output_path

    def test_runs_each_sheet_in_complete_order_and_renumbers_ids(self) -> None:
        calls: list[str] = []

        def invoke(stage, sources, *, target_sheet, visual_artifacts_dir=None):
            self.assertEqual(stage, "part1")
            calls.append(target_sheet)
            if target_sheet == "Hidden":
                return {"sections": [], "section_summaries": []}
            address = "A1" if target_sheet == "Alpha" else "B2"
            return {
                "sections": [
                    {
                        "section_id": "section_001",
                        "sheet": target_sheet,
                        "cells": [address],
                    }
                ],
                "section_summaries": [
                    {
                        "section_id": "section_001",
                        "title": f"{target_sheet} Panel",
                        "detail": f"Contains the main {target_sheet} calculation panel.",
                        "plain_language": f"Explains the main {target_sheet} model area.",
                    }
                ],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._sources(
                Path(temp_dir),
                ["Beta", "Alpha", "Hidden"],
                ["Alpha", "Hidden", "Beta"],
                hidden={"Hidden"},
            )
            with patch(
                "rubric_mapping_agent.workflow._invoke_stage",
                side_effect=invoke,
            ):
                artifact = create_overall_section(
                    paths[0], paths[1], paths[2], output_path=paths[3]
                )

            self.assertEqual(
                json.loads(paths[3].read_text(encoding="utf-8")),
                artifact,
            )
            summary = paths[3].with_name("summary.md").read_text(encoding="utf-8")

        self.assertCountEqual(calls, ["Alpha", "Hidden", "Beta"])
        self.assertEqual(
            artifact,
            {
                "sections": [
                    {
                        "section_id": "section_001",
                        "sheet": "Alpha",
                        "cells": ["A1"],
                    },
                    {
                        "section_id": "section_002",
                        "sheet": "Beta",
                        "cells": ["B2"],
                    },
                ]
            },
        )
        self.assertIn("## section_001 — Alpha Panel", summary)
        self.assertIn("## section_002 — Beta Panel", summary)
        self.assertNotIn("Cell ranges", summary)
        self.assertNotIn("**Cells:**", summary)
        self.assertIn("**In normal words:**", summary)
        self.assertLess(summary.index("section_001"), summary.index("section_002"))

    def test_sheet_mismatch_fails_before_agent_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._sources(
                Path(temp_dir),
                ["Alpha"],
                ["Alpha", "Beta"],
            )
            with patch("rubric_mapping_agent.workflow._invoke_stage") as invoke:
                with self.assertRaisesRegex(ValueError, "matching worksheet names"):
                    create_overall_section(
                        paths[0], paths[1], paths[2], output_path=paths[3]
                    )

            invoke.assert_not_called()
            self.assertFalse(paths[3].exists())
            self.assertFalse(paths[3].with_name("summary.md").exists())

    def test_wrong_sheet_output_is_rejected_without_geometry_checks(self) -> None:
        artifact = {
            "sections": [
                {
                    "section_id": "local",
                    "sheet": "Beta",
                    "cells": ["XFD1048576"],
                }
            ],
            "section_summaries": [
                {
                    "section_id": "local",
                    "title": "Wrong Sheet",
                    "detail": "This description belongs to the wrong sheet.",
                    "plain_language": "Explains a panel on another worksheet.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._sources(Path(temp_dir), ["Alpha"], ["Alpha"])
            with patch(
                "rubric_mapping_agent.workflow._invoke_stage",
                return_value=artifact,
            ):
                with self.assertRaisesRegex(ValueError, "another sheet"):
                    create_overall_section(
                        paths[0], paths[1], paths[2], output_path=paths[3]
                    )

            self.assertFalse(paths[3].exists())
            self.assertFalse(paths[3].with_name("summary.md").exists())

    def test_later_sheet_failure_does_not_write_a_partial_artifact(self) -> None:
        def invoke(stage, sources, *, target_sheet, visual_artifacts_dir=None):
            if target_sheet == "Beta":
                raise RuntimeError("second sheet failed")
            return {
                "sections": [
                    {
                        "section_id": "local",
                        "sheet": target_sheet,
                        "cells": ["A1"],
                    }
                ],
                "section_summaries": [
                    {
                        "section_id": "local",
                        "title": f"{target_sheet} Panel",
                        "detail": "Contains the sheet calculation panel.",
                        "plain_language": "Explains the main model area.",
                    }
                ],
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._sources(
                Path(temp_dir),
                ["Alpha", "Beta"],
                ["Alpha", "Beta"],
            )
            with patch(
                "rubric_mapping_agent.workflow._invoke_stage",
                side_effect=invoke,
            ):
                with self.assertRaisesRegex(RuntimeError, "second sheet failed"):
                    create_overall_section(
                        paths[0], paths[1], paths[2], output_path=paths[3]
                    )

            self.assertFalse(paths[3].exists())
            self.assertFalse(paths[3].with_name("summary.md").exists())

    def test_summary_ids_must_match_sections_before_outputs_are_written(self) -> None:
        artifact = {
            "sections": [
                {
                    "section_id": "local",
                    "sheet": "Alpha",
                    "cells": ["A1"],
                }
            ],
            "section_summaries": [
                {
                    "section_id": "different",
                    "title": "Alpha Panel",
                    "detail": "Contains the Alpha calculation panel.",
                    "plain_language": "Explains the main Alpha model area.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._sources(Path(temp_dir), ["Alpha"], ["Alpha"])
            with patch(
                "rubric_mapping_agent.workflow._invoke_stage",
                return_value=artifact,
            ):
                with self.assertRaisesRegex(ValueError, "IDs must match"):
                    create_overall_section(
                        paths[0], paths[1], paths[2], output_path=paths[3]
                    )

            self.assertFalse(paths[3].exists())
            self.assertFalse(paths[3].with_name("summary.md").exists())


if __name__ == "__main__":
    unittest.main()
