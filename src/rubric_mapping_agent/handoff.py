"""Cross-stage artifact policy and deterministic Markdown summaries."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Sequence


HANDOFF_JSON_ENV = "RUBRIC_MAP_HANDOFF_JSON"
HANDOFF_SUMMARY_ENV = "RUBRIC_MAP_HANDOFF_SUMMARY"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_SUMMARY_HEADING = re.compile(r"^(?P<identifier>\S+) — (?P<title>\S.*)$")
_SUMMARY_FIELD = re.compile(r"^\*\*(?P<label>[^*]+):\*\* (?P<value>\S.*)$")


@dataclass(frozen=True, slots=True)
class HandoffPolicy:
    """Select which generated artifacts are visible to the next agent."""

    include_json: bool = True
    include_summary: bool = True

    @classmethod
    def from_environment(cls) -> "HandoffPolicy":
        return cls(
            include_json=_environment_bool(HANDOFF_JSON_ENV, default=True),
            include_summary=_environment_bool(HANDOFF_SUMMARY_ENV, default=True),
        )

    def require_part2_context(self) -> None:
        if not (self.include_json or self.include_summary):
            raise ValueError(
                "Part 2 requires at least one Part 1 handoff. Enable "
                f"{HANDOFF_JSON_ENV} or {HANDOFF_SUMMARY_ENV}."
            )


@dataclass(frozen=True, slots=True)
class SummaryRecord:
    identifier: str
    title: str
    detail: str
    plain_language: str


def _environment_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    choices = ", ".join(sorted(_TRUE_VALUES | _FALSE_VALUES))
    raise ValueError(f"{name} must be one of: {choices}")


def _single_line(value: Any, *, context: str, max_words: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    normalized = " ".join(value.split())
    if len(normalized.split()) > max_words:
        raise ValueError(f"{context} must contain at most {max_words} words")
    return normalized


def parse_summary_records(
    raw_records: Any,
    *,
    id_field: str,
    expected_ids: Sequence[str],
    context: str,
) -> tuple[SummaryRecord, ...]:
    """Validate semantic records emitted beside a strict JSON mapping."""

    if not isinstance(raw_records, list):
        raise ValueError(f"{context} must be a list")
    required = {id_field, "title", "detail", "plain_language"}
    records: list[SummaryRecord] = []
    for index, raw in enumerate(raw_records):
        item_context = f"{context}[{index}]"
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError(
                f"{item_context} must contain exactly {sorted(required)}"
            )
        identifier = _single_line(
            raw[id_field], context=f"{item_context}.{id_field}", max_words=1
        )
        records.append(
            SummaryRecord(
                identifier=identifier,
                title=_single_line(
                    raw["title"], context=f"{item_context}.title", max_words=10
                ),
                detail=_single_line(
                    raw["detail"], context=f"{item_context}.detail", max_words=60
                ),
                plain_language=_single_line(
                    raw["plain_language"],
                    context=f"{item_context}.plain_language",
                    max_words=35,
                ),
            )
        )
    actual_ids = [record.identifier for record in records]
    if actual_ids != list(expected_ids):
        raise ValueError(f"{context} IDs must match mapping IDs in order")
    return tuple(records)


def render_section_summary(
    sections: Sequence[dict[str, Any]],
    records: Sequence[SummaryRecord],
) -> str:
    lines = ["# Part 1 Section Summary", ""]
    for section, record in zip(sections, records, strict=True):
        lines.extend(
            (
                f"## {record.identifier} — {record.title}",
                "",
                f"**Detail:** {record.detail}",
                "",
                f"**In normal words:** {record.plain_language}",
                "",
                f"**Worksheet:** `{section['sheet']}`",
                "",
            )
        )
    return "\n".join(lines)


def _parse_markdown_summary(
    text: str,
    *,
    document_heading: str,
) -> tuple[tuple[str, str, dict[str, str]], ...]:
    chunks = re.split(r"(?m)^## ", text)
    if chunks[0].strip() != document_heading:
        raise ValueError(f"summary.md must start with {document_heading!r}")
    parsed: list[tuple[str, str, dict[str, str]]] = []
    for index, chunk in enumerate(chunks[1:]):
        nonempty = [line.strip() for line in chunk.splitlines() if line.strip()]
        if not nonempty:
            raise ValueError(f"summary.md entry {index} is empty")
        heading = _SUMMARY_HEADING.fullmatch(nonempty[0])
        if heading is None:
            raise ValueError(f"summary.md entry {index} has an invalid heading")
        fields: dict[str, str] = {}
        for line in nonempty[1:]:
            field = _SUMMARY_FIELD.fullmatch(line)
            if field is None or field.group("label") in fields:
                raise ValueError(f"summary.md entry {index} has an invalid field")
            fields[field.group("label")] = field.group("value")
        parsed.append(
            (heading.group("identifier"), heading.group("title"), fields)
        )
    return tuple(parsed)


def validate_section_summary(
    text: str,
    sections: Sequence[dict[str, Any]],
) -> None:
    parsed = _parse_markdown_summary(
        text, document_heading="# Part 1 Section Summary"
    )
    if len(parsed) != len(sections):
        raise ValueError("summary.md must contain one entry per section")
    expected_fields = {"Detail", "In normal words", "Worksheet"}
    for (identifier, title, fields), section in zip(parsed, sections, strict=True):
        if identifier != section["section_id"]:
            raise ValueError("summary.md section IDs must match sections.json in order")
        if set(fields) != expected_fields:
            raise ValueError(f"summary.md section {identifier!r} has invalid fields")
        _single_line(
            title,
            context=f"summary.md section {identifier!r} title",
            max_words=10,
        )
        _single_line(
            fields["Detail"],
            context=f"summary.md section {identifier!r} detail",
            max_words=60,
        )
        _single_line(
            fields["In normal words"],
            context=f"summary.md section {identifier!r} plain language",
            max_words=35,
        )
        if fields["Worksheet"] != f"`{section['sheet']}`":
            raise ValueError(
                f"summary.md section {identifier!r} has the wrong worksheet"
            )
