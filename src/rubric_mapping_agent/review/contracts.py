"""Review-artifact models, parsers, and workbook-reference validation."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rubric_mapping_eval.common import (
    CellRef,
    EvaluationError,
    require_exact_keys,
    require_list,
    require_nonempty_string,
    require_object,
    validate_cell_address,
)
from rubric_mapping_eval.i2c_mapping import parse_rubric
from rubric_mapping_eval.sectioning import Section


@dataclass(frozen=True, slots=True)
class Subsection:
    subsection_id: str
    parent_section_id: str
    sheet: str
    cells: tuple[str, ...]
    roles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RubricItemDetail:
    criterion: str
    criterion_description: str
    condition: str


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Mapping artifact does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc


def parse_subsections(payload: Any, *, context: str) -> tuple[Subsection, ...]:
    root = require_object(payload, context)
    require_exact_keys(root, {"subsections"}, context)
    raw_subsections = require_list(root["subsections"], f"{context}.subsections")
    if not raw_subsections:
        raise EvaluationError(
            f"{context}.subsections must contain at least one subsection"
        )

    required = {"subsection_id", "parent_section_id", "sheet", "cells", "roles"}
    seen_ids: set[str] = set()
    subsections: list[Subsection] = []
    for index, raw_subsection in enumerate(raw_subsections):
        item_context = f"{context}.subsections[{index}]"
        subsection = require_object(raw_subsection, item_context)
        require_exact_keys(subsection, required, item_context)
        subsection_id = require_nonempty_string(
            subsection["subsection_id"], f"{item_context}.subsection_id"
        )
        if subsection_id in seen_ids:
            raise EvaluationError(
                f"{context} contains duplicate subsection_id {subsection_id!r}"
            )
        seen_ids.add(subsection_id)
        parent_section_id = require_nonempty_string(
            subsection["parent_section_id"], f"{item_context}.parent_section_id"
        )
        sheet = require_nonempty_string(
            subsection["sheet"], f"{item_context}.sheet"
        )

        raw_cells = require_list(subsection["cells"], f"{item_context}.cells")
        if not raw_cells:
            raise EvaluationError(f"{item_context}.cells must not be empty")
        cells = tuple(
            validate_cell_address(address, f"{item_context}.cells[{cell_index}]")
            for cell_index, address in enumerate(raw_cells)
        )
        if len(cells) != len(set(cells)):
            raise EvaluationError(f"{item_context}.cells contains duplicate addresses")

        raw_roles = require_list(subsection["roles"], f"{item_context}.roles")
        if not raw_roles:
            raise EvaluationError(f"{item_context}.roles must not be empty")
        roles = tuple(
            require_nonempty_string(role, f"{item_context}.roles[{role_index}]")
            for role_index, role in enumerate(raw_roles)
        )
        subsections.append(
            Subsection(
                subsection_id=subsection_id,
                parent_section_id=parent_section_id,
                sheet=sheet,
                cells=cells,
                roles=roles,
            )
        )
    return tuple(subsections)


def with_visual_subsection_coverage(
    sections: tuple[Section, ...],
    subsections: tuple[Subsection, ...],
) -> tuple[Subsection, ...]:
    """Add review-only coverage for Part 1 cells missing from Part 2."""

    covered_by_parent: dict[str, set[str]] = defaultdict(set)
    used_ids = {subsection.subsection_id for subsection in subsections}
    for subsection in subsections:
        covered_by_parent[subsection.parent_section_id].update(subsection.cells)

    completed = list(subsections)
    for section in sections:
        missing = tuple(
            cell.address
            for cell in section.cells
            if cell.address not in covered_by_parent[section.section_id]
        )
        if not missing:
            continue
        base_id = f"visual_{section.section_id}"
        subsection_id = base_id
        suffix = 2
        while subsection_id in used_ids:
            subsection_id = f"{base_id}_{suffix}"
            suffix += 1
        used_ids.add(subsection_id)
        completed.append(
            Subsection(
                subsection_id=subsection_id,
                parent_section_id=section.section_id,
                sheet=section.sheet,
                cells=missing,
                roles=("review-only-fallback",),
            )
        )
    return tuple(completed)


def rubric_details(payload: Any, *, context: str) -> dict[str, RubricItemDetail]:
    criteria = parse_rubric(payload, context=context)
    root = require_object(payload, context)
    raw_criteria = require_object(root["criteria"], f"{context}.criteria")
    details: dict[str, RubricItemDetail] = {}
    for criterion in criteria:
        raw_criterion = require_object(
            raw_criteria[criterion.key], f"{context}.criteria[{criterion.key!r}]"
        )
        description = str(raw_criterion.get("description", "")).strip()
        for raw_item in raw_criterion["grading"]:
            item_id = str(raw_item["item_id"])
            details[item_id] = RubricItemDetail(
                criterion=str(criterion.criterion_id),
                criterion_description=description,
                condition=str(raw_item.get("condition", "")).strip(),
            )
    return details


def validate_workbook_references(
    workbook,
    sections: tuple[Section, ...],
    subsections: tuple[Subsection, ...],
    items: dict[str, frozenset[CellRef]],
) -> None:
    sheet_names = set(workbook.sheetnames)
    missing = sorted(
        {
            *(section.sheet for section in sections if section.sheet not in sheet_names),
            *(
                subsection.sheet
                for subsection in subsections
                if subsection.sheet not in sheet_names
            ),
            *(
                cell.sheet
                for cells in items.values()
                for cell in cells
                if cell.sheet not in sheet_names
            ),
        }
    )
    if missing:
        raise ValueError(
            "Mapping artifacts reference missing worksheet(s): " + ", ".join(missing)
        )

    section_by_id = {section.section_id: section for section in sections}
    for subsection in subsections:
        parent = section_by_id.get(subsection.parent_section_id)
        if parent is None:
            raise ValueError(
                f"Subsection {subsection.subsection_id!r} references unknown parent "
                f"{subsection.parent_section_id!r}"
            )
        if parent.sheet != subsection.sheet:
            raise ValueError(
                f"Subsection {subsection.subsection_id!r} is not on its parent "
                "section's sheet"
            )
        parent_cells = {cell.address for cell in parent.cells}
        outside = sorted(set(subsection.cells) - parent_cells)
        if outside:
            raise ValueError(
                f"Subsection {subsection.subsection_id!r} contains cells outside "
                "its parent: " + ", ".join(outside[:10])
            )
