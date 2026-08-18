#!/usr/bin/env python3
"""Evaluate labeled sectioning and I2C examples through the evaluator Python API."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Iterable

from rubric_mapping_eval.common import EvaluationError
from rubric_mapping_eval.i2c_mapping import evaluate_i2c_files
from rubric_mapping_eval.sectioning import evaluate_section_files

from rubric_mapping_agent.artifacts import write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLES_DIR = PROJECT_ROOT / "examples"
DEFAULT_PREDICTIONS_DIR = PROJECT_ROOT / "artifacts" / "predictions"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "eval_results.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate sectioning and item-to-cell predictions for the labeled "
            "examples and write a consolidated evaluation report."
        )
    )
    parser.add_argument(
        "--examples-dir",
        type=Path,
        default=DEFAULT_EXAMPLES_DIR,
        help=f"labeled examples root (default: {DEFAULT_EXAMPLES_DIR})",
    )
    parser.add_argument(
        "--predictions-dir",
        type=Path,
        default=DEFAULT_PREDICTIONS_DIR,
        help=(
            "prediction root containing <task>/part1/sections.json and "
            f"<task>/part3/items_to_cells.json (default: {DEFAULT_PREDICTIONS_DIR})"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"result JSON path (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--kind",
        choices=("all", "sectioning", "i2c"),
        default="all",
        help="evaluation family to run (default: all)",
    )
    parser.add_argument(
        "--task",
        action="append",
        dest="tasks",
        metavar="NAME",
        help="evaluate only this task; repeat to select multiple tasks",
    )
    return parser.parse_args()


def task_directories(root: Path, required_files: Iterable[str]) -> dict[str, Path]:
    if not root.is_dir():
        raise ValueError(f"Example directory does not exist: {root}")

    required = tuple(required_files)
    tasks = {
        child.name: child
        for child in sorted(root.iterdir())
        if child.is_dir() and all((child / name).is_file() for name in required)
    }
    if not tasks:
        joined = ", ".join(required)
        raise ValueError(f"No example tasks with {joined} found under {root}")
    return tasks


def select_tasks(tasks: dict[str, Path], selected: set[str] | None) -> dict[str, Path]:
    if selected is None:
        return tasks

    unknown = sorted(selected - tasks.keys())
    if unknown:
        raise ValueError(f"Unknown task(s): {', '.join(unknown)}")
    return {name: path for name, path in tasks.items() if name in selected}


def require_predictions(paths: Iterable[Path]) -> None:
    missing = sorted(path for path in paths if not path.is_file())
    if not missing:
        return

    rendered = "\n".join(f"  - {path}" for path in missing)
    raise ValueError(
        "Missing prediction files:\n"
        f"{rendered}\n"
        "Generate the predictions at these paths, or pass --predictions-dir."
    )


def prediction_path(
    predictions_dir: Path,
    task_name: str,
    stage: str,
    filename: str,
) -> Path:
    """Prefer stage-scoped outputs while retaining legacy flat-run support."""

    staged = predictions_dir / task_name / stage / filename
    legacy = predictions_dir / task_name / filename
    return staged if staged.is_file() or not legacy.is_file() else legacy


def required_prediction_paths(
    examples_dir: Path,
    predictions_dir: Path,
    selected_tasks: set[str] | None,
    kind: str,
) -> list[Path]:
    paths: list[Path] = []
    if kind in ("all", "sectioning"):
        examples = select_tasks(
            task_directories(
                examples_dir / "sectioning", ("sections.json",)
            ),
            selected_tasks,
        )
        paths.extend(
            prediction_path(predictions_dir, task_name, "part1", "sections.json")
            for task_name in examples
        )

    if kind in ("all", "i2c"):
        examples = select_tasks(
            task_directories(
                examples_dir / "item-to-cell-mapping",
                ("items_to_cells.json", "rubric.json"),
            ),
            selected_tasks,
        )
        paths.extend(
            prediction_path(
                predictions_dir, task_name, "part3", "items_to_cells.json"
            )
            for task_name in examples
        )
    return paths


def average_metrics(metrics: Iterable[dict[str, float]]) -> dict[str, float]:
    values = tuple(metrics)
    if not values:
        raise ValueError("Cannot average an empty metric collection")
    return {
        name: sum(value[name] for value in values) / len(values)
        for name in ("precision", "recall", "f1")
    }


def portable_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def evaluate_sectioning(
    examples_dir: Path,
    predictions_dir: Path,
    selected_tasks: set[str] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    examples = select_tasks(
        task_directories(examples_dir / "sectioning", ("sections.json",)),
        selected_tasks,
    )
    predicted_paths = {
        task_name: prediction_path(
            predictions_dir, task_name, "part1", "sections.json"
        )
        for task_name in examples
    }

    results = {
        task_name: evaluate_section_files(
            predicted_paths[task_name],
            task_dir / "sections.json",
        )
        for task_name, task_dir in examples.items()
    }
    summary = {
        "task_count": len(results),
        "task_macro": average_metrics(
            result["metrics"] for result in results.values()
        ),
    }
    return results, summary


def evaluate_i2c(
    examples_dir: Path,
    predictions_dir: Path,
    selected_tasks: set[str] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    examples = select_tasks(
        task_directories(
            examples_dir / "item-to-cell-mapping",
            ("items_to_cells.json", "rubric.json"),
        ),
        selected_tasks,
    )
    predicted_paths = {
        task_name: prediction_path(
            predictions_dir, task_name, "part3", "items_to_cells.json"
        )
        for task_name in examples
    }

    results = {
        task_name: evaluate_i2c_files(
            predicted_paths[task_name],
            task_dir / "items_to_cells.json",
            task_dir / "rubric.json",
        )
        for task_name, task_dir in examples.items()
    }
    summary = {
        "task_count": len(results),
        "task_macro_criterion": average_metrics(
            result["summary"]["criterion_macro"] for result in results.values()
        ),
        "task_macro_item": average_metrics(
            result["summary"]["item_macro"] for result in results.values()
        ),
    }
    return results, summary


def display_summary(summary: dict[str, Any], output_path: Path) -> None:
    print(f"Wrote evaluation results to {output_path}")
    if "sectioning" in summary:
        metrics = summary["sectioning"]["task_macro"]
        print(
            "Sectioning task macro: "
            f"P={metrics['precision']:.4f} "
            f"R={metrics['recall']:.4f} "
            f"F1={metrics['f1']:.4f}"
        )
    if "i2c_mapping" in summary:
        metrics = summary["i2c_mapping"]["task_macro_criterion"]
        print(
            "I2C criterion task macro: "
            f"P={metrics['precision']:.4f} "
            f"R={metrics['recall']:.4f} "
            f"F1={metrics['f1']:.4f}"
        )


def main() -> int:
    args = parse_args()
    examples_dir = args.examples_dir.resolve()
    predictions_dir = args.predictions_dir.resolve()
    output_path = args.output.resolve()
    selected_tasks = set(args.tasks) if args.tasks else None

    results: dict[str, Any] = {}
    summary: dict[str, Any] = {}

    try:
        require_predictions(
            required_prediction_paths(
                examples_dir,
                predictions_dir,
                selected_tasks,
                args.kind,
            )
        )

        if args.kind in ("all", "sectioning"):
            section_results, section_summary = evaluate_sectioning(
                examples_dir, predictions_dir, selected_tasks
            )
            results["sectioning"] = section_results
            summary["sectioning"] = section_summary

        if args.kind in ("all", "i2c"):
            i2c_results, i2c_summary = evaluate_i2c(
                examples_dir, predictions_dir, selected_tasks
            )
            results["i2c_mapping"] = i2c_results
            summary["i2c_mapping"] = i2c_summary
    except (EvaluationError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluator": {
            "package": "rubric-mapping-eval",
            "version": version("rubric-mapping-eval"),
        },
        "examples_dir": portable_path(examples_dir),
        "predictions_dir": portable_path(predictions_dir),
        "results": results,
        "summary": summary,
    }

    write_json(payload, output_path)
    display_summary(summary, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
