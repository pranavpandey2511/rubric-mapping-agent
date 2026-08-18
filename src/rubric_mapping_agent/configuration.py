"""Validated environment configuration for workflow orchestration."""

from __future__ import annotations

import os


PART3_CONTEXTS = {"none", "part1", "part1_part2"}
STAGE_SCOPES = {"sheet", "workbook"}
STAGE_SCOPE_ENV = {
    "part1": "RUBRIC_MAP_PART1_SCOPE",
    "part2": "RUBRIC_MAP_PART2_SCOPE",
    "part3": "RUBRIC_MAP_PART3_SCOPE",
}
STAGE_SCOPE_DEFAULTS = {
    "part1": "sheet",
    "part2": "workbook",
    "part3": "workbook",
}
SHEET_MAX_WORKERS_ENV = "RUBRIC_MAP_SHEET_MAX_WORKERS"
DEFAULT_SHEET_MAX_WORKERS = 4


def environment_choice(name: str, default: str, choices: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in choices:
        rendered = ", ".join(sorted(choices))
        raise ValueError(f"{name} must be one of: {rendered}")
    return value


def part3_context() -> str:
    return environment_choice(
        "RUBRIC_MAP_PART3_CONTEXT", "part1_part2", PART3_CONTEXTS
    )


def stage_scope(stage: str) -> str:
    try:
        name = STAGE_SCOPE_ENV[stage]
        default = STAGE_SCOPE_DEFAULTS[stage]
    except KeyError as exc:
        raise ValueError(f"Unknown stage {stage!r}") from exc
    return environment_choice(name, default, STAGE_SCOPES)


def sheet_max_workers() -> int:
    raw = os.getenv(SHEET_MAX_WORKERS_ENV, str(DEFAULT_SHEET_MAX_WORKERS)).strip()
    try:
        workers = int(raw)
    except ValueError as exc:
        raise ValueError(f"{SHEET_MAX_WORKERS_ENV} must be a positive integer") from exc
    if workers < 1:
        raise ValueError(f"{SHEET_MAX_WORKERS_ENV} must be a positive integer")
    return workers
