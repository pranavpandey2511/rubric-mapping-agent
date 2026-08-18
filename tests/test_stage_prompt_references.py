from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCEL_SKILL = PROJECT_ROOT / "skills" / "excel" / "SKILL.md"
MAPPING_SKILL = PROJECT_ROOT / "skills" / "xlsx-rubric-mapping" / "SKILL.md"
REFERENCES = PROJECT_ROOT / "skills" / "xlsx-rubric-mapping" / "references"


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class StagePromptReferenceTests(unittest.TestCase):
    def test_skills_route_to_each_other_without_prescribing_order(self) -> None:
        excel = EXCEL_SKILL.read_text(encoding="utf-8")
        mapping = MAPPING_SKILL.read_text(encoding="utf-8")

        self.assertIn("also use the available `xlsx-rubric-mapping` skill", excel)
        self.assertIn("When an `excel` skill is available", mapping)
        self.assertIn("before or after this skill", mapping)
        for part in ("part-1", "part-2", "part-3"):
            self.assertIn(f"references/{part}/{part}-workflow.md", mapping)
            self.assertIn(f"references/{part}/output-format.md", mapping)
        self.assertNotIn("PART1_POLICY", mapping)
        self.assertNotIn("PART3_EVIDENCE_POLICY", mapping)

    def test_reference_tree_has_normal_visual_and_output_files_per_part(self) -> None:
        self.assertEqual(
            sorted(path.name for path in REFERENCES.iterdir()),
            ["part-1", "part-2", "part-3"],
        )
        for part in ("part-1", "part-2", "part-3"):
            self.assertEqual(
                sorted(path.name for path in (REFERENCES / part).iterdir()),
                [
                    "output-format.md",
                    f"{part}-workflow-visual.md",
                    f"{part}-workflow.md",
                ],
            )

    def test_part1_defines_section_extraction_and_strict_outputs(self) -> None:
        instructions = _normalized(
            REFERENCES / "part-1" / "part-1-workflow.md"
        )
        output = _normalized(REFERENCES / "part-1" / "output-format.md")

        self.assertIn(
            "An overall section is a complete, coherent worksheet panel",
            instructions,
        )
        self.assertIn(
            "`input.xlsx` is the starting workbook given to a human",
            instructions,
        )
        self.assertIn(
            "use `complete.xlsx` to understand the finished work",
            instructions,
        )
        self.assertIn("Choose the smallest complete panel", instructions)
        self.assertIn("Keep uncertain neighboring panels separate", instructions)
        self.assertIn("one uninterrupted local period or header axis", instructions)
        self.assertIn("A repeated or new local axis is a split boundary", instructions)
        self.assertIn(
            "A subtotal, historical/projected transition, style change",
            instructions,
        )
        self.assertIn("helper table's tight occupied footprint", instructions)
        self.assertIn("do not pad it through surrounding blanks", instructions)
        self.assertIn(
            "Audit every proposed section's top, bottom, left, and right edges",
            instructions,
        )
        self.assertIn("Interior blankness never justifies moving an outer edge", instructions)
        self.assertIn("Optimize for the grouped-pair metric", instructions)
        self.assertIn(
            "Describe a section only after its geometry is final",
            instructions,
        )
        self.assertNotIn("perform a separate hierarchy pass", instructions)
        self.assertNotIn("occupy the same responsibility layer", instructions)
        self.assertNotIn("exact union of separately bounded", instructions)
        self.assertNotIn("sparse decorative or sentinel edge", instructions)
        self.assertNotIn("v5", instructions.lower())
        self.assertNotIn("best measured", instructions.lower())
        self.assertIn("`sections.json`", output)
        self.assertIn("`summary.md`", output)
        self.assertIn("exactly `sections` and", output)

    def test_part2_uses_retrieval_units_and_stable_roles(self) -> None:
        prompt = _normalized(REFERENCES / "part-2" / "part-2-workflow.md")
        output = _normalized(REFERENCES / "part-2" / "output-format.md")

        self.assertIn("rubric-independent semantic", prompt)
        self.assertIn("agent-authored index replaces the Part 2 Markdown summary", prompt)
        self.assertIn("cannot establish a coordinate", prompt)
        self.assertIn("coordinate or override the parent footprint", prompt)
        self.assertIn("Keep copy-across or copy-down formula families together", prompt)
        self.assertIn("Part 1 parent as a bounding region", prompt)
        self.assertIn("period bands as subsection boundaries", prompt)
        self.assertIn("Do not place cells from both bands in one subsection", prompt)
        self.assertIn("Roles must describe the subsection as a whole", prompt)
        self.assertIn("no subsection crosses an explicit historical/actual", prompt)
        self.assertIn("blank separators or whitespace", prompt)
        self.assertIn("Use the fixed role taxonomy", prompt)
        self.assertIn("exactly the five fields shown", output)
        self.assertIn('"generated_by": "part2_agent"', output)
        self.assertNotIn("## `summary.md`", output)

    def test_part3_uses_scoring_aware_prompt_and_strict_output(self) -> None:
        instructions = _normalized(
            REFERENCES / "part-3" / "part-3-workflow.md"
        )
        output = _normalized(REFERENCES / "part-3" / "output-format.md")

        self.assertIn("Select numerical evidence", instructions)
        self.assertIn("positive `numerical_points`", instructions)
        self.assertIn("every eligible changed cell", instructions)
        self.assertIn("A formula dependency is reasoning context", instructions)
        self.assertIn("method-only mappings", instructions)
        self.assertIn("exactly this shape", output)
        self.assertIn("every rubric item ID exactly once", output)

    def test_each_part_has_conditional_stage_specific_visual_guidance(self) -> None:
        normal = {
            part: _normalized(REFERENCES / part / f"{part}-workflow.md")
            for part in ("part-1", "part-2", "part-3")
        }
        visual = {
            part: _normalized(
                REFERENCES / part / f"{part}-workflow-visual.md"
            )
            for part in ("part-1", "part-2", "part-3")
        }

        for part, instructions in visual.items():
            self.assertIn(
                "When `inspect_workbook_view` is attached",
                instructions,
            )
            self.assertNotIn("inspect_workbook_view", normal[part])
        self.assertIn("all four proposed edges", visual["part-1"])
        self.assertIn("semantic grouping", visual["part-2"])
        self.assertIn(
            "cannot determine whether a cell is eligible",
            visual["part-3"],
        )

    def test_each_workflow_follows_sheet_or_workbook_execution_scope(self) -> None:
        for part in ("part-1", "part-2", "part-3"):
            for suffix in ("", "-visual"):
                with self.subTest(part=part, suffix=suffix):
                    instructions = _normalized(
                        REFERENCES / part / f"{part}-workflow{suffix}.md"
                    )
                    self.assertIn("`EXECUTION_SCOPE`", instructions)
                    self.assertIn("In `sheet` scope", instructions)
                    self.assertIn("`TARGET_SHEET`", instructions)
                    self.assertIn("In `workbook` scope", instructions)

    def test_visual_variants_only_add_their_visual_workflow_section(self) -> None:
        boundaries = {
            "part-1": (
                "## Use attached visual inspection for boundary ambiguity",
                "## Choose boundaries",
            ),
            "part-2": (
                "## Use attached visual inspection for semantic grouping ambiguity",
                "## Form coherent retrieval units",
            ),
            "part-3": (
                "## Use attached visual inspection only for structural ambiguity",
                "## Bind every emitted cell to the rubric",
            ),
        }
        for part, (visual_heading, next_heading) in boundaries.items():
            with self.subTest(part=part):
                normal = (
                    REFERENCES / part / f"{part}-workflow.md"
                ).read_text(encoding="utf-8")
                visual = (
                    REFERENCES / part / f"{part}-workflow-visual.md"
                ).read_text(encoding="utf-8")
                start = visual.index(visual_heading)
                end = visual.index(next_heading, start)
                self.assertEqual(visual[:start] + visual[end:], normal)


if __name__ == "__main__":
    unittest.main()
