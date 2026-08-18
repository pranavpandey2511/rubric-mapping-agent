#!/usr/bin/env python3
"""Run named Part 3 ablations against one frozen upstream bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rubric_mapping_agent.artifacts import write_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "ablations"
TASKS = ("keysight", "textron-1", "topbuild")

VARIANTS: dict[str, dict[str, str]] = {
    "p3-part1-only": {"RUBRIC_MAP_PART3_CONTEXT": "part1"},
    "p3-direct": {"RUBRIC_MAP_PART3_CONTEXT": "none"},
    "recommended": {"RUBRIC_MAP_PART3_CONTEXT": "part1_part2"},
}

CONFIG_DEFAULTS: dict[str, str] = {
    "OPENAI_MODEL": "openai:gpt-5.6-terra",
    "OPENAI_CODE_INTERPRETER_MEMORY": "4g",
    "RUBRIC_MAP_HANDOFF_JSON": "true",
    "RUBRIC_MAP_HANDOFF_SUMMARY": "true",
    "RUBRIC_MAP_PART3_SCOPE": "workbook",
    "RUBRIC_MAP_SHEET_MAX_WORKERS": "4",
    "RUBRIC_MAP_VISUAL_BACKEND": "off",
    "RUBRIC_MAP_VISUAL_WIDTH": "1440",
    "RUBRIC_MAP_VISUAL_HEIGHT": "900",
    "RUBRIC_MAP_VISUAL_TIMEOUT_SECONDS": "45.0",
    "RUBRIC_MAP_VISUAL_CAPTURE_DELAY_SECONDS": "0.6",
}

SOURCE_PATHS = {
    "input": Path("input.xlsx"),
    "complete": Path("complete.xlsx"),
    "instructions": Path("instructions.md"),
    "rubric": Path("rubric.json"),
}
UPSTREAM_PATHS = {
    "sections": Path("part1/sections.json"),
    "section_summary": Path("part1/summary.md"),
    "subsections": Path("part2/subsections.json"),
    "subsection_index": Path("part2/subsection_index.json"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one Part 3 context variant against frozen Part 1/2 outputs."
    )
    parser.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    parser.add_argument(
        "--upstream-root",
        required=True,
        type=Path,
        help=(
            "Frozen bundle root containing <task>/part1/{sections.json,summary.md} "
            "and <task>/part2/{subsections.json,subsection_index.json}."
        ),
    )
    parser.add_argument(
        "--task",
        action="append",
        choices=TASKS,
        dest="tasks",
        help="Run only this task; repeat to select multiple tasks.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Ablation output root (default: {DEFAULT_OUTPUT_ROOT}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Create a new run even when an identical completed run exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve inputs and print commands without writing or running them.",
    )
    return parser.parse_args()


def _require_files(paths: dict[str, Path], label: str) -> dict[str, Path]:
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing {label} file(s): " + ", ".join(map(str, missing))
        )
    return {name: path.resolve() for name, path in paths.items()}


def task_inputs(task: str, upstream_root: Path) -> dict[str, dict[str, Path]]:
    task_dir = PROJECT_ROOT / "examples" / "item-to-cell-mapping" / task
    sources = _require_files(
        {name: task_dir / relative for name, relative in SOURCE_PATHS.items()},
        "task",
    )
    upstream_dir = upstream_root.resolve() / task
    upstream = _require_files(
        {
            name: upstream_dir / relative
            for name, relative in UPSTREAM_PATHS.items()
        },
        "frozen upstream",
    )
    return {"sources": sources, "upstream": upstream}


def task_command(
    inputs: dict[str, dict[str, Path]],
    output: Path,
    context: str,
) -> list[str]:
    sources = inputs["sources"]
    upstream = inputs["upstream"]
    command = [
        sys.executable,
        "-m",
        "rubric_mapping_agent.workflow",
        "part3",
        "--input",
        str(sources["input"]),
        "--complete",
        str(sources["complete"]),
        "--instructions",
        str(sources["instructions"]),
        "--rubric",
        str(sources["rubric"]),
    ]
    if context != "none":
        command.extend(
            (
                "--sections",
                str(upstream["sections"]),
                "--section-summary",
                str(upstream["section_summary"]),
            )
        )
    if context == "part1_part2":
        command.extend(
            (
                "--subsections",
                str(upstream["subsections"]),
                "--subsection-index",
                str(upstream["subsection_index"]),
            )
        )
    command.extend(("--output", str(output)))
    return command


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _file_records(files: dict[str, Path]) -> dict[str, dict[str, str]]:
    return {
        name: {"path": str(path), "sha256": _sha256_file(path)}
        for name, path in sorted(files.items())
    }


def _implementation_hash() -> str:
    roots = (
        PROJECT_ROOT / "src" / "rubric_mapping_agent",
        PROJECT_ROOT / "skills" / "excel",
        PROJECT_ROOT / "skills" / "xlsx-rubric-mapping",
        PROJECT_ROOT / "pyproject.toml",
        PROJECT_ROOT / "uv.lock",
    )
    files = sorted(
        path
        for root in roots
        for path in ([root] if root.is_file() else root.rglob("*"))
        if path.is_file() and path.suffix != ".pyc"
    )
    if not files:
        raise FileNotFoundError("Part 3 implementation files are missing")
    records = {
        str(path.relative_to(PROJECT_ROOT)): _sha256_file(path) for path in files
    }
    return _sha256_json(records)


def effective_configuration(variant: dict[str, str]) -> dict[str, Any]:
    environment = {
        name: os.getenv(name, default) for name, default in CONFIG_DEFAULTS.items()
    }
    environment.update(variant)
    return {
        "environment": environment,
        "implementation_sha256": _implementation_hash(),
    }


def run_spec(
    variant_name: str,
    tasks: tuple[str, ...],
    configuration: dict[str, Any],
    inputs: dict[str, dict[str, dict[str, Path]]],
) -> dict[str, Any]:
    source_records = {
        task: _file_records(inputs[task]["sources"]) for task in tasks
    }
    upstream_records = {
        task: _file_records(inputs[task]["upstream"]) for task in tasks
    }
    return {
        "schema_version": 1,
        "variant": variant_name,
        "tasks": list(tasks),
        "configuration": configuration,
        "inputs": {
            "sources": source_records,
            "upstream": upstream_records,
        },
        "fingerprints": {
            "sources": _sha256_json(source_records),
            "upstream": _sha256_json(upstream_records),
            "configuration": _sha256_json(configuration),
        },
    }


def _valid_outputs(
    run_dir: Path,
    manifest: dict[str, Any],
    tasks: tuple[str, ...],
) -> bool:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != set(tasks):
        return False
    for task in tasks:
        record = outputs.get(task)
        if not isinstance(record, dict):
            return False
        relative = record.get("path")
        expected_hash = record.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            return False
        output = (run_dir / relative).resolve()
        if run_dir.resolve() not in output.parents or not output.is_file():
            return False
        if _sha256_file(output) != expected_hash:
            return False
    return True


def matching_run(variant_root: Path, spec: dict[str, Any]) -> Path | None:
    tasks = tuple(spec["tasks"])
    if not variant_root.is_dir():
        return None
    for run_dir in sorted(variant_root.iterdir(), reverse=True):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if all(
            manifest.get(name) == spec[name]
            for name in (
                "schema_version",
                "variant",
                "tasks",
                "configuration",
                "inputs",
                "fingerprints",
            )
        ) and _valid_outputs(run_dir, manifest, tasks):
            return run_dir
    return None


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def main() -> int:
    args = parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    variant = VARIANTS[args.variant]
    selected_tasks = set(args.tasks or TASKS)
    tasks = tuple(task for task in TASKS if task in selected_tasks)
    inputs = {task: task_inputs(task, args.upstream_root) for task in tasks}
    configuration = effective_configuration(variant)
    spec = run_spec(args.variant, tasks, configuration, inputs)
    variant_root = args.output_root.resolve() / args.variant

    if not args.force:
        existing = matching_run(variant_root, spec)
        if existing is not None:
            print(f"Reusing completed run: {existing}")
            return 0

    run_id = _run_id()
    run_dir = variant_root / run_id
    child_environment = os.environ.copy()
    child_environment.update(configuration["environment"])
    context = variant["RUBRIC_MAP_PART3_CONTEXT"]
    outputs: dict[str, Path] = {}

    print(f"Variant: {args.variant}")
    print(f"Frozen upstream: {spec['fingerprints']['upstream']}")
    if not args.dry_run:
        run_dir.mkdir(parents=True, exist_ok=False)
    for task in tasks:
        output = run_dir / task / "part3" / "items_to_cells.json"
        outputs[task] = output
        command = task_command(inputs[task], output, context)
        print(f"Running {task}: {' '.join(command)}")
        if args.dry_run:
            continue
        output.parent.mkdir(parents=True)
        subprocess.run(command, cwd=PROJECT_ROOT, env=child_environment, check=True)
        if not output.is_file():
            raise RuntimeError(f"Part 3 did not create expected output: {output}")

    if args.dry_run:
        return 0

    manifest = {
        **spec,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "outputs": {
            task: {
                "path": str(output.relative_to(run_dir)),
                "sha256": _sha256_file(output),
            }
            for task, output in outputs.items()
        },
    }
    write_json(manifest, run_dir / "manifest.json")
    print(f"Completed run: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
