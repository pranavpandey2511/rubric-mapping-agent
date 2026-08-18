#!/usr/bin/env python3
"""Run one example stage with timestamped artifacts and recorded lineage."""

from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from rubric_mapping_agent.configuration import (
    part3_context as _part3_context,
    sheet_max_workers as _sheet_max_workers,
    stage_scope as _stage_scope,
)
from rubric_mapping_agent.handoff import HandoffPolicy
from rubric_mapping_agent.managed_runs import (
    evaluate_outputs,
    evaluate_part2,
    gold_sections_path,
    latest_part1_bundle,
    manifest_path as _manifest_path,
    upstream_for_part3,
    write_manifest as _write_manifest,
)
from rubric_mapping_agent.review import create_review_workbook
from rubric_mapping_agent.visual.inspection import VisualWorkbookConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_ROOT = PROJECT_ROOT / "examples" / "item-to-cell-mapping"
DEFAULT_ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts" / "example-runs"
EXAMPLE_ALIASES = {
    "1": "keysight",
    "2": "textron-1",
    "3": "topbuild",
}
STAGE_OUTPUTS = {
    "part1": Path("part1/sections.json"),
    "part2": Path("part2/subsections.json"),
    "part3": Path("part3/items_to_cells.json"),
}
PART1_SUMMARY_OUTPUT = Path("part1/summary.md")
PART2_INDEX_OUTPUT = Path("part2/subsection_index.json")
REVIEW_OUTPUT = Path("review/complete_annotated.xlsx")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one rubric-mapping example stage and preserve timestamped "
            "artifact lineage."
        )
    )
    parser.add_argument(
        "stage",
        choices=("part1", "part2", "part3", "pipeline"),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--example",
        help="Example name (keysight, textron-1, topbuild) or number (1, 2, 3).",
    )
    source.add_argument(
        "--directory",
        type=Path,
        help=(
            "Task directory containing input.xlsx, complete.xlsx, and "
            "instructions.md (plus rubric.json for Part 3)."
        ),
    )
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=DEFAULT_ARTIFACTS_ROOT,
        help=f"Artifact root (default: {DEFAULT_ARTIFACTS_ROOT}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve upstream artifacts and print commands without running them.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help=(
            "Evaluate the completed stage outputs and save reports in the run "
            "folder."
        ),
    )
    return parser.parse_args()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def resolve_example(value: str) -> str:
    example = EXAMPLE_ALIASES.get(value.strip().lower(), value.strip().lower())
    example_dir = EXAMPLES_ROOT / example
    required = ("input.xlsx", "complete.xlsx", "instructions.md", "rubric.json")
    missing = [
        example_dir / name
        for name in required
        if not (example_dir / name).is_file()
    ]
    if missing:
        available = ", ".join(
            sorted(path.name for path in EXAMPLES_ROOT.iterdir() if path.is_dir())
        )
        raise ValueError(
            f"Unknown or incomplete example {value!r}. Available examples: {available}"
        )
    return example


def resolve_task_directory(value: Path, stage: str, *, evaluate: bool) -> Path:
    """Resolve and validate an arbitrary task directory for one invocation."""

    task_dir = value.expanduser().resolve()
    if not task_dir.is_dir():
        raise ValueError(f"Task directory does not exist: {task_dir}")

    required = [
        task_dir / "input.xlsx",
        task_dir / "complete.xlsx",
        task_dir / "instructions.md",
    ]
    if stage in {"part3", "pipeline"}:
        required.append(task_dir / "rubric.json")
    if evaluate and stage in {"part1", "pipeline"}:
        required.append(gold_sections_path(task_dir))
    if evaluate and stage in {"part3", "pipeline"}:
        required.append(task_dir / "items_to_cells.json")

    missing = [path for path in required if not path.is_file()]
    if missing:
        rendered = "\n".join(f"  - {path}" for path in missing)
        raise ValueError(f"Task directory is missing required files:\n{rendered}")
    return task_dir


