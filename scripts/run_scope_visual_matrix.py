#!/usr/bin/env python3
"""Run the controlled model, stage-scope, and visual-backend experiment matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from rubric_mapping_agent.artifacts import write_json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_example import run_example


DEFAULT_EXPERIMENTS_ROOT = PROJECT_ROOT / "artifacts" / "experiments"
TASKS = ("keysight", "textron-1", "topbuild")
MODELS = (
    ("sol", "openai:gpt-5.6-sol"),
)


@dataclass(frozen=True)
class Variant:
    variant_id: str
    visual_backend: str
    part1_scope: str
    part2_scope: str
    part3_scope: str


VARIANTS = (
    Variant("off-p1-sheet-p2-workbook-p3-workbook", "off", "sheet", "workbook", "workbook"),
    Variant("off-p1-sheet-p2-sheet-p3-workbook", "off", "sheet", "sheet", "workbook"),
    Variant("off-p1-workbook-p2-workbook-p3-workbook", "off", "workbook", "workbook", "workbook"),
    Variant(
        "libreoffice-pdf-p1-workbook-p2-workbook-p3-workbook",
        "libreoffice_pdf",
        "workbook",
        "workbook",
        "workbook",
    ),
)


@dataclass(frozen=True)
class RunSpec:
    ordinal: int
    key: str
    variant_id: str
    model_label: str
    model: str
    task: str
    environment: dict[str, str]
    artifacts_root: str


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run all 12 GPT-5.6 sol full-pipeline experiments in a fixed order, with "
            "immutable planning metadata and resumable result tracking."
        )
    )
    parser.add_argument(
        "--experiments-root",
        type=Path,
        default=DEFAULT_EXPERIMENTS_ROOT,
        help=f"Parent output directory (default: {DEFAULT_EXPERIMENTS_ROOT}).",
    )
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        help="Resume an existing experiment directory instead of creating one.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the complete plan without writing files or making API calls.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop after the first failed pipeline instead of recording and continuing.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        help=(
            "Execute at most this many pending pipelines, preserving the same "
            "plan for a later resume."
        ),
    )
    parser.add_argument(
        "--run-key",
        action="append",
        dest="run_keys",
        help=(
            "Execute only this exact planned run key; repeat to select multiple "
            "runs while retaining the full matrix plan."
        ),
    )
    return parser.parse_args()


def fixed_environment() -> dict[str, str]:
    return {
        "OPENAI_CODE_INTERPRETER_MEMORY": "4g",
        "RUBRIC_MAP_SHEET_MAX_WORKERS": "1",
        "RUBRIC_MAP_PART3_CONTEXT": "part1_part2",
        "RUBRIC_MAP_HANDOFF_JSON": "true",
        "RUBRIC_MAP_HANDOFF_SUMMARY": "true",
        "RUBRIC_MAP_VISUAL_WIDTH": "1440",
        "RUBRIC_MAP_VISUAL_HEIGHT": "900",
        "RUBRIC_MAP_VISUAL_TIMEOUT_SECONDS": "45",
        "RUBRIC_MAP_VISUAL_CAPTURE_DELAY_SECONDS": "0.6",
    }


def build_run_specs(experiment_dir: Path) -> list[RunSpec]:
    specs: list[RunSpec] = []
    fixed = fixed_environment()
    ordinal = 0
    for variant in VARIANTS:
        for model_label, model in MODELS:
            for task in TASKS:
                ordinal += 1
                environment = {
                    **fixed,
                    "OPENAI_MODEL": model,
                    "RUBRIC_MAP_VISUAL_BACKEND": variant.visual_backend,
                    "RUBRIC_MAP_PART1_SCOPE": variant.part1_scope,
                    "RUBRIC_MAP_PART2_SCOPE": variant.part2_scope,
                    "RUBRIC_MAP_PART3_SCOPE": variant.part3_scope,
                }
                key = f"{variant.variant_id}__{model_label}__{task}"
                artifacts_root = (
                    experiment_dir / "runs" / variant.variant_id / model_label
                )
                specs.append(
                    RunSpec(
                        ordinal=ordinal,
                        key=key,
                        variant_id=variant.variant_id,
                        model_label=model_label,
                        model=model,
                        task=task,
                        environment=environment,
                        artifacts_root=str(artifacts_root),
                    )
                )
    return specs


def select_run_specs(
    specs: list[RunSpec], selected_keys: list[str] | None
) -> list[RunSpec]:
    if not selected_keys:
        return specs
    requested = set(selected_keys)
    known = {spec.key for spec in specs}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError("Unknown experiment run key(s): " + ", ".join(unknown))
    return [spec for spec in specs if spec.key in requested]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_snapshot() -> dict[str, Any]:
    candidates: set[Path] = set()
    for root in ("src", "skills", "evaluator/src"):
        candidates.update(path for path in (PROJECT_ROOT / root).rglob("*") if path.is_file())
    for relative in (
        "scripts/run_example.py",
        "scripts/run_scope_visual_matrix.py",
        "pyproject.toml",
        "uv.lock",
        "evaluator/pyproject.toml",
    ):
        path = PROJECT_ROOT / relative
        if path.is_file():
            candidates.add(path)

    digest = hashlib.sha256()
    for path in sorted(candidates):
        relative = str(path.relative_to(PROJECT_ROOT))
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(_sha256(path)))
    return {"file_count": len(candidates), "sha256": digest.hexdigest()}


def _input_snapshot() -> dict[str, dict[str, str]]:
    snapshot: dict[str, dict[str, str]] = {}
    for task in TASKS:
        paths = {
            "input.xlsx": PROJECT_ROOT / "examples" / "item-to-cell-mapping" / task / "input.xlsx",
            "complete.xlsx": PROJECT_ROOT / "examples" / "item-to-cell-mapping" / task / "complete.xlsx",
            "instructions.md": PROJECT_ROOT / "examples" / "item-to-cell-mapping" / task / "instructions.md",
            "rubric.json": PROJECT_ROOT / "examples" / "item-to-cell-mapping" / task / "rubric.json",
            "gold_sections.json": PROJECT_ROOT / "examples" / "sectioning" / task / "sections.json",
            "gold_items_to_cells.json": PROJECT_ROOT / "examples" / "item-to-cell-mapping" / task / "items_to_cells.json",
        }
        missing = [path for path in paths.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                f"Missing experiment input(s) for {task}: "
                + ", ".join(str(path) for path in missing)
            )
        snapshot[task] = {
            name: _sha256(path) for name, path in sorted(paths.items())
        }
    return snapshot


def _git_value(*args: str) -> str | None:
    completed = subprocess.run(
        ("git", *args),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else None


def _matrix_signature(specs: list[RunSpec]) -> str:
    payload = [
        {
            "key": spec.key,
            "environment": spec.environment,
            "task": spec.task,
        }
        for spec in specs
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_plan(experiment_id: str, experiment_dir: Path) -> dict[str, Any]:
    specs = build_run_specs(experiment_dir)
    status = _git_value("status", "--porcelain")
    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "created_at": utc_now(),
        "objective": (
            "Compare stage execution scope and optional LibreOffice PDF visual "
            "inspection using GPT-5.6 sol."
        ),
        "primary_metrics": {
            "part1": "task-macro precision, recall, and F1 over section-pair scoring",
            "part2": "gold-free structural diagnostics only",
            "part3": "task-macro criterion precision, recall, and F1",
        },
        "limitations": [
            "One stochastic run per task/configuration; no confidence intervals.",
            "Visual enabled measures tool availability; saved capture counts show actual use.",
            "Part 2 has no gold semantic labels and is not assigned P/R/F1.",
        ],
        "task_order": list(TASKS),
        "model_order": [model for _, model in MODELS],
        "variant_order": [asdict(variant) for variant in VARIANTS],
        "fixed_controls": {
            **fixed_environment(),
            "pipeline": "part1 -> part2 -> part3",
            "evaluation_after_generation": True,
            "model_temperature": 0.1,
        },
        "matrix_signature": _matrix_signature(specs),
        "planned_runs": [asdict(spec) for spec in specs],
        "provenance": {
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_dirty": bool(status),
            "source_snapshot": _source_snapshot(),
            "input_sha256": _input_snapshot(),
        },
    }


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


@contextmanager
def environment_override(values: dict[str, str]) -> Iterator[None]:
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _micro_metrics(items: dict[str, Any]) -> dict[str, Any]:
    counts = {
        name: sum(int(item["counts"][name]) for item in items.values())
        for name in ("true_positive", "false_positive", "false_negative")
    }
    tp = counts["true_positive"]
    fp = counts["false_positive"]
    fn = counts["false_negative"]
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {**counts, "precision": precision, "recall": recall, "f1": f1}


def collect_metrics(run_dir: Path) -> dict[str, Any]:
    part1 = _load_json(run_dir / "part1" / "evaluation.json")["result"]
    part2 = _load_json(run_dir / "part2" / "evaluation.json")["result"]
    part3 = _load_json(run_dir / "part3" / "evaluation.json")["result"]
    visual_captures: dict[str, int] = {}
    for stage in ("part1", "part2", "part3"):
        capture_dir = run_dir / stage / "visual-inspection"
        visual_captures[stage] = (
            len(tuple(capture_dir.glob("*.json"))) if capture_dir.is_dir() else 0
        )
    return {
        "part1": part1["metrics"],
        "part2": part2["metrics"],
        "part3": {
            **part3["summary"],
            "micro": _micro_metrics(part3["items"]),
        },
        "visual_captures": visual_captures,
    }


def _mean(records: list[dict[str, Any]], *path: str) -> float | None:
    values: list[float] = []
    for record in records:
        value: Any = record
        for name in path:
            value = value[name]
        values.append(float(value))
    return sum(values) / len(values) if values else None


def aggregate_results(
    specs: list[RunSpec], runs: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    aggregates: list[dict[str, Any]] = []
    for variant in VARIANTS:
        for model_label, model in MODELS:
            group_specs = [
                spec
                for spec in specs
                if spec.variant_id == variant.variant_id
                and spec.model_label == model_label
            ]
            completed = [
                runs[spec.key]
                for spec in group_specs
                if runs.get(spec.key, {}).get("status") == "completed"
            ]
            metrics = [record["metrics"] for record in completed]
            micro_counts = {
                name: sum(
                    int(metric["part3"]["micro"][name]) for metric in metrics
                )
                for name in ("true_positive", "false_positive", "false_negative")
            }
            tp = micro_counts["true_positive"]
            fp = micro_counts["false_positive"]
            fn = micro_counts["false_negative"]
            micro_precision = tp / (tp + fp) if tp + fp else None
            micro_recall = tp / (tp + fn) if tp + fn else None
            micro_f1 = (
                2 * micro_precision * micro_recall / (micro_precision + micro_recall)
                if micro_precision is not None
                and micro_recall is not None
                and micro_precision + micro_recall
                else None
            )
            aggregates.append(
                {
                    "variant_id": variant.variant_id,
                    "model_label": model_label,
                    "model": model,
                    "completed_tasks": len(completed),
                    "planned_tasks": len(group_specs),
                    "invalid_output_rate": 1 - len(completed) / len(group_specs),
                    "duration_seconds": sum(
                        float(record["duration_seconds"]) for record in completed
                    ),
                    "part1_task_macro": {
                        name: _mean(metrics, "part1", name)
                        for name in ("precision", "recall", "f1")
                    },
                    "part2_mean_eligible_diff_coverage": _mean(
                        metrics, "part2", "eligible_diff_coverage"
                    ),
                    "part3_task_macro_criterion": {
                        name: _mean(metrics, "part3", "criterion_macro", name)
                        for name in ("precision", "recall", "f1")
                    },
                    "part3_task_macro_item": {
                        name: _mean(metrics, "part3", "item_macro", name)
                        for name in ("precision", "recall", "f1")
                    },
                    "part3_micro": {
                        **micro_counts,
                        "precision": micro_precision,
                        "recall": micro_recall,
                        "f1": micro_f1,
                    },
                    "visual_capture_count": sum(
                        sum(record["metrics"]["visual_captures"].values())
                        for record in completed
                    ),
                }
            )
    return aggregates


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.2f}%"


def _duration(value: float) -> str:
    minutes, seconds = divmod(round(value), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}"


def render_summary(
    plan: dict[str, Any],
    specs: list[RunSpec],
    runs: dict[str, dict[str, Any]],
) -> str:
    aggregates = aggregate_results(specs, runs)
    lines = [
        f"# Scope, visual, and model matrix: {plan['experiment_id']}",
        "",
        "Primary Part 3 metric: task-macro criterion P/R/F1. Part 2 coverage is a gold-free structural diagnostic, not semantic accuracy.",
        "",
        "| Variant | Model | Done | P1 P/R/F1 | P2 coverage | P3 criterion P/R/F1 | P3 item F1 | P3 micro F1 | Visual captures | Duration |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregates:
        p1 = row["part1_task_macro"]
        p3 = row["part3_task_macro_criterion"]
        lines.append(
            "| {variant} | {model} | {done}/{planned} | {p1p}/{p1r}/{p1f} | "
            "{p2} | {p3p}/{p3r}/{p3f} | {p3item} | {p3micro} | {captures} | {duration} |".format(
                variant=row["variant_id"],
                model=row["model_label"],
                done=row["completed_tasks"],
                planned=row["planned_tasks"],
                p1p=_percent(p1["precision"]),
                p1r=_percent(p1["recall"]),
                p1f=_percent(p1["f1"]),
                p2=_percent(row["part2_mean_eligible_diff_coverage"]),
                p3p=_percent(p3["precision"]),
                p3r=_percent(p3["recall"]),
                p3f=_percent(p3["f1"]),
                p3item=_percent(row["part3_task_macro_item"]["f1"]),
                p3micro=_percent(row["part3_micro"]["f1"]),
                captures=row["visual_capture_count"],
                duration=_duration(row["duration_seconds"]),
            )
        )

    lines.extend(
        [
            "",
            "## Per-task runs",
            "",
            "| # | Variant | Model | Task | Status | P1 F1 | P2 coverage | P3 criterion F1 | Captures | Duration |",
            "|---:|---|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for spec in specs:
        record = runs.get(spec.key, {})
        metrics = record.get("metrics", {})
        captures = sum(metrics.get("visual_captures", {}).values())
        lines.append(
            f"| {spec.ordinal} | {spec.variant_id} | {spec.model_label} | {spec.task} | "
            f"{record.get('status', 'pending')} | "
            f"{_percent(metrics.get('part1', {}).get('f1'))} | "
            f"{_percent(metrics.get('part2', {}).get('eligible_diff_coverage'))} | "
            f"{_percent(metrics.get('part3', {}).get('criterion_macro', {}).get('f1'))} | "
            f"{captures} | {_duration(float(record.get('duration_seconds', 0)))} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- Each cell is one stochastic run per example; use reruns before treating small differences as stable.",
            "- Part 2 has no gold labels. Coverage and structural checks do not establish semantic quality.",
            "- Visual capture count distinguishes tool availability from actual model use.",
            "- Generation completes before deterministic gold-backed evaluation.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_progress(
    experiment_dir: Path,
    plan: dict[str, Any],
    specs: list[RunSpec],
    results: dict[str, Any],
) -> None:
    results["updated_at"] = utc_now()
    results["aggregates"] = aggregate_results(specs, results["runs"])
    write_json(results, experiment_dir / "results.json")
    _atomic_text(
        experiment_dir / "summary.md",
        render_summary(plan, specs, results["runs"]),
    )


def _validate_resume_plan(
    plan: dict[str, Any], current: dict[str, Any]
) -> None:
    if plan.get("matrix_signature") != current.get("matrix_signature"):
        raise ValueError("Experiment matrix changed; start a new experiment directory")
    previous_source = plan.get("provenance", {}).get("source_snapshot")
    current_source = current.get("provenance", {}).get("source_snapshot")
    if previous_source != current_source:
        raise ValueError("Experiment source snapshot changed; start a new experiment directory")
    if plan.get("provenance", {}).get("input_sha256") != current.get("provenance", {}).get("input_sha256"):
        raise ValueError("Experiment input snapshot changed; start a new experiment directory")


def main() -> int:
    args = parse_args()
    if args.max_runs is not None and args.max_runs < 1:
        print("error: --max-runs must be a positive integer", file=sys.stderr)
        return 2
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY") and not args.dry_run:
        print("error: OPENAI_API_KEY is required", file=sys.stderr)
        return 2

    if args.experiment_dir:
        experiment_dir = args.experiment_dir.resolve()
        experiment_id = experiment_dir.name
    else:
        experiment_id = f"scope-visual-model-matrix-{utc_id()}"
        experiment_dir = args.experiments_root.resolve() / experiment_id

    plan = build_plan(experiment_id, experiment_dir)
    specs = build_run_specs(experiment_dir)
    try:
        selected_specs = select_run_specs(specs, args.run_keys)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    plan["selected_run_keys"] = [spec.key for spec in selected_specs]
    if args.dry_run:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    plan_path = experiment_dir / "plan.json"
    if plan_path.is_file():
        stored_plan = _load_json(plan_path)
        _validate_resume_plan(stored_plan, plan)
        plan = stored_plan
    else:
        experiment_dir.mkdir(parents=True, exist_ok=False)
        write_json(plan, plan_path)

    results_path = experiment_dir / "results.json"
    results = (
        _load_json(results_path)
        if results_path.is_file()
        else {
            "schema_version": 1,
            "experiment_id": experiment_id,
            "created_at": utc_now(),
            "runs": {},
        }
    )
    _write_progress(experiment_dir, plan, specs, results)

    failures = 0
    executed = 0
    for spec in selected_specs:
        previous = results["runs"].get(spec.key, {})
        if previous.get("status") == "completed":
            print(f"[{spec.ordinal:02d}/{len(specs)}] skipping completed {spec.key}")
            continue
        if args.max_runs is not None and executed >= args.max_runs:
            break

        attempt = int(previous.get("attempt", 0)) + 1
        executed += 1
        run_id = f"{experiment_id}-a{attempt}"
        started_at = utc_now()
        started = time.monotonic()
        results["runs"][spec.key] = {
            "status": "running",
            "attempt": attempt,
            "started_at": started_at,
        }
        _write_progress(experiment_dir, plan, specs, results)
        print(f"[{spec.ordinal:02d}/{len(specs)}] running {spec.key}", flush=True)

        try:
            with environment_override(spec.environment):
                run_dir = run_example(
                    "pipeline",
                    spec.task,
                    Path(spec.artifacts_root),
                    evaluate=True,
                    run_id=run_id,
                )
            duration = time.monotonic() - started
            results["runs"][spec.key] = {
                "status": "completed",
                "attempt": attempt,
                "started_at": started_at,
                "completed_at": utc_now(),
                "duration_seconds": duration,
                "run_dir": str(run_dir.relative_to(PROJECT_ROOT)),
                "manifest": str((run_dir / "manifest.json").relative_to(PROJECT_ROOT)),
                "metrics": collect_metrics(run_dir),
            }
            print(f"[{spec.ordinal:02d}/{len(specs)}] completed in {_duration(duration)}", flush=True)
        except KeyboardInterrupt:
            results["runs"][spec.key] = {
                "status": "interrupted",
                "attempt": attempt,
                "started_at": started_at,
                "completed_at": utc_now(),
                "duration_seconds": time.monotonic() - started,
            }
            _write_progress(experiment_dir, plan, specs, results)
            raise
        except Exception as exc:  # Preserve failure evidence and continue the matrix.
            failures += 1
            results["runs"][spec.key] = {
                "status": "failed",
                "attempt": attempt,
                "started_at": started_at,
                "completed_at": utc_now(),
                "duration_seconds": time.monotonic() - started,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            print(f"[{spec.ordinal:02d}/{len(specs)}] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            if args.stop_on_error:
                _write_progress(experiment_dir, plan, specs, results)
                return 1
        _write_progress(experiment_dir, plan, specs, results)

    print(f"Plan: {plan_path}")
    print(f"Results: {results_path}")
    print(f"Summary: {experiment_dir / 'summary.md'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
