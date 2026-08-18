#!/usr/bin/env python3
"""Run one managed stage for every example and aggregate cost, time, and metrics."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv

from rubric_mapping_agent.artifacts import write_json
from rubric_mapping_agent.telemetry import aggregate_stage_reports, pricing_metadata
from scripts.run_example import DEFAULT_ARTIFACTS_ROOT, PROJECT_ROOT, run_example, utc_run_id


DEFAULT_EXAMPLES_ROOT = PROJECT_ROOT / "examples" / "item-to-cell-mapping"
DEFAULT_EVAL_RESULTS_OUTPUT = PROJECT_ROOT / "eval_results.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one stage or the complete pipeline for every task directory."
    )
    parser.add_argument("stage", choices=("part1", "part2", "part3", "pipeline"))
    parser.add_argument("--examples-root", type=Path, default=DEFAULT_EXAMPLES_ROOT)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument(
        "--eval-results-output", type=Path, default=DEFAULT_EVAL_RESULTS_OUTPUT
    )
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def discover_examples(root: Path) -> tuple[Path, ...]:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"Examples root does not exist: {resolved}")
    examples = tuple(
        child
        for child in sorted(resolved.iterdir())
        if child.is_dir()
    )
    if not examples:
        raise ValueError(f"No example directories found under {resolved}")
    return examples


def _load_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read generated JSON report: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Generated report must be a JSON object: {path}")
    return payload


def _portable(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def _average_metrics(metrics: Iterable[dict[str, Any]]) -> dict[str, float]:
    values = tuple(metrics)
    if not values:
        raise ValueError("Cannot average an empty metric collection")
    return {
        name: sum(float(value[name]) for value in values) / len(values)
        for name in ("precision", "recall", "f1")
    }


def _compact_example_report(run_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    stages: dict[str, Any] = {}
    for stage, value in report.get("stages", {}).items():
        runtime = value.get("runtime", {})
        stages[stage] = {
            "evaluation": value.get("evaluation"),
            "runtime": runtime.get("totals", {}),
        }
    return {
        "run_id": report.get("run_id"),
        "run_evaluation": _portable(run_dir / "evaluation.json"),
        "stages": stages,
        "totals": report.get("totals", {}),
    }


def build_batch_report(
    *,
    stage: str,
    batch_id: str,
    example_reports: dict[str, tuple[Path, dict[str, Any]]],
    wall_time_seconds: float,
) -> dict[str, Any]:
    runtime_reports_by_stage: dict[str, list[dict[str, Any]]] = {}
    all_runtime_reports: list[dict[str, Any]] = []
    compact_examples: dict[str, Any] = {}
    for example, (run_dir, report) in example_reports.items():
        compact_examples[example] = _compact_example_report(run_dir, report)
        for selected_stage, value in report.get("stages", {}).items():
            runtime = value["runtime"]
            runtime_reports_by_stage.setdefault(selected_stage, []).append(runtime)
            all_runtime_reports.append(runtime)

    stage_totals = {
        selected_stage: aggregate_stage_reports(
            reports,
            wall_time_seconds=sum(
                float(report.get("totals", {}).get("process_wall_time_seconds", 0))
                for report in reports
            ),
        )
        for selected_stage, reports in runtime_reports_by_stage.items()
    }
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "command": f"{stage}-all",
        "pricing": pricing_metadata(),
        "examples": compact_examples,
        "stages": stage_totals,
        "totals": aggregate_stage_reports(
            all_runtime_reports, wall_time_seconds=wall_time_seconds
        ),
    }


def build_assignment_eval_results(
    batch_report: dict[str, Any],
) -> dict[str, Any]:
    """Build the exact repository-level evaluation deliverable named by the brief."""

    examples: dict[str, Any] = {}
    for example, value in batch_report["examples"].items():
        stages = value["stages"]
        part1 = stages.get("part1", {}).get("evaluation")
        part3 = stages.get("part3", {}).get("evaluation")
        if not isinstance(part1, dict) or not isinstance(part3, dict):
            raise ValueError(
                f"Evaluated pipeline report for {example} lacks Part 1 or Part 3 metrics"
            )
        examples[example] = {
            "part1": part1["metrics"],
            "part3": part3["metrics"],
            "runtime": {
                "parts": {
                    stage: stage_value["runtime"]
                    for stage, stage_value in stages.items()
                },
                "total": value["totals"],
            },
            "run_evaluation": value["run_evaluation"],
        }

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assignment_requirement": (
            "Part 1 and Part 3 precision, recall, and F1 for each labeled example"
        ),
        "metrics": {
            "part1": "grouped-cell-pair precision/recall/F1",
            "part3": "criterion-macro cell precision/recall/F1",
        },
        "pricing": batch_report["pricing"],
        "examples": examples,
        "summary": {
            "part1_task_macro": _average_metrics(
                value["part1"] for value in examples.values()
            ),
            "part3_task_macro_criterion": _average_metrics(
                value["part3"] for value in examples.values()
            ),
            "runtime": {
                "parts": batch_report["stages"],
                "total": batch_report["totals"],
            },
        },
    }


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    if args.dry_run and args.evaluate:
        print("error: --evaluate cannot be combined with --dry-run", file=sys.stderr)
        return 2

    started = time.monotonic()
    batch_id = utc_run_id()
    try:
        examples = discover_examples(args.examples_root)
        reports: dict[str, tuple[Path, dict[str, Any]]] = {}
        for example_dir in examples:
            print(f"==> {args.stage}: {example_dir.name}", flush=True)
            run_dir = run_example(
                args.stage,
                example_dir.name,
                args.artifacts_root,
                task_dir=example_dir,
                dry_run=args.dry_run,
                evaluate=args.evaluate,
            )
            if not args.dry_run:
                reports[example_dir.name] = (
                    run_dir,
                    _load_object(run_dir / "evaluation.json"),
                )
    except subprocess.CalledProcessError as exc:
        print(
            f"error: {args.stage} failed with exit code {exc.returncode}",
            file=sys.stderr,
        )
        return exc.returncode or 1
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        return 0

    batch_report = build_batch_report(
        stage=args.stage,
        batch_id=batch_id,
        example_reports=reports,
        wall_time_seconds=time.monotonic() - started,
    )
    batch_output = (
        args.artifacts_root.resolve().parent
        / "evaluations"
        / f"{args.stage}-all-{batch_id}.json"
    )
    write_json(batch_report, batch_output)
    total = batch_report["totals"]
    cost = total.get("total_cost_usd")
    rendered_cost = f"${float(cost):.6f}" if cost is not None else "unavailable"
    print(
        f"All examples total: {float(total['wall_time_seconds']):.2f}s; "
        f"estimated cost {rendered_cost}"
    )
    print(f"Batch evaluation: {batch_output}")

    if args.stage == "pipeline" and args.evaluate:
        eval_results = build_assignment_eval_results(batch_report)
        output = args.eval_results_output.resolve()
        write_json(eval_results, output)
        print(f"Assignment eval results: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
