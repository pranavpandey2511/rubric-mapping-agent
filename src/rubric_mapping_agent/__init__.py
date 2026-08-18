"""Public entry points for the rubric-mapping agent."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORT_MODULES = {
    "create_intermediate_sections": ".workflow",
    "create_items_to_cells_mapping": ".workflow",
    "create_overall_section": ".workflow",
    "run_complete_workflow": ".workflow",
    "create_review_workbook": ".review",
    "visualize_mapping_outputs": ".review",
}

__all__ = [
    "create_intermediate_sections",
    "create_items_to_cells_mapping",
    "create_overall_section",
    "create_review_workbook",
    "run_complete_workflow",
    "visualize_mapping_outputs",
]


def __getattr__(name: str) -> Any:
    """Load optional runtime dependencies only when an entry point is used."""

    try:
        module_name = _EXPORT_MODULES[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value
