"""Lineage lookup and evaluation for managed example runs."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from rubric_mapping_eval.i2c_mapping import evaluate_i2c_files
from rubric_mapping_eval.sectioning import evaluate_section_files

from .artifacts import write_json
from .retrieval_index import PART2_ROLES
from .stage_outputs import eligible_diff_cells, validate_subsections


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = PROJECT_ROOT / "examples" / "item-to-cell-mapping"
EVALUATION_OUTPUTS = {
    "part1": Path("part1/evaluation.json"),
    "part2": Path("part2/evaluation.json"),
    "part3": Path("part3/evaluation.json"),
}
def gold_sections_path(task_dir: Path) -> Path:
    """Locate Part 1 labels without borrowing gold from an unrelated task."""

    direct = task_dir / "sections.json"
    if direct.is_file() or task_dir.parent.resolve() != EXAMPLES_ROOT.resolve():
        return direct
    return PROJECT_ROOT / "examples" / "sectioning" / task_dir.name / "sections.json"


def manifest_path(run_dir: Path) -> Path:
    return run_dir / "manifest.json"


def _load_manifest(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _manifest_artifact(
    path: Path,
    manifest: dict[str, Any],
    group: str,
    stage: str,
) -> Path | None:
    values = manifest.get(group)
    if not isinstance(values, dict):
        return None
    value = values.get(stage)
    if not isinstance(value, str):
        return None
    artifact = (path.parent / value).resolve()
    return artifact if artifact.is_file() else None


def latest_part1_bundle(example_root: Path) -> tuple[Path, Path]:
    """Return sections and summary from the newest complete Part 1 run."""

    for path in sorted(example_root.glob("*/manifest.json"), reverse=True):
        manifest = _load_manifest(path)
        if manifest is None:
            continue
        sections = _manifest_artifact(path, manifest, "outputs", "part1")
        summary = _manifest_artifact(path, manifest, "outputs", "part1_summary")
        if sections is not None and summary is not None:
            return sections, summary
    raise FileNotFoundError(
        f"No successful Part 1 sections/summary bundle exists under {example_root}."
    )


def upstream_for_part3(example_root: Path) -> tuple[Path, Path, Path, Path]:
    """Return the newest complete Part 2 bundle and its exact Part 1 lineage."""

    for path in sorted(example_root.glob("*/manifest.json"), reverse=True):
        manifest = _load_manifest(path)
        if manifest is None:
            continue
        part2 = _manifest_artifact(path, manifest, "outputs", "part2")
        part2_index = _manifest_artifact(
            path, manifest, "outputs", "subsection_index"
        )
        part1 = _manifest_artifact(path, manifest, "outputs", "part1")
        part1_summary = _manifest_artifact(
            path, manifest, "outputs", "part1_summary"
        )
        if part1 is None:
            part1 = _manifest_artifact(path, manifest, "upstream", "part1")
        if part1_summary is None:
            part1_summary = _manifest_artifact(
                path, manifest, "upstream", "part1_summary"
            )
        if all(
            artifact is not None
            for artifact in (part1, part1_summary, part2, part2_index)
        ):
            return part1, part1_summary, part2, part2_index
    raise FileNotFoundError(
        f"No complete Part 1 plus Part 2 lineage exists under {example_root}."
    )


def write_manifest(run_dir: Path, payload: dict[str, Any]) -> None:
    write_json(payload, manifest_path(run_dir))


def evaluate_part2(
    subsections_path: Path,
    sections_path: Path,
    input_path: Path,
    complete_path: Path,
) -> dict[str, Any]:
    """Return gold-free structural diagnostics for the internal Part 2 handoff."""

    payload = json.loads(subsections_path.read_text(encoding="utf-8"))
    validate_subsections(payload, sections_path)
    subsections = payload["subsections"]
    eligible = eligible_diff_cells(input_path, complete_path)
    memberships = Counter(
        (subsection["sheet"], address)
        for subsection in subsections
        for address in subsection["cells"]
    )
    assigned = set(memberships)
    covered = assigned & eligible
    role_counts = Counter(
        role for subsection in subsections for role in subsection["roles"]
    )
    unknown_roles = sorted(set(role_counts) - PART2_ROLES)
    contradictory_period_subsections = sum(
        {"historical", "projected"}.issubset(subsection["roles"])
        for subsection in subsections
    )
    eligible_count = len(eligible)
    return {
        "evaluation": "part2_structural_diagnostics",
        "gold_backed": False,
        "checks": {
            "schema_valid": True,
            "part1_lineage_valid": True,
        },
        "limitations": (
            "The assignment supplies no gold subsections.json. These diagnostics "
            "measure structural validity and retrieval coverage, not semantic "
            "accuracy or downstream Part 3 improvement."
        ),
        "metrics": {
            "subsection_count": len(subsections),
            "parent_section_count": len(
                {subsection["parent_section_id"] for subsection in subsections}
            ),
            "assigned_cell_occurrences": sum(memberships.values()),
            "unique_assigned_cells": len(assigned),
            "overlapping_cell_count": sum(count > 1 for count in memberships.values()),
            "eligible_diff_cells": eligible_count,
            "covered_eligible_diff_cells": len(covered),
            "eligible_diff_coverage": (
                len(covered) / eligible_count if eligible_count else 1.0
            ),
            "assigned_cells_outside_eligible_diff": len(assigned - eligible),
            "contradictory_period_subsections": contradictory_period_subsections,
            "unknown_roles": unknown_roles,
            "role_counts": dict(sorted(role_counts.items())),
        },
    }


def evaluate_outputs(
    stage: str,
    example_dir: Path,
    run_dir: Path,
    outputs: dict[str, Path],
    upstream: dict[str, Path],
    runtime_by_stage: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Path]:
    """Evaluate only outputs produced by this completed invocation."""

    selected_stages = (
        tuple(name for name in ("part1", "part2", "part3") if name in outputs)
        if stage == "pipeline"
        else (stage,)
    )
    reports: dict[str, Path] = {}
    evaluator = {
        "package": "rubric-mapping-eval",
        "version": version("rubric-mapping-eval"),
    }
    for selected_stage in selected_stages:
        report_path = run_dir / EVALUATION_OUTPUTS[selected_stage]
        if selected_stage == "part1":
            result = evaluate_section_files(
                outputs["part1"],
                gold_sections_path(example_dir),
            )
            payload = {"evaluator": evaluator, "result": result}
        elif selected_stage == "part2":
            sections_path = outputs.get("part1", upstream.get("part1"))
            if sections_path is None:
                raise ValueError("Part 2 evaluation requires its Part 1 lineage")
            payload = {
                "evaluator": {
                    "package": "rubric-mapping-agent",
                    "version": version("rubric-mapping-agent"),
                },
                "result": evaluate_part2(
                    outputs["part2"],
                    sections_path,
                    example_dir / "input.xlsx",
                    example_dir / "complete.xlsx",
                ),
            }
        else:
            result = evaluate_i2c_files(
                outputs["part3"],
                example_dir / "items_to_cells.json",
                example_dir / "rubric.json",
            )
            payload = {"evaluator": evaluator, "result": result}
        if runtime_by_stage is not None and selected_stage in runtime_by_stage:
            payload["runtime"] = runtime_by_stage[selected_stage]
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(payload, report_path)
        reports[selected_stage] = report_path
        print(f"Evaluation {selected_stage}: {report_path}")
    return reports


def evaluation_summary(report_path: Path) -> dict[str, Any]:
    """Return the compact metrics needed by run and assignment-level reports."""

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError(f"Evaluation report has no result object: {report_path}")
    evaluation = result.get("evaluation")
    if evaluation == "sectioning":
        return {
            "evaluation": evaluation,
            "gold_backed": True,
            "metrics": result["metrics"],
            "section_counts": result.get("section_counts"),
        }
    if evaluation == "part2_structural_diagnostics":
        return {
            "evaluation": evaluation,
            "gold_backed": False,
            "metrics": result["metrics"],
            "limitations": result.get("limitations"),
        }
    if evaluation == "i2c_mapping":
        summary = result["summary"]
        return {
            "evaluation": evaluation,
            "gold_backed": True,
            "metrics": summary["criterion_macro"],
            "item_macro": summary.get("item_macro"),
            "mapped_item_fraction": summary.get("mapped_item_fraction"),
            "mapped_items": summary.get("mapped_items"),
            "total_items": summary.get("total_items"),
        }
    raise ValueError(f"Unknown evaluation type {evaluation!r} in {report_path}")
