"""Shared validation and metric primitives."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection, Hashable, Iterable, Mapping


_CELL_ADDRESS_RE = re.compile(r"([A-Z]{1,3})([1-9][0-9]*)")
_MAX_EXCEL_COLUMN = 16_384  # XFD
_MAX_EXCEL_ROW = 1_048_576


class EvaluationError(ValueError):
    """Raised when an input does not satisfy the evaluator's contract."""


def require_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvaluationError(f"{context} must be a JSON object")
    return value


def require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvaluationError(f"{context} must be a JSON array")
    return value


def require_nonempty_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or value == "":
        raise EvaluationError(f"{context} must be a non-empty string")
    return value


def require_exact_keys(
    value: Mapping[str, Any], expected: Collection[str], context: str
) -> None:
    expected_set = set(expected)
    actual_set = set(value)
    if actual_set == expected_set:
        return
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    details: list[str] = []
    if missing:
        details.append(f"missing {missing}")
    if extra:
        details.append(f"unexpected {extra}")
    raise EvaluationError(f"{context} has invalid keys: {', '.join(details)}")


def _column_number(column_letters: str) -> int:
    value = 0
    for character in column_letters:
        value = value * 26 + (ord(character) - ord("A") + 1)
    return value


def validate_cell_address(address: Any, context: str) -> str:
    """Validate canonical, absolute-free A1 notation without modifying it."""

    address = require_nonempty_string(address, context)
    match = _CELL_ADDRESS_RE.fullmatch(address)
    if match is None:
        raise EvaluationError(
            f"{context} must use canonical uppercase A1 notation, for example A1 or XFD1048576"
        )
    column_letters, row_text = match.groups()
    if _column_number(column_letters) > _MAX_EXCEL_COLUMN:
        raise EvaluationError(f"{context} exceeds Excel's maximum column XFD")
    if int(row_text) > _MAX_EXCEL_ROW:
        raise EvaluationError(f"{context} exceeds Excel's maximum row 1048576")
    return address


@dataclass(frozen=True, order=True, slots=True)
class CellRef:
    """A cell uniquely identified by exact sheet name and A1 address."""

    sheet: str
    address: str

    @classmethod
    def create(cls, sheet: Any, address: Any, context: str) -> "CellRef":
        return cls(
            sheet=require_nonempty_string(sheet, f"{context}.sheet"),
            address=validate_cell_address(address, f"{context}.address"),
        )

    def to_dict(self) -> dict[str, str]:
        return {"sheet": self.sheet, "address": self.address}


@dataclass(frozen=True, slots=True)
class Metrics:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float

    @property
    def predicted_count(self) -> int:
        return self.true_positive + self.false_positive

    @property
    def gold_count(self) -> int:
        return self.true_positive + self.false_negative

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "counts": {
                "true_positive": self.true_positive,
                "false_positive": self.false_positive,
                "false_negative": self.false_negative,
                "predicted": self.predicted_count,
                "gold": self.gold_count,
            },
        }


def calculate_metrics(
    predicted: set[Hashable], gold: set[Hashable], *, context: str
) -> Metrics:
    """Calculate precision, recall and F1 from two non-weighted sets."""

    if not gold:
        raise EvaluationError(f"{context} gold set must not be empty")

    true_positive = len(predicted & gold)
    false_positive = len(predicted - gold)
    false_negative = len(gold - predicted)
    predicted_count = true_positive + false_positive
    gold_count = true_positive + false_negative

    precision = true_positive / predicted_count if predicted_count else 0.0
    recall = true_positive / gold_count
    f1_denominator = 2 * true_positive + false_positive + false_negative
    f1 = 2 * true_positive / f1_denominator if f1_denominator else 0.0

    return Metrics(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def average_scores(scores: Iterable[Mapping[str, float]], *, context: str) -> dict[str, float]:
    values = list(scores)
    if not values:
        raise EvaluationError(f"{context} requires at least one score")
    return {
        name: sum(float(score[name]) for score in values) / len(values)
        for name in ("precision", "recall", "f1")
    }


def read_json(path: str | Path) -> Any:
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise EvaluationError(f"JSON file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationError(
            f"Invalid JSON in {source}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def write_json(payload: Any, path: str | Path | None = None) -> str:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path is not None:
        Path(path).write_text(rendered, encoding="utf-8")
    return rendered