def directory_run_name(task_dir: Path) -> str:
    """Return a stable artifact namespace without basename collisions."""

    digest = hashlib.sha256(str(task_dir.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{task_dir.name}-{digest}"


def _relative_to_run(path: Path, run_dir: Path) -> str:
    return os.path.relpath(path.resolve(), start=run_dir.resolve())


def _configuration() -> dict[str, str | bool | int | float]:
    handoff = HandoffPolicy.from_environment()
    visual = VisualWorkbookConfig.from_env()
    return {
        "model": os.getenv("OPENAI_MODEL", "openai:gpt-5.6-terra"),
        "code_interpreter_memory": os.getenv("OPENAI_CODE_INTERPRETER_MEMORY", "4g"),
        "part1_policy": "current",
        "part1_scope": _stage_scope("part1"),
        "part2_scope": _stage_scope("part2"),
        "part3_evidence": "scoring_aware",
        "part3_context": _part3_context(),
        "part3_scope": _stage_scope("part3"),
        "part2_retrieval_index": "agent",
        "part2_index_validation": "disabled",
        "sheet_max_workers": _sheet_max_workers(),
        "handoff_json": handoff.include_json,
        "handoff_summary": handoff.include_summary,
        "visual_backend": visual.backend,
        "visual_width": visual.width,
        "visual_height": visual.height,
        "visual_timeout_seconds": visual.timeout_seconds,
        "visual_capture_delay_seconds": visual.capture_delay_seconds,
    }


def _common_command(example_dir: Path, stage: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "rubric_mapping_agent.workflow",
        stage,
        "--input",
        str(example_dir / "input.xlsx"),
        "--complete",
        str(example_dir / "complete.xlsx"),
        "--instructions",
        str(example_dir / "instructions.md"),
    ]


def stage_command(
    stage: str,
    example_dir: Path,
    output: Path,
    *,
    part1: Path | None = None,
    part1_summary: Path | None = None,
    part2: Path | None = None,
    part2_index: Path | None = None,
) -> list[str]:
    command = _common_command(example_dir, stage)
    if stage == "part1":
        if part1_summary is None:
            raise ValueError("Part 1 requires a summary output path")
        command.extend(
            (
                "--output",
                str(output),
                "--summary-output",
                str(part1_summary),
            )
        )
    elif stage == "part2":
        if part1 is None or part1_summary is None:
            raise ValueError("Part 2 requires Part 1 sections and summary artifacts")
        if part2_index is None:
            raise ValueError("Part 2 requires a retrieval index output path")
        command.extend(
            (
                "--sections",
                str(part1),
                "--section-summary",
                str(part1_summary),
                "--output",
                str(output),
                "--index-output",
                str(part2_index),
            )
        )
    elif stage == "part3":
        command.extend(("--rubric", str(example_dir / "rubric.json")))
        if (part1 is None) != (part1_summary is None):
            raise ValueError("Part 3 requires a complete Part 1 bundle")
        if (part2 is None) != (part2_index is None):
            raise ValueError("Part 3 requires a complete Part 2 bundle")
        if part2 is not None and part1 is None:
            raise ValueError("Part 3 Part 2 context requires Part 1 lineage")
        if part1 is not None:
            command.extend(
                (
                    "--sections",
                    str(part1),
                    "--section-summary",
                    str(part1_summary),
                )
            )
        if part2 is not None:
            command.extend(
                (
                    "--subsections",
                    str(part2),
                    "--subsection-index",
                    str(part2_index),
                )
            )
        command.extend(("--output", str(output)))
    else:
        raise ValueError(f"Unsupported individual stage: {stage}")
    return command


def create_run_review(
    example_dir: Path,
    run_dir: Path,
    outputs: dict[str, Path],
    upstream: dict[str, Path],
) -> Path:
    """Create the cumulative annotated workbook for one managed run."""

    sections = outputs.get("part1", upstream.get("part1"))
    subsections = outputs.get("part2", upstream.get("part2"))
    items_to_cells = outputs.get("part3", upstream.get("part3"))
    if subsections is not None and sections is None:
        raise ValueError("Review generation requires Part 1 lineage for Part 2")

    destination = run_dir / REVIEW_OUTPUT
    rubric = example_dir / "rubric.json" if items_to_cells is not None else None
    return create_review_workbook(
        example_dir / "complete.xlsx",
        destination,
        sections_path=sections,
        subsections_path=subsections,
        items_to_cells_path=items_to_cells,
        rubric_path=rubric,
    )


def run_example(
    stage: str,
    example: str,
    artifacts_root: Path,
    *,
    task_dir: Path | None = None,
    dry_run: bool = False,
    evaluate: bool = False,
    run_id: str | None = None,
) -> Path:
    example_dir = (task_dir or (EXAMPLES_ROOT / example)).resolve()
    example_root = artifacts_root.resolve() / example
    run_id = run_id or utc_run_id()
    run_dir = example_root / run_id
    configuration = _configuration()
    part3_context = str(configuration["part3_context"])
    stages = (
        ("part1", "part2", "part3")
        if stage == "pipeline" and part3_context == "part1_part2"
        else (("part1", "part3") if stage == "pipeline" else (stage,))
    )
    outputs: dict[str, Path] = {}
    upstream: dict[str, Path] = {}
    evaluations: dict[str, Path] = {}

    if dry_run and evaluate:
        raise ValueError("--evaluate cannot be combined with --dry-run")

    if stage == "part2":
        upstream["part1"], upstream["part1_summary"] = latest_part1_bundle(
            example_root
        )
    elif stage == "part3" and part3_context == "part1":
        upstream["part1"], upstream["part1_summary"] = latest_part1_bundle(
            example_root
        )
    elif stage == "part3" and part3_context == "part1_part2":
        (
            upstream["part1"],
            upstream["part1_summary"],
            upstream["part2"],
            upstream["subsection_index"],
        ) = upstream_for_part3(example_root)

    for selected_stage in stages:
        output = run_dir / STAGE_OUTPUTS[selected_stage]
        part1_summary_output = run_dir / PART1_SUMMARY_OUTPUT
        part2_index_output = run_dir / PART2_INDEX_OUTPUT
        if selected_stage == "part1":
            part1 = None
            part2 = None
        elif selected_stage == "part2":
            part1 = outputs.get("part1", upstream.get("part1"))
            part2 = None
        else:
            part1 = (
                outputs.get("part1", upstream.get("part1"))
                if part3_context != "none"
                else None
            )
            part2 = (
                outputs.get("part2", upstream.get("part2"))
                if part3_context == "part1_part2"
                else None
            )
        part1_summary = (
            part1_summary_output
            if selected_stage == "part1"
            else (
                outputs.get("part1_summary", upstream.get("part1_summary"))
                if part3_context != "none" or selected_stage == "part2"
                else None
            )
        )
        part2_index = (
            part2_index_output
            if selected_stage == "part2"
            else (
                outputs.get("subsection_index", upstream.get("subsection_index"))
                if part3_context == "part1_part2"
                else None
            )
        )
        command = stage_command(
            selected_stage,
            example_dir,
            output,
            part1=part1,
            part1_summary=part1_summary,
            part2=part2,
            part2_index=part2_index,
        )
        print(f"Running {selected_stage}: {shlex.join(command)}")
        if not dry_run:
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(command, cwd=PROJECT_ROOT, check=True)
            if not output.is_file():
                raise FileNotFoundError(
                    f"{selected_stage} completed without creating {output}"
                )
        outputs[selected_stage] = output
        visual_inspection = output.parent / "visual-inspection"
        if (
            not dry_run
            and visual_inspection.is_dir()
            and any(visual_inspection.iterdir())
        ):
            outputs[f"{selected_stage}_visual_inspection"] = visual_inspection
        if selected_stage == "part1":
            if not dry_run and not part1_summary_output.is_file():
                raise FileNotFoundError(
                    f"part1 completed without creating {part1_summary_output}"
                )
            outputs["part1_summary"] = part1_summary_output
        elif selected_stage == "part2":
            if not dry_run and not part2_index_output.is_file():
                raise FileNotFoundError(
                    f"part2 completed without creating {part2_index_output}"
                )
            outputs["subsection_index"] = part2_index_output

    review_output = run_dir / REVIEW_OUTPUT
    if not dry_run:
        review_output = create_run_review(
            example_dir,
            run_dir,
            outputs,
            upstream,
        )
        if not review_output.is_file():
            raise FileNotFoundError(
                f"review generation completed without creating {review_output}"
            )
    outputs["review_workbook"] = review_output

    print(f"Example: {example}")
    print(f"Run: {run_id}")
    for name, path in upstream.items():
        print(f"Upstream {name}: {path}")
    for name, path in outputs.items():
        print(f"Output {name}: {path}")

    if not dry_run:
        if evaluate:
            evaluations = evaluate_outputs(
                stage,
                example_dir,
                run_dir,
                outputs,
                upstream,
            )
        manifest = {
            "schema_version": 1,
            "example": example,
            "task_directory": str(example_dir),
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "command": stage,
            "configuration": configuration,
            "sources": {
                name: portable_source_path(example_dir / name)
                for name in (
                    "input.xlsx",
                    "complete.xlsx",
                    "instructions.md",
                    "rubric.json",
                )
                if (example_dir / name).is_file()
            },
            "outputs": {
                name: _relative_to_run(path, run_dir) for name, path in outputs.items()
            },
            "upstream": {
                name: _relative_to_run(path, run_dir) for name, path in upstream.items()
            },
            "evaluations": {
                name: _relative_to_run(path, run_dir)
                for name, path in evaluations.items()
            },
        }
        _write_manifest(run_dir, manifest)
        print(f"Manifest: {_manifest_path(run_dir)}")
    return run_dir


def portable_source_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    try:
        if args.directory is not None:
            task_dir = resolve_task_directory(
                args.directory,
                args.stage,
                evaluate=args.evaluate,
            )
            example = directory_run_name(task_dir)
        else:
            task_dir = None
            example = resolve_example(args.example)
        run_example(
            args.stage,
            example,
            args.artifacts_root,
            task_dir=task_dir,
            dry_run=args.dry_run,
            evaluate=args.evaluate,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(
            f"error: workflow command failed with exit code {exc.returncode}",
            file=sys.stderr,
        )
        return exc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
