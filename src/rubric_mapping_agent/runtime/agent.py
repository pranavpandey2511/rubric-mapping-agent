"""Deep Agents construction for one isolated rubric-mapping stage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = PROJECT_ROOT / "skills"


class StageResponse(BaseModel):
    """Small receipt for artifacts written inside the hosted container."""

    model_config = ConfigDict(extra="forbid")

    artifact_paths: list[str]


SYSTEM_PROMPT = """You are the workbook-mapping agent for one isolated stage.

The user message declares the stage and the only allowed input files. Read no
other task data. Treat every supplied task file as read-only. Use the hosted
`python` tool for all Python execution; do not look for a local shell or Python
process.

The user message declares one or more hosted Python output paths. Write the
exact requested JSON artifacts only to those paths. Do not print or repeat the
artifacts, and do not create annotated workbooks, drawings, reports, or
intermediate files. Return the exact output paths in the `artifact_paths`
field.
"""

VISUAL_SYSTEM_PROMPT = """

A read-only `inspect_workbook_view` visual tool is attached to this agent. Start
with structural workbook inspection in hosted Python. When formatting, spatial
grouping, merged layout, or another visual feature could resolve a remaining
ambiguity, call `inspect_workbook_view` with the supplied workbook role
(`input` or `complete`), exact worksheet, and an anchor or bounded A1 range. You
may inspect matching regions in both supplied workbooks or page from a previous
view when that comparison is useful.

The tool may be restricted to the current target worksheet. It returns viewport
metadata and a screenshot as supporting visual evidence; it is never the source
of exact cell coordinates or membership. Do not ask it to save, recalculate, or
modify a workbook, and do not use any other visual or local-computer tool.
"""


def _model_name() -> str:
    model = os.getenv("OPENAI_MODEL", "openai:gpt-5.6-terra")
    if ":" not in model:
        return model
    provider, model_name = model.split(":", 1)
    if provider != "openai" or not model_name:
        raise ValueError("OPENAI_MODEL must select an OpenAI model")
    return model_name


def build_agent(
    container_id: str,
    *,
    skills_root: Path = SKILLS_ROOT,
    visual_tools: Sequence[Any] = (),
):
    """Build one stage agent bound to one hosted Python container."""

    skills_root = skills_root.resolve()
    model = ChatOpenAI(model=_model_name(), use_responses_api=True, temperature=0.1)
    tools = [{"type": "code_interpreter", "container": container_id}]
    tools.extend(visual_tools)
    return create_deep_agent(
        model=model,
        tools=tools,
        backend=FilesystemBackend(root_dir=skills_root, virtual_mode=True),
        # The backend exposes the project skills directory directly as `/`.
        skills=["/"],
        system_prompt=SYSTEM_PROMPT + (VISUAL_SYSTEM_PROMPT if visual_tools else ""),
        response_format=StageResponse,
        permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/**"],
                mode="deny",
            )
        ],
        name="xlsx-rubric-mapping",
    )
