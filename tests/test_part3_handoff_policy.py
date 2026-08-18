from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rubric_mapping_agent.workflow import create_items_to_cells_mapping


class Part3HandoffPolicyTests(unittest.TestCase):
    def _files(self, root: Path) -> dict[str, Path]:
        paths = {
            "input": root / "input.xlsx",
            "complete": root / "complete.xlsx",
            "instructions": root / "instructions.md",
            "rubric": root / "rubric.json",
            "sections": root / "part1" / "sections.json",
            "section_summary": root / "part1" / "summary.md",
            "subsections": root / "part2" / "subsections.json",
            "subsection_index": root / "part2" / "subsection_index.json",
            "output": root / "part3" / "items_to_cells.json",
        }
        for name, path in paths.items():
            if name == "output":
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == "sections":
                content = '{"sections": []}\n'
            elif name == "subsections":
                content = '{"subsections": []}\n'
            else:
                content = "{}\n"
            path.write_text(content, encoding="utf-8")
        return paths

    def test_flags_filter_only_the_agent_sources(self) -> None:
        cases = (
            (
                {"RUBRIC_MAP_HANDOFF_JSON": "true", "RUBRIC_MAP_HANDOFF_SUMMARY": "true"},
                {
                    "sections",
                    "section_summary",
                    "subsections",
                    "subsection_index",
                },
            ),
            (
                {"RUBRIC_MAP_HANDOFF_JSON": "true", "RUBRIC_MAP_HANDOFF_SUMMARY": "false"},
                {"sections", "subsections", "subsection_index"},
            ),
            (
                {"RUBRIC_MAP_HANDOFF_JSON": "false", "RUBRIC_MAP_HANDOFF_SUMMARY": "true"},
                {"section_summary"},
            ),
            (
                {"RUBRIC_MAP_HANDOFF_JSON": "false", "RUBRIC_MAP_HANDOFF_SUMMARY": "false"},
                set(),
            ),
        )
        for environment, expected_handoff in cases:
            with self.subTest(environment=environment), tempfile.TemporaryDirectory() as temp_dir:
                paths = self._files(Path(temp_dir))
                captured: dict[str, Path] = {}

                def invoke(
                    stage: str,
                    sources: dict[str, Path],
                    *,
                    visual_artifacts_dir: Path | None = None,
                ):
                    self.assertEqual(stage, "part3")
                    self.assertEqual(
                        visual_artifacts_dir,
                        paths["output"].resolve().parent / "visual-inspection",
                    )
                    captured.update(sources)
                    return {"items": {"item_1": []}}

                with (
                    patch.dict("os.environ", environment, clear=True),
                    patch(
                        "rubric_mapping_agent.workflow.parse_rubric",
                        return_value=[SimpleNamespace(item_ids=("item_1",))],
                    ),
                    patch("rubric_mapping_agent.workflow.parse_sections"),
                    patch("rubric_mapping_agent.workflow._validate_subsections"),
                    patch("rubric_mapping_agent.workflow.validate_section_summary"),
                    patch(
                        "rubric_mapping_agent.stage_outputs.parse_item_mapping",
                        return_value={"item_1": frozenset()},
                    ),
                    patch(
                        "rubric_mapping_agent.workflow._eligible_diff_cells",
                        return_value=set(),
                    ),
                    patch(
                        "rubric_mapping_agent.workflow._invoke_stage",
                        side_effect=invoke,
                    ),
                ):
                    create_items_to_cells_mapping(
                        paths["input"],
                        paths["complete"],
                        paths["instructions"],
                        paths["rubric"],
                        sections_path=paths["sections"],
                        section_summary_path=paths["section_summary"],
                        subsections_path=paths["subsections"],
                        subsection_index_path=paths["subsection_index"],
                        output_path=paths["output"],
                    )

                always_present = {"input", "complete", "instructions", "rubric"}
                self.assertEqual(set(captured), always_present | expected_handoff)
                self.assertTrue(paths["output"].is_file())


if __name__ == "__main__":
    unittest.main()
