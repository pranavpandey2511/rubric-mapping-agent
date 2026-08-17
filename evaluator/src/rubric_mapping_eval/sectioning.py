"""Sectioning evaluation based on cell-grouping relationships."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations_with_replacement
from pathlib import Path
from typing import Any, Iterable

from .common import (
    CellRef,
    EvaluationError,
    calculate_metrics,
    read_json,
    require_exact_keys,
    require_list,
    require_nonempty_string,
    require_object,
)


CellPair = tuple[CellRef, CellRef]


@dataclass(frozen=True, slots=True)
class Section:
    section_id: str
    sheet: str
    cells: tuple[CellRef, ...]


def parse_sections(
    payload: Any,
    *,
    context: str = "sections.json",
    allow_empty_sections: bool = False,
) -> tuple[Section, ...]:
    """Parse and strictly validate a sections.json payload."""

    root = require_object(payload, context)
    require_exact_keys(root, {"sections"}, context)
    raw_sections = require_list(root["sections"], f"{context}.sections")
    if not raw_sections and not allow_empty_sections:
        raise EvaluationError(f"{context}.sections must contain at least one section")

    seen_ids: set[str] = set()
    sections: list[Section] = []
    for section_index, raw_section in enumerate(raw_sections):
        section_context = f"{context}.sections[{section_index}]"
        section_object = require_object(raw_section, section_context)
        require_exact_keys(
            section_object, {"section_id", "sheet", "cells"}, section_context
        )
        section_id = require_nonempty_string(
            section_object["section_id"], f"{section_context}.section_id"
        )
        if section_id in seen_ids:
            raise EvaluationError(f"{context} contains duplicate section_id {section_id!r}")
        seen_ids.add(section_id)

        sheet = require_nonempty_string(section_object["sheet"], f"{section_context}.sheet")
        raw_cells = require_list(section_object["cells"], f"{section_context}.cells")
        if not raw_cells:
            raise EvaluationError(f"{section_context}.cells must not be empty")

        cells: list[CellRef] = []
        seen_cells: set[CellRef] = set()
        for cell_index, address in enumerate(raw_cells):
            cell = CellRef.create(
                sheet,
                address,
                f"{section_context}.cells[{cell_index}]",
            )
            if cell in seen_cells:
                raise EvaluationError(
                    f"{section_context}.cells contains duplicate address {cell.address!r}"
                )
            seen_cells.add(cell)
            cells.append(cell)

        sections.append(Section(section_id=section_id, sheet=sheet, cells=tuple(cells)))

    return tuple(sections)


def load_sections(
    path: str | Path, *, allow_empty_sections: bool = False
) -> tuple[Section, ...]:
    return parse_sections(
        read_json(path),
        context=str(path),
        allow_empty_sections=allow_empty_sections,
    )


def build_grouped_pairs(sections: Iterable[Section]) -> set[CellPair]:
    """Build canonical unordered cell pairs, including one self-pair per assigned cell.

    Pairs are deduplicated across overlapping sections. The function is intentionally
    public so callers can inspect the exact relationships being scored.
    """

    grouped_pairs: set[CellPair] = set()
    for section in sections:
        ordered_cells = sorted(section.cells)
        grouped_pairs.update(combinations_with_replacement(ordered_cells, 2))
    return grouped_pairs


def evaluate_sections(
    predicted_sections: Iterable[Section], gold_sections: Iterable[Section]
) -> dict[str, Any]:
    predicted_tuple = tuple(predicted_sections)
    gold_tuple = tuple(gold_sections)
    predicted_pairs = build_grouped_pairs(predicted_tuple)
    gold_pairs = build_grouped_pairs(gold_tuple)
    metrics = calculate_metrics(
        predicted_pairs, gold_pairs, context="sectioning grouped-pair evaluation"
    )
    return {
        "evaluation": "sectioning",
        "metrics": metrics.to_dict(),
        "section_counts": {
            "predicted": len(predicted_tuple),
            "gold": len(gold_tuple),
        },
    }


def evaluate_section_files(
    predicted_path: str | Path, gold_path: str | Path
) -> dict[str, Any]:
    """Load and evaluate a predicted and gold sections.json file."""

    return evaluate_sections(
        load_sections(predicted_path, allow_empty_sections=True),
        load_sections(gold_path),
    )
