"""Command-line interface for rubric-mapping evaluation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from .batch import evaluate_batch_manifest
from .common import EvaluationError, write_json
from .i2c_mapping import evaluate_i2c_files
from .sectioning import evaluate_section_files


def _add_output_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSON results to this path instead of stdout.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rubric-mapping-eval",
        description="Evaluate rubric-mapping sectioning and item-to-cell artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sectioning_parser = subparsers.add_parser(
        "sectioning", help="Evaluate sectioning outputs in sections.json."
    )
    sectioning_parser.add_argument("--predicted", type=Path, required=True)
    sectioning_parser.add_argument("--gold", type=Path, required=True)
    _add_output_argument(sectioning_parser)

    i2c_parser = subparsers.add_parser(
        "i2c", help="Evaluate I2C mappings in items_to_cells.json."
    )
    i2c_parser.add_argument("--predicted", type=Path, required=True)
    i2c_parser.add_argument("--gold", type=Path, required=True)
    i2c_parser.add_argument("--rubric", type=Path, required=True)
    _add_output_argument(i2c_parser)

    batch_parser = subparsers.add_parser(
        "batch", help="Evaluate tasks described by a batch manifest."
    )
    batch_parser.add_argument("--manifest", type=Path, required=True)
    _add_output_argument(batch_parser)
    return parser


def _evaluate(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "sectioning":
        return evaluate_section_files(args.predicted, args.gold)
    if args.command == "i2c":
        return evaluate_i2c_files(args.predicted, args.gold, args.rubric)
    if args.command == "batch":
        return evaluate_batch_manifest(args.manifest)
    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = _evaluate(args)
        rendered = write_json(result, args.output)
    except (EvaluationError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    if args.output is None:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
