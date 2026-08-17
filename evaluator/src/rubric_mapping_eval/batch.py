"""Manifest-driven batch evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    EvaluationError,
    average_scores,
    read_json,
    require_exact_keys,
    require_list,
    require_nonempty_string,
    require_object,
)
from .i2c_mapping import evaluate_i2c_files
from .sectioning import evaluate_section_files


def _resolve(base: Path, value: Any, context: str) -> Path:
    path_text = require_nonempty_string(value, context)
    path = Path(path_text)
    return path if path.is_absolute() else base / path


def evaluate_batch_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Evaluate every stage declared in a batch manifest.

    Paths inside the manifest are resolved relative to the manifest file.
    """

    manifest = Path(manifest_path)
    root = require_object(read_json(manifest), str(manifest))
    require_exact_keys(root, {"tasks"}, str(manifest))
    raw_tasks = require_list(root["tasks"], f"{manifest}.tasks")
    if not raw_tasks:
        raise EvaluationError(f"{manifest}.tasks must contain at least one task")

    task_results: dict[str, dict[str, Any]] = {}
    sectioning_results: list[dict[str, Any]] = []
    i2c_results: list[dict[str, Any]] = []
    base = manifest.parent

    for task_index, raw_task in enumerate(raw_tasks):
        task_context = f"{manifest}.tasks[{task_index}]"
        task = require_object(raw_task, task_context)
        allowed_keys = {"task_id", "sectioning", "i2c_mapping"}
        extra_keys = set(task) - allowed_keys
        missing_keys = {"task_id"} - set(task)
        if extra_keys or missing_keys:
            details: list[str] = []
            if missing_keys:
                details.append(f"missing {sorted(missing_keys)}")
            if extra_keys:
                details.append(f"unexpected {sorted(extra_keys)}")
            raise EvaluationError(f"{task_context} has invalid keys: {', '.join(details)}")
        if "sectioning" not in task and "i2c_mapping" not in task:
            raise EvaluationError(
                f"{task_context} must define sectioning, i2c_mapping, or both"
            )

        task_id = require_nonempty_string(task["task_id"], f"{task_context}.task_id")
        if task_id in task_results:
            raise EvaluationError(f"{manifest} contains duplicate task_id {task_id!r}")

        result: dict[str, Any] = {}
        if "sectioning" in task:
            config_context = f"{task_context}.sectioning"
            config = require_object(task["sectioning"], config_context)
            require_exact_keys(config, {"predicted", "gold"}, config_context)
            sectioning_result = evaluate_section_files(
                _resolve(base, config["predicted"], f"{config_context}.predicted"),
                _resolve(base, config["gold"], f"{config_context}.gold"),
            )
            result["sectioning"] = sectioning_result
            sectioning_results.append(sectioning_result)

        if "i2c_mapping" in task:
            config_context = f"{task_context}.i2c_mapping"
            config = require_object(task["i2c_mapping"], config_context)
            require_exact_keys(
                config, {"predicted", "gold", "rubric"}, config_context
            )
            i2c_result = evaluate_i2c_files(
                _resolve(base, config["predicted"], f"{config_context}.predicted"),
                _resolve(base, config["gold"], f"{config_context}.gold"),
                _resolve(base, config["rubric"], f"{config_context}.rubric"),
            )
            result["i2c_mapping"] = i2c_result
            i2c_results.append(i2c_result)

        task_results[task_id] = result

    summary: dict[str, Any] = {}
    if sectioning_results:
        summary["sectioning"] = {
            "task_count": len(sectioning_results),
            "macro_average": average_scores(
                (result["metrics"] for result in sectioning_results),
                context="batch sectioning macro average",
            ),
        }
    if i2c_results:
        summary["i2c_mapping"] = {
            "task_count": len(i2c_results),
            "criterion_macro_average": average_scores(
                (result["summary"]["criterion_macro"] for result in i2c_results),
                context="batch I2C criterion macro average",
            ),
            "item_macro_average": average_scores(
                (result["summary"]["item_macro"] for result in i2c_results),
                context="batch I2C item macro average",
            ),
            "mapped_item_fraction_average": sum(
                result["summary"]["mapped_item_fraction"] for result in i2c_results
            )
            / len(i2c_results),
        }

    return {"summary": summary, "tasks": task_results}
