"""Command-line interface for the checkout workflow."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .workflow import (
    create_intermediate_sections,
    create_items_to_cells_mapping,
    create_overall_section,
    run_complete_workflow,
)
from .telemetry import TelemetryCollector


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--complete", required=True, type=Path)
    parser.add_argument("--instructions", required=True, type=Path)
    parser.add_argument(
        "--telemetry-output",
        type=Path,
        help="optional runtime, token-usage, and estimated-cost JSON output",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the rubric-mapping agent workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    part1 = subparsers.add_parser("part1", help="create sections.json")
    _add_common(part1)
    part1.add_argument("--output", type=Path, default=Path("sections.json"))
    part1.add_argument(
        "--summary-output",
        type=Path,
        help="summary Markdown output (default: summary.md beside --output)",
    )

    part2 = subparsers.add_parser("part2", help="create subsections.json")
    _add_common(part2)
    part2.add_argument("--sections", required=True, type=Path)
    part2.add_argument("--section-summary", required=True, type=Path)
    part2.add_argument("--output", type=Path, default=Path("subsections.json"))
    part2.add_argument(
        "--index-output",
        type=Path,
        help=(
            "agent-authored retrieval index output "
            "(default: subsection_index.json beside --output)"
        ),
    )

    part3 = subparsers.add_parser("part3", help="create items_to_cells.json")
    _add_common(part3)
    part3.add_argument("--rubric", required=True, type=Path)
    part3.add_argument("--sections", type=Path)
    part3.add_argument("--section-summary", type=Path)
    part3.add_argument("--subsections", type=Path)
    part3.add_argument("--subsection-index", type=Path)
    part3.add_argument("--output", type=Path, default=Path("items_to_cells.json"))

    all_stages = subparsers.add_parser("all", help="run Parts 1, 2, and 3")
    _add_common(all_stages)
    all_stages.add_argument("--rubric", required=True, type=Path)
    all_stages.add_argument("--output-dir", required=True, type=Path)

    visualize = subparsers.add_parser(
        "visualize", help="annotate a workbook copy with Parts 1-3 outputs"
    )
    visualize.add_argument("--workbook", required=True, type=Path)
    visualize.add_argument("--sections", type=Path)
    visualize.add_argument("--subsections", type=Path)
    visualize.add_argument("--items-to-cells", type=Path)
    visualize.add_argument("--rubric", type=Path)
    visualize.add_argument("--output", required=True, type=Path)
    visualize.add_argument("--no-legend", action="store_true")
    return parser


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    args = _parser().parse_args()
    if args.command == "visualize":
        from .review import create_review_workbook

        output = create_review_workbook(
            args.workbook,
            args.output,
            sections_path=args.sections,
            subsections_path=args.subsections,
            items_to_cells_path=args.items_to_cells,
            rubric_path=args.rubric,
            include_legend=not args.no_legend,
        )
        print(output)
        return 0

    common = (args.input, args.complete, args.instructions)
    telemetry = TelemetryCollector() if args.telemetry_output is not None else None
    started = time.monotonic()
    try:
        if args.command == "part1":
            create_overall_section(
                *common,
                output_path=args.output,
                summary_output_path=args.summary_output,
                telemetry=telemetry,
            )
            summary_output = (
                args.summary_output.resolve()
                if args.summary_output is not None
                else args.output.resolve().with_name("summary.md")
            )
            print(
                json.dumps(
                    {
                        "sections": str(args.output.resolve()),
                        "section_summary": str(summary_output),
                    },
                    indent=2,
                )
            )
        elif args.command == "part2":
            create_intermediate_sections(
                *common,
                args.sections,
                args.section_summary,
                output_path=args.output,
                index_output_path=args.index_output,
                telemetry=telemetry,
            )
            index_output = (
                args.index_output.resolve()
                if args.index_output is not None
                else args.output.resolve().with_name("subsection_index.json")
            )
            print(
                json.dumps(
                    {
                        "subsections": str(args.output.resolve()),
                        "subsection_index": str(index_output),
                    },
                    indent=2,
                )
            )
        elif args.command == "part3":
            create_items_to_cells_mapping(
                *common,
                args.rubric,
                sections_path=args.sections,
                section_summary_path=args.section_summary,
                subsections_path=args.subsections,
                subsection_index_path=args.subsection_index,
                output_path=args.output,
                telemetry=telemetry,
            )
            print(args.output.resolve())
        else:
            outputs = run_complete_workflow(
                *common,
                args.rubric,
                output_dir=args.output_dir,
                telemetry=telemetry,
            )
            print(json.dumps({key: str(path) for key, path in outputs.items()}, indent=2))
    finally:
        if telemetry is not None:
            command = "pipeline" if args.command == "all" else args.command
            telemetry.write(
                args.telemetry_output.resolve(),
                command,
                time.monotonic() - started,
            )
    return 0
