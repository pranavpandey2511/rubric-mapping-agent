"""Standalone Part 1-3 functions, full pipeline, and minimal CLI."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

from rubric_mapping_eval.i2c_mapping import parse_rubric
from rubric_mapping_eval.sectioning import parse_sections

from .artifacts import write_json as _write_json
from .artifacts import write_text as _write_text
from .configuration import (
    environment_choice as _environment_choice,
    part3_context as _part3_context,
    sheet_max_workers as _sheet_max_workers,
    stage_scope as _stage_scope,
)
from .handoff import (
    HandoffPolicy,
    validate_section_summary,
)
from .retrieval_index import validate_subsection_index
from .runtime.stage import _invoke_stage, _stage_prompt
from .stage_outputs import (
    build_part2_artifacts as _build_part2_artifacts,
    combine_part1_artifacts as _combine_part1_artifacts,
    combine_part2_artifacts as _combine_part2_artifacts,
    combine_part3_artifacts as _combine_part3_artifacts,
    eligible_diff_cells as _eligible_diff_cells,
    require_files as _require_files,
    validate_part3_artifact as _validate_part3_artifact,
    validate_subsections as _validate_subsections,
    workbook_sheet_names as _workbook_sheet_names,
)


def _invoke_sheets_in_parallel(
    stage: str,
    sheet_names: Iterable[str],
    sources: dict[str, Path],
    *,
    visual_artifacts_dir: Path | None = None,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    """Run isolated worksheet invocations concurrently and return workbook order."""

    ordered_sheets = tuple(sheet_names)
    if not ordered_sheets:
        return ()
    worker_count = min(len(ordered_sheets), _sheet_max_workers())
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix=f"rubric-map-{stage}",
    ) as executor:
        futures = {
            executor.submit(
                _invoke_stage,
                stage,
                sources,
                target_sheet=sheet_name,
                visual_artifacts_dir=visual_artifacts_dir,
            ): sheet_name
            for sheet_name in ordered_sheets
        }
        try:
            for future in as_completed(futures):
                sheet_name = futures[future]
                results[sheet_name] = future.result()
        except BaseException as exc:
            for future in futures:
                future.cancel()
            if hasattr(exc, "add_note"):
                exc.add_note(f"{stage} worksheet invocation failed for {sheet_name!r}")
            raise
    return tuple((sheet_name, results[sheet_name]) for sheet_name in ordered_sheets)


def create_overall_section(
    input_path: str | Path,
    complete_path: str | Path,
    instructions_path: str | Path,
    *,
    output_path: str | Path = "sections.json",
    summary_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create Part 1 sections and their human-readable semantic summary."""

    sections_output = Path(output_path).resolve()
    summary_output = (
        Path(summary_output_path).resolve()
        if summary_output_path is not None
        else sections_output.with_name("summary.md")
    )
    if sections_output == summary_output:
        raise ValueError("Part 1 sections and summary outputs must be different files")
    sources = {
        "input": Path(input_path).resolve(),
        "complete": Path(complete_path).resolve(),
        "instructions": Path(instructions_path).resolve(),
    }
    _require_files(sources.values())
    scope = _stage_scope("part1")
    visual_artifacts_dir = sections_output.parent / "visual-inspection"
    sheet_names = _workbook_sheet_names(sources["input"], sources["complete"])
    scoped_artifacts: Iterable[tuple[str | None, dict[str, Any]]]
    if scope == "sheet":
        scoped_artifacts = _invoke_sheets_in_parallel(
            "part1",
            sheet_names,
            sources,
            visual_artifacts_dir=visual_artifacts_dir,
        )
    else:
        scoped_artifacts = (
            (
                None,
                _invoke_stage(
                    "part1",
                    sources,
                    visual_artifacts_dir=visual_artifacts_dir,
                ),
            ),
        )
    artifact, summary = _combine_part1_artifacts(
        scoped_artifacts,
        allowed_sheets=set(sheet_names),
    )
    parse_sections(artifact)
    _write_text(summary, summary_output)
    _write_json(artifact, sections_output)
    return artifact


