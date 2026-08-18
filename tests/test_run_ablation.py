from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts import run_ablation


class RunAblationTests(unittest.TestCase):
    def _inputs(self, root: Path) -> dict[str, dict[str, Path]]:
        sources = {}
        upstream = {}
        for name in run_ablation.SOURCE_PATHS:
            path = root / "sources" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"source {name}\n", encoding="utf-8")
            sources[name] = path
        for name in run_ablation.UPSTREAM_PATHS:
            path = root / "upstream" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"upstream {name}\n", encoding="utf-8")
            upstream[name] = path
        return {"sources": sources, "upstream": upstream}

    def _checkout(self, root: Path) -> tuple[Path, Path]:
        project = root / "project"
        task_dir = project / "examples" / "item-to-cell-mapping" / "keysight"
        upstream_root = root / "frozen"
        for name, relative in run_ablation.SOURCE_PATHS.items():
            path = task_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"source {name}\n", encoding="utf-8")
        for name, relative in run_ablation.UPSTREAM_PATHS.items():
            path = upstream_root / "keysight" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"upstream {name}\n", encoding="utf-8")
        return project, upstream_root

    def test_commands_run_only_part3_with_selected_frozen_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            inputs = self._inputs(Path(temp_dir))
            output = Path(temp_dir) / "items_to_cells.json"

            direct = run_ablation.task_command(inputs, output, "none")
            part1 = run_ablation.task_command(inputs, output, "part1")
            full = run_ablation.task_command(inputs, output, "part1_part2")

        self.assertIn("part3", direct)
        self.assertNotIn("all", direct)
        self.assertNotIn("--sections", direct)
        self.assertIn("--sections", part1)
        self.assertIn("--section-summary", part1)
        self.assertNotIn("--subsections", part1)
        self.assertIn("--subsections", full)
        self.assertIn("--subsection-index", full)

    def test_matching_run_requires_all_input_and_output_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inputs = {"keysight": self._inputs(root)}
            configuration = {"environment": {"OPENAI_MODEL": "test"}}
            spec = run_ablation.run_spec(
                "recommended", ("keysight",), configuration, inputs
            )
            variant_root = root / "runs"
            run_dir = variant_root / "run-1"
            output = run_dir / "keysight" / "part3" / "items_to_cells.json"
            output.parent.mkdir(parents=True)
            output.write_text("{}\n", encoding="utf-8")
            manifest = {
                **spec,
                "outputs": {
                    "keysight": {
                        "path": str(output.relative_to(run_dir)),
                        "sha256": run_ablation._sha256_file(output),
                    }
                },
            }
            (run_dir / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )

            self.assertEqual(run_ablation.matching_run(variant_root, spec), run_dir)

            inputs["keysight"]["sources"]["input"].write_text(
                "changed source\n", encoding="utf-8"
            )
            changed_source = run_ablation.run_spec(
                "recommended", ("keysight",), configuration, inputs
            )
            self.assertIsNone(
                run_ablation.matching_run(variant_root, changed_source)
            )
            inputs["keysight"]["sources"]["input"].write_text(
                "source input\n", encoding="utf-8"
            )

            inputs["keysight"]["upstream"]["sections"].write_text(
                "changed upstream\n", encoding="utf-8"
            )
            changed_upstream = run_ablation.run_spec(
                "recommended", ("keysight",), configuration, inputs
            )
            self.assertIsNone(
                run_ablation.matching_run(variant_root, changed_upstream)
            )
            inputs["keysight"]["upstream"]["sections"].write_text(
                "upstream sections\n", encoding="utf-8"
            )

            changed_config = run_ablation.run_spec(
                "recommended",
                ("keysight",),
                {"environment": {"OPENAI_MODEL": "other"}},
                inputs,
            )
            self.assertIsNone(
                run_ablation.matching_run(variant_root, changed_config)
            )

            output.write_text('{"changed": true}\n', encoding="utf-8")
            self.assertIsNone(run_ablation.matching_run(variant_root, spec))

    def test_reuse_does_not_rewrite_completed_run_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, upstream_root = self._checkout(root)
            output_root = root / "ablations"
            args = argparse.Namespace(
                variant="recommended",
                upstream_root=upstream_root,
                tasks=["keysight"],
                output_root=output_root,
                force=False,
                dry_run=False,
            )
            configuration = {
                "environment": {
                    "RUBRIC_MAP_PART3_CONTEXT": "part1_part2",
                },
                "implementation_sha256": "implementation",
            }

            def write_output(command: list[str], **_: object) -> None:
                output = Path(command[command.index("--output") + 1])
                output.write_text("{}\n", encoding="utf-8")

            with patch.object(run_ablation, "PROJECT_ROOT", project), patch.object(
                run_ablation, "parse_args", return_value=args
            ), patch.object(
                run_ablation,
                "effective_configuration",
                return_value=configuration,
            ), patch.object(
                run_ablation, "_run_id", return_value="run-1"
            ), patch.object(
                run_ablation.subprocess, "run", side_effect=write_output
            ) as subprocess_run, redirect_stdout(StringIO()):
                self.assertEqual(run_ablation.main(), 0)

            manifest_path = (
                output_root / "recommended" / "run-1" / "manifest.json"
            )
            before = manifest_path.read_bytes()
            self.assertEqual(subprocess_run.call_count, 1)

            with patch.object(run_ablation, "PROJECT_ROOT", project), patch.object(
                run_ablation, "parse_args", return_value=args
            ), patch.object(
                run_ablation,
                "effective_configuration",
                return_value=configuration,
            ), patch.object(
                run_ablation.subprocess, "run"
            ) as subprocess_run, redirect_stdout(StringIO()):
                self.assertEqual(run_ablation.main(), 0)

            self.assertEqual(subprocess_run.call_count, 0)
            self.assertEqual(manifest_path.read_bytes(), before)
            self.assertEqual(
                [path.name for path in manifest_path.parent.parent.iterdir()],
                ["run-1"],
            )


if __name__ == "__main__":
    unittest.main()
