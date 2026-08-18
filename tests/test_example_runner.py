from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts.run_example import (
    REVIEW_OUTPUT,
    create_run_review,
    directory_run_name,
    evaluate_part2,
    gold_sections_path,
    latest_part1_bundle,
    resolve_example,
    resolve_task_directory,
    run_example,
    upstream_for_part3,
)


class ExampleRunnerTests(unittest.TestCase):
    def _write_runtime(self, command: list[str]) -> None:
        path = Path(command[command.index("--telemetry-output") + 1])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "command": command[3],
                    "pricing": {},
                    "invocations": [],
                    "totals": {"wall_time_seconds": 1.0},
                }
            ),
            encoding="utf-8",
        )

    def _write_review(
        self,
        _workbook_path: Path,
        output_path: Path,
        **_: object,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"review workbook fixture")
        return output_path.resolve()

    def _manifest(
        self,
        example_root: Path,
        run_id: str,
        *,
        outputs: dict[str, str],
        upstream: dict[str, str] | None = None,
    ) -> Path:
        run_dir = example_root / run_id
        for relative in outputs.values():
            artifact = run_dir / relative
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("{}\n", encoding="utf-8")
        manifest = {
            "outputs": outputs,
            "upstream": upstream or {},
        }
        path = run_dir / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_numeric_example_aliases_resolve(self) -> None:
        self.assertEqual(resolve_example("1"), "keysight")
        self.assertEqual(resolve_example("2"), "textron-1")
        self.assertEqual(resolve_example("3"), "topbuild")

    def test_arbitrary_task_directory_is_validated_by_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task_dir = Path(temp_dir) / "custom-task"
            task_dir.mkdir()
            for name in ("input.xlsx", "complete.xlsx", "instructions.md"):
                (task_dir / name).write_text("fixture\n", encoding="utf-8")

            resolved = resolve_task_directory(task_dir, "part1", evaluate=False)

            self.assertEqual(resolved, task_dir.resolve())
            self.assertRegex(
                directory_run_name(resolved),
                r"^custom-task-[0-9a-f]{8}$",
            )
            with self.assertRaisesRegex(ValueError, "rubric.json"):
                resolve_task_directory(task_dir, "pipeline", evaluate=False)
            with self.assertRaisesRegex(ValueError, "sections.json"):
                resolve_task_directory(task_dir, "part1", evaluate=True)

    def test_builtin_mapping_directory_uses_matching_sectioning_labels(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "item-to-cell-mapping"
            / "keysight"
        )

        self.assertEqual(
            gold_sections_path(task_dir),
            Path(__file__).resolve().parents[1]
            / "examples"
            / "sectioning"
            / "keysight"
            / "sections.json",
        )
        self.assertEqual(
            resolve_task_directory(task_dir, "pipeline", evaluate=True),
            task_dir,
        )

    def test_arbitrary_task_directory_is_recorded_in_manifest(self) -> None:
        def write_declared_output(command: list[str], **_: object) -> None:
            output = Path(command[command.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("{}\n", encoding="utf-8")
            visual_dir = output.parent / "visual-inspection"
            visual_dir.mkdir()
            (visual_dir / "capture.png").write_bytes(b"png fixture")
            (visual_dir / "capture.json").write_text("{}\n", encoding="utf-8")
            summary = Path(command[command.index("--summary-output") + 1])
            summary.parent.mkdir(parents=True, exist_ok=True)
            summary.write_text("# Generated Summary\n", encoding="utf-8")
            self._write_runtime(command)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / "custom-task"
            task_dir.mkdir()
            for name in ("input.xlsx", "complete.xlsx", "instructions.md"):
                (task_dir / name).write_text("fixture\n", encoding="utf-8")
            task_name = directory_run_name(task_dir)
            with patch(
                "scripts.run_example.subprocess.run",
                side_effect=write_declared_output,
            ), patch(
                "scripts.run_example.create_review_workbook",
                side_effect=self._write_review,
            ), redirect_stdout(StringIO()):
                run_dir = run_example(
                    "part1",
                    task_name,
                    root / "runs",
                    task_dir=task_dir,
                    run_id="20260818T000000.000000Z",
                )

            manifest = json.loads(
                (run_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["example"], task_name)
            self.assertEqual(manifest["task_directory"], str(task_dir.resolve()))
            self.assertEqual(
                manifest["sources"]["input.xlsx"],
                str((task_dir / "input.xlsx").resolve()),
            )
            self.assertEqual(
                manifest["outputs"]["review_workbook"],
                str(REVIEW_OUTPUT),
            )
            self.assertEqual(
                manifest["outputs"]["part1_visual_inspection"],
                "part1/visual-inspection",
            )

    def test_part3_uses_part1_lineage_from_latest_part2(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "keysight"
            part1_manifest = self._manifest(
                root,
                "20260818T010000.000000Z",
                outputs={
                    "part1": "part1/sections.json",
                    "part1_summary": "part1/summary.md",
                },
            )
            part1 = part1_manifest.parent / "part1" / "sections.json"
            part1_summary = part1_manifest.parent / "part1" / "summary.md"
            part2_manifest = self._manifest(
                root,
                "20260818T020000.000000Z",
                outputs={
                    "part2": "part2/subsections.json",
                    "subsection_index": "part2/subsection_index.json",
                },
                upstream={
                    "part1": f"../{part1_manifest.parent.name}/part1/sections.json",
                    "part1_summary": f"../{part1_manifest.parent.name}/part1/summary.md",
                },
            )
            part2 = part2_manifest.parent / "part2" / "subsections.json"
            part2_index = part2_manifest.parent / "part2" / "subsection_index.json"
            self._manifest(
                root,
                "20260818T030000.000000Z",
                outputs={"part1": "part1/sections.json"},
            )

            selected = upstream_for_part3(root)

            self.assertEqual(
                selected,
                (
                    part1.resolve(),
                    part1_summary.resolve(),
                    part2.resolve(),
                    part2_index.resolve(),
                ),
            )

    def test_part2_requires_latest_complete_part1_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "keysight"
            complete = self._manifest(
                root,
                "20260818T010000.000000Z",
                outputs={
                    "part1": "part1/sections.json",
                    "part1_summary": "part1/summary.md",
                },
            )
            self._manifest(
                root,
                "20260818T020000.000000Z",
                outputs={"part1": "part1/sections.json"},
            )

            sections, summary = latest_part1_bundle(root)

            self.assertEqual(
                sections,
                (complete.parent / "part1" / "sections.json").resolve(),
            )
            self.assertEqual(
                summary,
                (complete.parent / "part1" / "summary.md").resolve(),
            )

    def test_pipeline_writes_all_outputs_and_one_manifest(self) -> None:
        def write_declared_output(command: list[str], **_: object) -> None:
            output = Path(command[command.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("{}\n", encoding="utf-8")
            if "--summary-output" in command:
                summary = Path(command[command.index("--summary-output") + 1])
                summary.parent.mkdir(parents=True, exist_ok=True)
                summary.write_text("# Generated Summary\n", encoding="utf-8")
            if "--index-output" in command:
                index = Path(command[command.index("--index-output") + 1])
                index.parent.mkdir(parents=True, exist_ok=True)
                index.write_text("{}\n", encoding="utf-8")
            self._write_runtime(command)

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "example-runs"
            with patch.dict(os.environ, {}, clear=True), patch(
                "scripts.run_example.subprocess.run",
                side_effect=write_declared_output,
            ) as subprocess_run, patch(
                "scripts.run_example.create_review_workbook",
                side_effect=self._write_review,
            ):
                with redirect_stdout(StringIO()):
                    run_dir = run_example(
                        "pipeline",
                        "keysight",
                        artifact_root,
                        run_id="20260818T040000.000000Z",
                    )

            self.assertEqual(subprocess_run.call_count, 3)
            self.assertTrue((run_dir / "part1" / "sections.json").is_file())
            self.assertTrue((run_dir / "part1" / "summary.md").is_file())
            self.assertTrue((run_dir / "part2" / "subsections.json").is_file())
            self.assertTrue((run_dir / "part2" / "subsection_index.json").is_file())
            self.assertFalse((run_dir / "part2" / "summary.md").exists())
            self.assertTrue((run_dir / "part3" / "items_to_cells.json").is_file())
            self.assertFalse((run_dir / "part3" / "subsection_index.json").exists())
            self.assertTrue((run_dir / REVIEW_OUTPUT).is_file())
            self.assertTrue((run_dir / "evaluation.json").is_file())
            manifest = json.loads(
                (run_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["command"], "pipeline")
            self.assertEqual(
                manifest["configuration"],
                {
                    "model": "openai:gpt-5.6-terra",
                    "code_interpreter_memory": "4g",
                    "part1_policy": "current",
                    "part1_scope": "sheet",
                    "part2_scope": "workbook",
                    "part3_evidence": "scoring_aware",
                    "part3_context": "part1_part2",
                    "part3_scope": "workbook",
                    "part2_retrieval_index": "agent",
                    "part2_index_validation": "disabled",
                    "sheet_max_workers": 4,
                    "handoff_json": True,
                    "handoff_summary": True,
                    "visual_backend": "off",
                    "visual_width": 1440,
                    "visual_height": 900,
                    "visual_timeout_seconds": 45.0,
                    "visual_capture_delay_seconds": 0.6,
                },
            )
            self.assertEqual(
                set(manifest["outputs"]),
                {
                    "part1",
                    "part1_summary",
                    "part2",
                    "part3",
                    "subsection_index",
                    "review_workbook",
                },
            )
            self.assertEqual(manifest["upstream"], {})

    def test_evaluated_pipeline_records_each_report(self) -> None:
        def write_declared_output(command: list[str], **_: object) -> None:
            output = Path(command[command.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("{}\n", encoding="utf-8")
            if "--summary-output" in command:
                summary = Path(command[command.index("--summary-output") + 1])
                summary.parent.mkdir(parents=True, exist_ok=True)
                summary.write_text("# Generated Summary\n", encoding="utf-8")
            if "--index-output" in command:
                index = Path(command[command.index("--index-output") + 1])
                index.parent.mkdir(parents=True, exist_ok=True)
                index.write_text("{}\n", encoding="utf-8")
            self._write_runtime(command)

        def write_evaluations(
            stage: str,
            example_dir: Path,
            run_dir: Path,
            outputs: dict[str, Path],
            upstream: dict[str, Path],
            runtimes: dict[str, dict[str, object]],
        ) -> dict[str, Path]:
            self.assertEqual(stage, "pipeline")
            self.assertEqual(example_dir.name, "keysight")
            self.assertEqual(
                set(outputs),
                {
                    "part1",
                    "part1_summary",
                    "part2",
                    "part3",
                    "subsection_index",
                    "review_workbook",
                },
            )
            self.assertEqual(upstream, {})
            self.assertEqual(set(runtimes), {"part1", "part2", "part3"})
            reports = {}
            for selected_stage in ("part1", "part2", "part3"):
                report = run_dir / selected_stage / "evaluation.json"
                if selected_stage == "part1":
                    result = {
                        "evaluation": "sectioning",
                        "metrics": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
                        "section_counts": {"gold": 1, "predicted": 1},
                    }
                elif selected_stage == "part2":
                    result = {
                        "evaluation": "part2_structural_diagnostics",
                        "metrics": {"eligible_diff_coverage": 1.0},
                        "limitations": "no gold",
                    }
                else:
                    result = {
                        "evaluation": "i2c_mapping",
                        "summary": {
                            "criterion_macro": {
                                "precision": 1.0,
                                "recall": 1.0,
                                "f1": 1.0,
                            },
                            "item_macro": {
                                "precision": 1.0,
                                "recall": 1.0,
                                "f1": 1.0,
                            },
                            "mapped_item_fraction": 1.0,
                            "mapped_items": 1,
                            "total_items": 1,
                        },
                    }
                report.write_text(json.dumps({"result": result}), encoding="utf-8")
                reports[selected_stage] = report
            return reports

        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "example-runs"
            with patch(
                "scripts.run_example.subprocess.run",
                side_effect=write_declared_output,
            ), patch(
                "scripts.run_example.evaluate_outputs",
                side_effect=write_evaluations,
            ), patch(
                "scripts.run_example.create_review_workbook",
                side_effect=self._write_review,
            ):
                with redirect_stdout(StringIO()):
                    run_dir = run_example(
                        "pipeline",
                        "keysight",
                        artifact_root,
                        evaluate=True,
                        run_id="20260818T050000.000000Z",
                    )

            manifest = json.loads(
                (run_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["evaluations"],
                {
                    "part1": "part1/evaluation.json",
                    "part2": "part2/evaluation.json",
                    "part3": "part3/evaluation.json",
                    "run": "evaluation.json",
                },
            )

    def test_pipeline_respects_part3_context_when_selecting_upstream(self) -> None:
        def write_declared_output(command: list[str], **_: object) -> None:
            output = Path(command[command.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("{}\n", encoding="utf-8")
            if "--summary-output" in command:
                summary = Path(command[command.index("--summary-output") + 1])
                summary.parent.mkdir(parents=True, exist_ok=True)
                summary.write_text("# Generated Summary\n", encoding="utf-8")
            self._write_runtime(command)

        for context, expects_part1 in (("none", False), (" Part1 ", True)):
            with self.subTest(context=context), tempfile.TemporaryDirectory() as temp_dir:
                artifact_root = Path(temp_dir) / "example-runs"
                with patch.dict(
                    "os.environ", {"RUBRIC_MAP_PART3_CONTEXT": context}, clear=True
                ), patch(
                    "scripts.run_example.subprocess.run",
                    side_effect=write_declared_output,
                ) as subprocess_run, patch(
                    "scripts.run_example.create_review_workbook",
                    side_effect=self._write_review,
                ), redirect_stdout(StringIO()):
                    run_dir = run_example(
                        "pipeline",
                        "keysight",
                        artifact_root,
                        run_id=f"20260818T06000{int(expects_part1)}.000000Z",
                    )

                self.assertEqual(subprocess_run.call_count, 2)
                part3_command = subprocess_run.call_args_list[-1].args[0]
                self.assertEqual("--sections" in part3_command, expects_part1)
                self.assertNotIn("--subsections", part3_command)
                manifest = json.loads(
                    (run_dir / "manifest.json").read_text(encoding="utf-8")
                )
                expected_outputs = {
                    "part1",
                    "part1_summary",
                    "part3",
                    "review_workbook",
                }
                self.assertEqual(set(manifest["outputs"]), expected_outputs)

    def test_review_uses_every_available_cumulative_mapping_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            example_dir = root / "task"
            run_dir = root / "run"
            example_dir.mkdir()
            paths = {
                "part1": root / "previous" / "part1" / "sections.json",
                "part2": root / "previous" / "part2" / "subsections.json",
                "part3": run_dir / "part3" / "items_to_cells.json",
            }

            cases = (
                (
                    {"part1": paths["part1"]},
                    {},
                    {
                        "sections_path": paths["part1"],
                        "subsections_path": None,
                        "items_to_cells_path": None,
                        "rubric_path": None,
                    },
                ),
                (
                    {"part2": paths["part2"]},
                    {"part1": paths["part1"]},
                    {
                        "sections_path": paths["part1"],
                        "subsections_path": paths["part2"],
                        "items_to_cells_path": None,
                        "rubric_path": None,
                    },
                ),
                (
                    {"part3": paths["part3"]},
                    {"part1": paths["part1"], "part2": paths["part2"]},
                    {
                        "sections_path": paths["part1"],
                        "subsections_path": paths["part2"],
                        "items_to_cells_path": paths["part3"],
                        "rubric_path": example_dir / "rubric.json",
                    },
                ),
            )

            for outputs, upstream, expected in cases:
                with self.subTest(outputs=tuple(outputs)), patch(
                    "scripts.run_example.create_review_workbook",
                    side_effect=self._write_review,
                ) as create_review:
                    result = create_run_review(
                        example_dir,
                        run_dir,
                        outputs,
                        upstream,
                    )

                self.assertEqual(result, (run_dir / REVIEW_OUTPUT).resolve())
                self.assertEqual(
                    create_review.call_args.args,
                    (example_dir / "complete.xlsx", run_dir / REVIEW_OUTPUT),
                )
                self.assertEqual(create_review.call_args.kwargs, expected)

    def test_part2_evaluation_reports_gold_free_structural_diagnostics(self) -> None:
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "input.xlsx"
            complete_path = root / "complete.xlsx"
            for path, values in (
                (input_path, (None, None)),
                (complete_path, (1, 2)),
            ):
                workbook = Workbook()
                sheet = workbook.active
                sheet.title = "Model"
                sheet["A1"], sheet["B1"] = values
                workbook.save(path)
                workbook.close()

            sections_path = root / "sections.json"
            sections_path.write_text(
                json.dumps(
                    {
                        "sections": [
                            {
                                "section_id": "section_001",
                                "sheet": "Model",
                                "cells": ["A1", "B1"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            subsections_path = root / "subsections.json"
            subsections_path.write_text(
                json.dumps(
                    {
                        "subsections": [
                            {
                                "subsection_id": "subsection_001",
                                "parent_section_id": "section_001",
                                "sheet": "Model",
                                "cells": ["A1"],
                                "roles": ["input"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = evaluate_part2(
                subsections_path,
                sections_path,
                input_path,
                complete_path,
            )

            self.assertFalse(result["gold_backed"])
            self.assertEqual(result["metrics"]["covered_eligible_diff_cells"], 1)
            self.assertEqual(result["metrics"]["eligible_diff_cells"], 2)
            self.assertEqual(result["metrics"]["eligible_diff_coverage"], 0.5)


if __name__ == "__main__":
    unittest.main()
