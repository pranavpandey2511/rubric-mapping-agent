from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from rubric_mapping_agent.workflow import create_intermediate_sections


class Part2IndexHandoffTests(unittest.TestCase):
    def _files(self, root: Path) -> tuple[Path, ...]:
        input_path = root / "input.xlsx"
        complete_path = root / "complete.xlsx"
        for path, value in ((input_path, None), (complete_path, 10)):
            workbook = Workbook()
            workbook.active.title = "Model"
            workbook.active["A1"] = value
            workbook.save(path)
            workbook.close()
        instructions = root / "instructions.md"
        instructions.write_text("Build the model.", encoding="utf-8")
        sections = root / "sections.json"
        sections.write_text(
            json.dumps(
                {
                    "sections": [
                        {
                            "section_id": "section_001",
                            "sheet": "Model",
                            "cells": ["A1"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        summary = root / "part1" / "summary.md"
        summary.parent.mkdir(parents=True)
        summary.write_text(
            "# Part 1 Section Summary\n\n"
            "## section_001 — Model Output\n\n"
            "**Detail:** Contains the primary model output.\n\n"
            "**In normal words:** Shows the main model result.\n\n"
            "**Worksheet:** `Model`\n",
            encoding="utf-8",
        )
        output = root / "part2" / "subsections.json"
        index = root / "part2" / "subsection_index.json"
        return input_path, complete_path, instructions, sections, summary, output, index

    def _artifact(self) -> dict:
        return {
            "subsections": [
                {
                    "subsection_id": "subsection_s001_001",
                    "parent_section_id": "section_001",
                    "sheet": "Model",
                    "cells": ["A1"],
                    "roles": ["output"],
                }
            ],
            "subsection_index": {
                "schema_version": 2,
                "generated_by": "part2_agent",
                "families": [
                    {
                        "family_id": "subsection_s001_001_family_01",
                        "subsection_id": "subsection_s001_001",
                        "parent_section_id": "section_001",
                        "sheet": "Model",
                        "object_name": "Primary Model Output",
                        "aliases": [],
                        "changed_cells": ["A1"],
                        "anchor_cells": [],
                        "roles": ["output"],
                        "scope": {
                            "period_type": "unspecified",
                            "period_headers": [],
                        },
                        "orientation": "row",
                        "calculation_kind": "output",
                        "formula_signatures": [],
                    }
                ],
                "relationships": [],
            },
        }

    def test_part2_preserves_agent_authored_index_without_markdown(self) -> None:
        artifact = self._artifact()
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._files(Path(temp_dir))
            with patch.dict("os.environ", {}, clear=True), patch(
                "rubric_mapping_agent.workflow._invoke_stage",
                return_value=artifact,
            ) as invoke:
                result = create_intermediate_sections(
                    *paths[:5],
                    output_path=paths[5],
                    index_output_path=paths[6],
                )

            self.assertEqual(result, {"subsections": artifact["subsections"]})
            self.assertEqual(invoke.call_args.args[0], "part2")
            self.assertEqual(
                invoke.call_args.args[1]["section_summary"], paths[4].resolve()
            )
            self.assertEqual(
                json.loads(paths[6].read_text(encoding="utf-8")),
                artifact["subsection_index"],
            )
            self.assertFalse((paths[5].parent / "summary.md").exists())

    def test_part2_input_handoff_can_send_only_json_or_part1_summary(self) -> None:
        for environment, expected_key, absent_key in (
            (
                {"RUBRIC_MAP_HANDOFF_JSON": "true", "RUBRIC_MAP_HANDOFF_SUMMARY": "false"},
                "sections",
                "section_summary",
            ),
            (
                {"RUBRIC_MAP_HANDOFF_JSON": "false", "RUBRIC_MAP_HANDOFF_SUMMARY": "true"},
                "section_summary",
                "sections",
            ),
        ):
            with self.subTest(environment=environment), tempfile.TemporaryDirectory() as temp_dir:
                paths = self._files(Path(temp_dir))
                with patch.dict("os.environ", environment, clear=True), patch(
                    "rubric_mapping_agent.workflow._invoke_stage",
                    return_value=self._artifact(),
                ) as invoke:
                    create_intermediate_sections(
                        *paths[:5],
                        output_path=paths[5],
                        index_output_path=paths[6],
                    )
                sources = invoke.call_args.args[1]
                self.assertIn(expected_key, sources)
                self.assertNotIn(absent_key, sources)

    def test_part2_rejects_handoff_with_both_channels_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._files(Path(temp_dir))
            with patch.dict(
                "os.environ",
                {
                    "RUBRIC_MAP_HANDOFF_JSON": "false",
                    "RUBRIC_MAP_HANDOFF_SUMMARY": "false",
                },
                clear=True,
            ), patch("rubric_mapping_agent.workflow._invoke_stage") as invoke:
                with self.assertRaisesRegex(ValueError, "at least one Part 1 handoff"):
                    create_intermediate_sections(
                        *paths[:5],
                        output_path=paths[5],
                        index_output_path=paths[6],
                    )
            invoke.assert_not_called()

    def test_part2_rejects_mismatched_part1_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = self._files(Path(temp_dir))
            paths[4].write_text(
                "# Part 1 Section Summary\n\n"
                "## section_999 — Wrong Section\n\n"
                "**Detail:** This does not match sections.json.\n\n"
                "**In normal words:** This points to the wrong model area.\n\n"
                "**Worksheet:** `Model`\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {}, clear=True), patch(
                "rubric_mapping_agent.workflow._invoke_stage"
            ) as invoke:
                with self.assertRaisesRegex(ValueError, "IDs must match"):
                    create_intermediate_sections(
                        *paths[:5],
                        output_path=paths[5],
                        index_output_path=paths[6],
                    )
            invoke.assert_not_called()


if __name__ == "__main__":
    unittest.main()
