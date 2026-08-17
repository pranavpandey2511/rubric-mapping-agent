"""LangGraph server entry point for the same stage functions used by the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from .workflow import (
    create_intermediate_sections,
    create_items_to_cells_mapping,
    create_overall_section,
    run_complete_workflow,
)


class WorkflowState(TypedDict):
    stage: Literal["part1", "part2", "part3", "all"]
    input_path: str
    complete_path: str
    instructions_path: str
    rubric_path: NotRequired[str]
    sections_path: NotRequired[str]
    subsections_path: NotRequired[str]
    output_path: NotRequired[str]
    output_dir: NotRequired[str]
    result: NotRequired[dict[str, Any]]


def run_stage(state: WorkflowState) -> dict[str, Any]:
    common = (
        state["input_path"],
        state["complete_path"],
        state["instructions_path"],
    )
    stage = state["stage"]
    if stage == "part1":
        output = Path(state.get("output_path", "sections.json")).resolve()
        artifact = create_overall_section(*common, output_path=output)
        return {"result": {"artifact": artifact, "output_path": str(output)}}
    if stage == "part2":
        output = Path(state.get("output_path", "subsections.json")).resolve()
        artifact = create_intermediate_sections(
            *common,
            state["sections_path"],
            output_path=output,
        )
        return {"result": {"artifact": artifact, "output_path": str(output)}}
    if stage == "part3":
        output = Path(state.get("output_path", "items_to_cells.json")).resolve()
        artifact = create_items_to_cells_mapping(
            *common,
            state["rubric_path"],
            sections_path=state.get("sections_path"),
            subsections_path=state.get("subsections_path"),
            output_path=output,
        )
        return {"result": {"artifact": artifact, "output_path": str(output)}}

    outputs = run_complete_workflow(
        *common,
        state["rubric_path"],
        output_dir=state.get("output_dir", "outputs"),
    )
    return {"result": {key: str(path) for key, path in outputs.items()}}


builder = StateGraph(WorkflowState)
builder.add_node("run_stage", run_stage)
builder.add_edge(START, "run_stage")
builder.add_edge("run_stage", END)
graph = builder.compile()
