"""I2C mapping evaluation with per-item and per-criterion aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import (
    CellRef,
    EvaluationError,
    average_scores,
    calculate_metrics,
    read_json,
    require_exact_keys,
    require_list,
    require_nonempty_string,
    require_object,
)


@dataclass(frozen=True, slots=True)
class Criterion:
    key: str
    criterion_id: int | str
    item_ids: tuple[str, ...]


def parse_item_mapping(
    payload: Any,
    *,
    context: str = "items_to_cells.json",
    allow_empty_cells: bool,
) -> dict[str, frozenset[CellRef]]:
    """Parse and strictly validate an items_to_cells.json payload."""

    root = require_object(payload, context)
    require_exact_keys(root, {"items"}, context)
    raw_items = require_list(root["items"], f"{context}.items")
    if not raw_items:
        raise EvaluationError(f"{context}.items must contain at least one item")

    items: dict[str, frozenset[CellRef]] = {}
    for item_index, raw_item in enumerate(raw_items):
        item_context = f"{context}.items[{item_index}]"
        item_object = require_object(raw_item, item_context)
        require_exact_keys(item_object, {"item_id", "cells"}, item_context)
        item_id = require_nonempty_string(item_object["item_id"], f"{item_context}.item_id")
        if item_id in items:
            raise EvaluationError(f"{context} contains duplicate item_id {item_id!r}")

        raw_cells = require_list(item_object["cells"], f"{item_context}.cells")
        if not raw_cells and not allow_empty_cells:
            raise EvaluationError(f"{item_context}.cells must not be empty in gold data")

        cells: set[CellRef] = set()
        for cell_index, raw_cell in enumerate(raw_cells):
            cell_context = f"{item_context}.cells[{cell_index}]"
            cell_object = require_object(raw_cell, cell_context)
            require_exact_keys(cell_object, {"sheet", "address"}, cell_context)
            cell = CellRef.create(
                cell_object["sheet"], cell_object["address"], cell_context
            )
            if cell in cells:
                raise EvaluationError(
                    f"{item_context}.cells contains duplicate cell "
                    f"{cell.sheet!r}!{cell.address}"
                )
            cells.add(cell)
        items[item_id] = frozenset(cells)

    return items


def parse_rubric(payload: Any, *, context: str = "rubric.json") -> tuple[Criterion, ...]:
    """Read the criterion-to-item structure needed for aggregation."""

    root = require_object(payload, context)
    if "criteria" not in root:
        raise EvaluationError(f"{context} is missing required key 'criteria'")
    raw_criteria = require_object(root["criteria"], f"{context}.criteria")
    if not raw_criteria:
        raise EvaluationError(f"{context}.criteria must not be empty")

    criteria: list[Criterion] = []
    seen_item_ids: set[str] = set()
    seen_criterion_ids: set[int | str] = set()
    for criterion_key, raw_criterion in raw_criteria.items():
        criterion_context = f"{context}.criteria[{criterion_key!r}]"
        require_nonempty_string(criterion_key, f"{criterion_context}.key")
        criterion_object = require_object(raw_criterion, criterion_context)
        for required_key in ("criterion_id", "grading"):
            if required_key not in criterion_object:
                raise EvaluationError(
                    f"{criterion_context} is missing required key {required_key!r}"
                )

        criterion_id = criterion_object["criterion_id"]
        if isinstance(criterion_id, bool) or not isinstance(criterion_id, (int, str)):
            raise EvaluationError(
                f"{criterion_context}.criterion_id must be an integer or string"
            )
        if isinstance(criterion_id, str) and criterion_id == "":
            raise EvaluationError(f"{criterion_context}.criterion_id must not be empty")
        if criterion_id in seen_criterion_ids:
            raise EvaluationError(f"{context} contains duplicate criterion_id {criterion_id!r}")
        seen_criterion_ids.add(criterion_id)

        raw_grading = require_list(
            criterion_object["grading"], f"{criterion_context}.grading"
        )
        if not raw_grading:
            raise EvaluationError(f"{criterion_context}.grading must not be empty")

        item_ids: list[str] = []
        for item_index, raw_item in enumerate(raw_grading):
            item_context = f"{criterion_context}.grading[{item_index}]"
            item_object = require_object(raw_item, item_context)
            if "item_id" not in item_object:
                raise EvaluationError(f"{item_context} is missing required key 'item_id'")
            item_id = require_nonempty_string(item_object["item_id"], f"{item_context}.item_id")
            if item_id in seen_item_ids:
                raise EvaluationError(f"{context} contains duplicate rubric item_id {item_id!r}")
            seen_item_ids.add(item_id)
            item_ids.append(item_id)

        criteria.append(
            Criterion(
                key=criterion_key,
                criterion_id=criterion_id,
                item_ids=tuple(item_ids),
            )
        )

    return tuple(criteria)


def _validate_item_ids(
    actual: Mapping[str, frozenset[CellRef]], expected: set[str], *, context: str
) -> None:
    actual_ids = set(actual)
    if actual_ids == expected:
        return
    missing = sorted(expected - actual_ids)
    unknown = sorted(actual_ids - expected)
    details: list[str] = []
    if missing:
        details.append(f"missing item_ids {missing}")
    if unknown:
        details.append(f"unknown item_ids {unknown}")
    raise EvaluationError(f"{context} does not match rubric: {', '.join(details)}")


def evaluate_item_mappings(
    predicted_items: Mapping[str, frozenset[CellRef]],
    gold_items: Mapping[str, frozenset[CellRef]],
    criteria: Iterable[Criterion],
) -> dict[str, Any]:
    criteria_tuple = tuple(criteria)
    expected_item_ids = {item_id for criterion in criteria_tuple for item_id in criterion.item_ids}
    _validate_item_ids(predicted_items, expected_item_ids, context="predicted mapping")
    _validate_item_ids(gold_items, expected_item_ids, context="gold mapping")

    item_results: dict[str, dict[str, Any]] = {}
    for item_id in sorted(expected_item_ids):
        item_results[item_id] = calculate_metrics(
            set(predicted_items[item_id]),
            set(gold_items[item_id]),
            context=f"item {item_id!r}",
        ).to_dict()

    criterion_results: dict[str, dict[str, Any]] = {}
    for criterion in criteria_tuple:
        criterion_score = average_scores(
            (
                {
                    "precision": item_results[item_id]["precision"],
                    "recall": item_results[item_id]["recall"],
                    "f1": item_results[item_id]["f1"],
                }
                for item_id in criterion.item_ids
            ),
            context=f"criterion {criterion.key!r}",
        )
        criterion_results[criterion.key] = {
            "criterion_id": criterion.criterion_id,
            "item_ids": list(criterion.item_ids),
            "metrics": criterion_score,
        }

    criterion_macro = average_scores(
        (result["metrics"] for result in criterion_results.values()),
        context="criterion macro average",
    )
    item_macro = average_scores(
        (
            {
                "precision": result["precision"],
                "recall": result["recall"],
                "f1": result["f1"],
            }
            for result in item_results.values()
        ),
        context="item macro average",
    )
    mapped_count = sum(bool(cells) for cells in predicted_items.values())

    return {
        "evaluation": "i2c_mapping",
        "summary": {
            "criterion_macro": criterion_macro,
            "item_macro": item_macro,
            "mapped_items": mapped_count,
            "total_items": len(expected_item_ids),
            "mapped_item_fraction": mapped_count / len(expected_item_ids),
        },
        "criteria": criterion_results,
        "items": item_results,
    }


def evaluate_i2c_files(
    predicted_path: str | Path,
    gold_path: str | Path,
    rubric_path: str | Path,
) -> dict[str, Any]:
    """Load and evaluate predicted/gold mappings using rubric criterion membership."""

    predicted_items = parse_item_mapping(
        read_json(predicted_path), context=str(predicted_path), allow_empty_cells=True
    )
    gold_items = parse_item_mapping(
        read_json(gold_path), context=str(gold_path), allow_empty_cells=False
    )
    criteria = parse_rubric(read_json(rubric_path), context=str(rubric_path))
    return evaluate_item_mappings(predicted_items, gold_items, criteria)
