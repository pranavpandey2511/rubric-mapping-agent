"""Public API for rubric-mapping evaluation."""

from .batch import evaluate_batch_manifest
from .common import CellRef, EvaluationError, Metrics
from .i2c_mapping import (
    Criterion,
    evaluate_i2c_files,
    evaluate_item_mappings,
    parse_item_mapping,
    parse_rubric,
)
from .sectioning import (
    CellPair,
    Section,
    build_grouped_pairs,
    evaluate_section_files,
    evaluate_sections,
    parse_sections,
)

__all__ = [
    "CellPair",
    "CellRef",
    "Criterion",
    "EvaluationError",
    "Metrics",
    "Section",
    "build_grouped_pairs",
    "evaluate_batch_manifest",
    "evaluate_i2c_files",
    "evaluate_item_mappings",
    "evaluate_section_files",
    "evaluate_sections",
    "parse_item_mapping",
    "parse_rubric",
    "parse_sections",
]