def create_intermediate_sections(
    input_path: str | Path,
    complete_path: str | Path,
    instructions_path: str | Path,
    sections_path: str | Path,
    section_summary_path: str | Path | None = None,
    *,
    output_path: str | Path = "subsections.json",
    index_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create Part 2 subsections and an agent-authored semantic index."""

    sections_file = Path(sections_path).resolve()
    section_summary_file = (
        Path(section_summary_path).resolve()
        if section_summary_path is not None
        else sections_file.with_name("summary.md")
    )
    subsections_output = Path(output_path).resolve()
    index_output = (
        Path(index_output_path).resolve()
        if index_output_path is not None
        else subsections_output.with_name("subsection_index.json")
    )
    if subsections_output == index_output:
        raise ValueError("Part 2 subsections and index outputs must be different files")
    if section_summary_file == index_output:
        raise ValueError("Part 2 index output must not overwrite the Part 1 summary")
    required_sources = {
        "input": Path(input_path).resolve(),
        "complete": Path(complete_path).resolve(),
        "instructions": Path(instructions_path).resolve(),
        "sections": sections_file,
        "section_summary": section_summary_file,
    }
    _require_files(required_sources.values())
    sections_payload = json.loads(sections_file.read_text(encoding="utf-8"))
    sections = parse_sections(sections_payload)
    validate_section_summary(
        section_summary_file.read_text(encoding="utf-8"),
        sections_payload["sections"],
    )

    policy = HandoffPolicy.from_environment()
    policy.require_part2_context()
    eligible = _eligible_diff_cells(
        required_sources["input"], required_sources["complete"]
    )
    sources = {
        key: required_sources[key] for key in ("input", "complete", "instructions")
    }
    if policy.include_json:
        sources["sections"] = sections_file
    if policy.include_summary:
        sources["section_summary"] = section_summary_file

    scope = _stage_scope("part2")
    visual_artifacts_dir = subsections_output.parent / "visual-inspection"
    if scope == "sheet":
        workbook_sheets = _workbook_sheet_names(
            required_sources["input"], required_sources["complete"]
        )
        represented_sheets = {section.sheet for section in sections}
        unknown_sheets = sorted(represented_sheets - set(workbook_sheets))
        if unknown_sheets:
            raise ValueError(
                f"Part 1 contains unknown worksheets: {unknown_sheets}"
            )
        target_sheets = tuple(
            sheet_name
            for sheet_name in workbook_sheets
            if sheet_name in represented_sheets
        )
        sheet_artifacts = _invoke_sheets_in_parallel(
            "part2",
            target_sheets,
            sources,
            visual_artifacts_dir=visual_artifacts_dir,
        )
        artifact, index_payload = _combine_part2_artifacts(
            sheet_artifacts, sections_file, eligible
        )
    else:
        hosted_artifact = _invoke_stage(
            "part2",
            sources,
            visual_artifacts_dir=visual_artifacts_dir,
        )
        artifact, index_payload = _build_part2_artifacts(
            hosted_artifact, sections_file, eligible
        )
    _write_json(index_payload, index_output)
    _write_json(artifact, subsections_output)
    return artifact


def create_items_to_cells_mapping(
    input_path: str | Path,
    complete_path: str | Path,
    instructions_path: str | Path,
    rubric_path: str | Path,
    *,
    sections_path: str | Path | None = None,
    section_summary_path: str | Path | None = None,
    subsections_path: str | Path | None = None,
    subsection_index_path: str | Path | None = None,
    output_path: str | Path = "items_to_cells.json",
) -> dict[str, Any]:
    """Create the assignment-required Part 3 artifact."""

    input_file = Path(input_path).resolve()
    complete_file = Path(complete_path).resolve()
    rubric_file = Path(rubric_path).resolve()
    policy = HandoffPolicy.from_environment()
    required_sources = {
        "input": input_file,
        "complete": complete_file,
        "instructions": Path(instructions_path).resolve(),
        "rubric": rubric_file,
    }
    sections_file = Path(sections_path).resolve() if sections_path is not None else None
    section_summary_file = (
        Path(section_summary_path).resolve()
        if section_summary_path is not None
        else (
            sections_file.with_name("summary.md")
            if sections_file is not None and policy.include_summary
            else None
        )
    )
    subsections_file = (
        Path(subsections_path).resolve() if subsections_path is not None else None
    )
    subsection_index_file = (
        Path(subsection_index_path).resolve()
        if subsection_index_path is not None
        else (
            subsections_file.with_name("subsection_index.json")
            if subsections_file is not None and policy.include_json
            else None
        )
    )
    if sections_path is not None:
        required_sources["sections"] = sections_file
    if subsections_path is not None:
        if sections_path is None:
            raise ValueError("subsections_path requires sections_path")
        required_sources["subsections"] = subsections_file
    if section_summary_file is not None:
        if sections_file is None:
            raise ValueError("section_summary_path requires sections_path")
        required_sources["section_summary"] = section_summary_file
    if subsection_index_file is not None:
        if subsections_file is None:
            raise ValueError("subsection_index_path requires subsections_path")
        required_sources["subsection_index"] = subsection_index_file

    _require_files(required_sources.values())
    eligible = _eligible_diff_cells(input_file, complete_file)
    criteria = parse_rubric(json.loads(rubric_file.read_text(encoding="utf-8")))
    expected_item_ids = tuple(
        item_id for criterion in criteria for item_id in criterion.item_ids
    )
    sections_payload = None
    subsections_payload = None
    if sections_file is not None:
        sections_payload = json.loads(sections_file.read_text(encoding="utf-8"))
        parse_sections(sections_payload)
    if subsections_file is not None:
        subsections_payload = json.loads(subsections_file.read_text(encoding="utf-8"))
        _validate_subsections(
            subsections_payload,
            sections_file,
        )
    if section_summary_file is not None and sections_payload is not None:
        validate_section_summary(
            section_summary_file.read_text(encoding="utf-8"),
            sections_payload["sections"],
        )
    if subsection_index_file is not None and subsections_payload is not None:
        subsection_index_payload = json.loads(
            subsection_index_file.read_text(encoding="utf-8")
        )
        validate_subsection_index(
            subsection_index_payload,
            subsections=subsections_payload["subsections"],
            eligible=eligible,
        )

    sources = {
        key: required_sources[key]
        for key in ("input", "complete", "instructions", "rubric")
    }
    if policy.include_json:
        if sections_file is not None:
            sources["sections"] = sections_file
        if subsections_file is not None:
            sources["subsections"] = subsections_file
        if subsection_index_file is not None:
            sources["subsection_index"] = subsection_index_file
    if policy.include_summary and section_summary_file is not None:
        sources["section_summary"] = section_summary_file

    scope = _stage_scope("part3")
    items_output = Path(output_path).resolve()
    visual_artifacts_dir = items_output.parent / "visual-inspection"
    if scope == "sheet":
        sheet_names = _workbook_sheet_names(input_file, complete_file)
        sheet_artifacts = _invoke_sheets_in_parallel(
            "part3",
            sheet_names,
            sources,
            visual_artifacts_dir=visual_artifacts_dir,
        )
        artifact = _combine_part3_artifacts(
            sheet_artifacts,
            expected_item_ids=expected_item_ids,
            eligible=eligible,
            workbook_sheet_order=sheet_names,
        )
    else:
        artifact = _invoke_stage(
            "part3",
            sources,
            visual_artifacts_dir=visual_artifacts_dir,
        )
        _validate_part3_artifact(
            artifact,
            expected_item_ids=expected_item_ids,
            eligible=eligible,
        )

    _write_json(artifact, items_output)
    return artifact


def run_complete_workflow(
    input_path: str | Path,
    complete_path: str | Path,
    instructions_path: str | Path,
    rubric_path: str | Path,
    *,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Run the configured Part 1-3 workflow as isolated agent invocations."""

    output = Path(output_dir).resolve()
    sections = output / "part1" / "sections.json"
    section_summary = output / "part1" / "summary.md"
    subsections = output / "part2" / "subsections.json"
    subsection_index = output / "part2" / "subsection_index.json"
    items = output / "part3" / "items_to_cells.json"
    context = _part3_context()
    create_overall_section(
        input_path,
        complete_path,
        instructions_path,
        output_path=sections,
        summary_output_path=section_summary,
    )
    if context == "part1_part2":
        create_intermediate_sections(
            input_path,
            complete_path,
            instructions_path,
            sections,
            section_summary,
            output_path=subsections,
            index_output_path=subsection_index,
        )
    create_items_to_cells_mapping(
        input_path,
        complete_path,
        instructions_path,
        rubric_path,
        sections_path=sections if context != "none" else None,
        section_summary_path=section_summary if context != "none" else None,
        subsections_path=subsections if context == "part1_part2" else None,
        subsection_index_path=(
            subsection_index if context == "part1_part2" else None
        ),
        output_path=items,
    )
    outputs = {
        "sections": sections,
        "section_summary": section_summary,
        "items_to_cells": items,
    }
    if context == "part1_part2":
        outputs["subsections"] = subsections
        outputs["subsection_index"] = subsection_index
    return outputs


def main() -> int:
    """Preserve module-based CLI invocation."""

    from .cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
