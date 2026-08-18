"""Orchestrate source-preserving annotated review workbook creation."""

from __future__ import annotations

from collections import defaultdict
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from openpyxl import load_workbook
from rubric_mapping_eval.i2c_mapping import parse_item_mapping
from rubric_mapping_eval.sectioning import parse_sections

from .contracts import (
    parse_subsections,
    read_json,
    rubric_details,
    validate_workbook_references,
    with_visual_subsection_coverage,
)
from .legend import add_legend
from .ooxml import restore_cell_payloads
from .overlays import (
    apply_item_highlights,
    apply_section_outlines,
    apply_subsection_underlines,
    color_map,
)


SUPPORTED_SUFFIXES = {".xlsx", ".xlsm"}


def create_review_workbook(
    workbook_path: str | Path,
    output_path: str | Path,
    *,
    sections_path: str | Path | None = None,
    subsections_path: str | Path | None = None,
    items_to_cells_path: str | Path | None = None,
    rubric_path: str | Path | None = None,
    include_legend: bool = True,
) -> Path:
    """Write an annotated workbook copy for supplied mapping artifacts.

    Part 1 cells receive a uniform region outline, Part 2 time-series cells
    receive row-level historical/projected bottom boundaries, and Part 3 cells
    receive a full-cell highlight plus one consolidated comment containing every
    mapped rubric item.
    """

    source = Path(workbook_path).resolve()
    destination = Path(output_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Workbook does not exist: {source}")
    if source.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("Review generation supports .xlsx and .xlsm workbooks")
    if destination.suffix.lower() != source.suffix.lower():
        raise ValueError(
            "Output workbook must use the same .xlsx or .xlsm suffix as the input"
        )
    if source == destination:
        raise ValueError("Output path must differ from the source workbook path")
    if not any((sections_path, subsections_path, items_to_cells_path)):
        raise ValueError("Supply at least one Part 1, Part 2, or Part 3 artifact")

    sections = (
        parse_sections(read_json(Path(sections_path)), context=str(sections_path))
        if sections_path is not None
        else ()
    )
    subsections = (
        parse_subsections(
            read_json(Path(subsections_path)), context=str(subsections_path)
        )
        if subsections_path is not None
        else ()
    )
    if subsections_path is not None and sections:
        subsections = with_visual_subsection_coverage(sections, subsections)
    items = (
        parse_item_mapping(
            read_json(Path(items_to_cells_path)),
            context=str(items_to_cells_path),
            allow_empty_cells=True,
        )
        if items_to_cells_path is not None
        else {}
    )
    details = (
        rubric_details(read_json(Path(rubric_path)), context=str(rubric_path))
        if rubric_path is not None
        else {}
    )
    if details and set(details) != set(items):
        missing = sorted(set(details) - set(items))
        unknown = sorted(set(items) - set(details))
        raise ValueError(
            "Part 3 item IDs do not match rubric.json"
            + (f"; missing: {missing}" if missing else "")
            + (f"; unknown: {unknown}" if unknown else "")
        )

    keep_vba = source.suffix.lower() == ".xlsm"
    workbook = load_workbook(
        source,
        data_only=False,
        read_only=False,
        keep_vba=keep_vba,
        keep_links=True,
    )
    temporary = destination.with_suffix(destination.suffix + f".{uuid4().hex}.tmp")
    try:
        validate_workbook_references(workbook, sections, subsections, items)
        subsection_colors = color_map(
            subsection.subsection_id for subsection in subsections
        )
        sections_by_cell: dict[tuple[str, str], list[str]] = defaultdict(list)
        for section in sections:
            for cell in section.cells:
                sections_by_cell[(section.sheet, cell.address)].append(
                    section.section_id
                )
        immutable_sections_by_cell = {
            key: tuple(value) for key, value in sections_by_cell.items()
        }
        sections_by_id = {section.section_id: section for section in sections}

        # Part 1 goes after Part 2 so the enclosing navy section frame remains
        # continuous where a row boundary meets the section's outer edge.
        apply_subsection_underlines(
            workbook,
            subsections,
            subsection_colors,
            sections_by_id,
        )
        apply_section_outlines(workbook, sections)
        apply_item_highlights(
            workbook,
            items,
            immutable_sections_by_cell,
            details,
        )
        if include_legend:
            add_legend(
                workbook,
                sections,
                subsections,
                items,
                subsection_colors,
                details,
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(temporary)
    finally:
        workbook.close()

    try:
        restore_cell_payloads(source, temporary)
        temporary.replace(destination)
    finally:
        with suppress(FileNotFoundError):
            temporary.unlink()
    return destination


# Compatibility name for callers of the original public API.
visualize_mapping_outputs = create_review_workbook
