from __future__ import annotations

import unittest
from pathlib import Path

from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import _list_skills

from rubric_mapping_agent.runtime.skills import create_stage_skill_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PROJECT_ROOT / "skills"
STAGE_DIRS = {
    "part1": "part-1",
    "part2": "part-2",
    "part3": "part-3",
}


class StageSkillBundleTests(unittest.TestCase):
    def test_nonvisual_bundle_exposes_only_selected_normal_instructions(self) -> None:
        for stage, reference_dir in STAGE_DIRS.items():
            with self.subTest(stage=stage):
                bundle = create_stage_skill_bundle(stage, visual_enabled=False)
                root = bundle.root
                try:
                    names = {
                        skill["name"]
                        for skill in _list_skills(
                            FilesystemBackend(root_dir=root, virtual_mode=True),
                            "/",
                        )
                    }
                    self.assertEqual(names, {"excel", "xlsx-rubric-mapping"})
                    visible_reference = (
                        root
                        / "xlsx-rubric-mapping"
                        / "references"
                        / reference_dir
                    )
                    self.assertEqual(
                        sorted(path.name for path in visible_reference.iterdir()),
                        ["output-format.md", f"{reference_dir}-workflow.md"],
                    )
                    self.assertEqual(
                        (
                            visible_reference / f"{reference_dir}-workflow.md"
                        ).read_text(
                            encoding="utf-8"
                        ),
                        (
                            SKILLS_ROOT
                            / "xlsx-rubric-mapping"
                            / "references"
                            / reference_dir
                            / f"{reference_dir}-workflow.md"
                        ).read_text(encoding="utf-8"),
                    )
                    self.assertNotIn(
                        "inspect_workbook_view",
                        (
                            visible_reference / f"{reference_dir}-workflow.md"
                        ).read_text(encoding="utf-8"),
                    )
                    self.assertEqual(
                        sorted(
                            path.name
                            for path in visible_reference.parent.iterdir()
                        ),
                        [reference_dir],
                    )
                finally:
                    bundle.close()
                self.assertFalse(root.exists())

    def test_visual_bundle_exposes_visual_variant_as_canonical_instructions(self) -> None:
        for stage, reference_dir in STAGE_DIRS.items():
            with self.subTest(stage=stage):
                bundle = create_stage_skill_bundle(stage, visual_enabled=True)
                root = bundle.root
                try:
                    visible_reference = (
                        root
                        / "xlsx-rubric-mapping"
                        / "references"
                        / reference_dir
                    )
                    self.assertEqual(
                        sorted(path.name for path in visible_reference.iterdir()),
                        ["output-format.md", f"{reference_dir}-workflow.md"],
                    )
                    visible = (
                        visible_reference / f"{reference_dir}-workflow.md"
                    ).read_text(encoding="utf-8")
                    expected = (
                        SKILLS_ROOT
                        / "xlsx-rubric-mapping"
                        / "references"
                        / reference_dir
                        / f"{reference_dir}-workflow-visual.md"
                    ).read_text(encoding="utf-8")
                    self.assertEqual(visible, expected)
                    self.assertIn("inspect_workbook_view", visible)
                    self.assertFalse(
                        (
                            visible_reference
                            / f"{reference_dir}-workflow-visual.md"
                        ).exists()
                    )
                finally:
                    bundle.close()
                self.assertFalse(root.exists())

    def test_unknown_stage_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown stage"):
            create_stage_skill_bundle("part4", visual_enabled=False)


if __name__ == "__main__":
    unittest.main()
