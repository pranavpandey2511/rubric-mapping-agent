"""Deep Agents construction for one isolated rubric-mapping stage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import FilesystemBackend
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class StageResponse(BaseModel):
    """Generic envelope; stage-specific validators check the inner artifact."""

    artifact: dict[str, Any]


SYSTEM_PROMPT = """You are the workbook-mapping agent for one isolated stage.

Use the xlsx-rubric-mapping skill. The user message declares the stage, the
only allowed input files, and the exact reference files to load. Read no other
task data. Inspect XLSX files without modifying them. Use the hosted `python`
tool for all Python execution; do not look for a local shell or Python process.

Return the requested JSON object inside the `artifact` field of the structured
response. Do not write the final artifact yourself. Do not include prose,
confidence, traces, or diagnostics inside the artifact.
"""


def _model_name() -> str:
    model = os.getenv("OPENAI_MODEL", "openai:gpt-5.6-terra")
    if ":" not in model:
        return model
    provider, model_name = model.split(":", 1)
    if provider != "openai" or not model_name:
        raise ValueError("OPENAI_MODEL must select an OpenAI model")
    return model_name


def build_agent(workspace_root: Path, container_id: str):
    """Build one stage agent bound to one hosted Python container."""

    workspace_root = workspace_root.resolve()
    model = ChatOpenAI(model=_model_name(), use_responses_api=True)
    return create_deep_agent(
        model=model,
        tools=[{"type": "code_interpreter", "container": container_id}],
        backend=FilesystemBackend(root_dir=workspace_root, virtual_mode=True),
        skills=[str(workspace_root / "skills")],
        system_prompt=SYSTEM_PROMPT,
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
