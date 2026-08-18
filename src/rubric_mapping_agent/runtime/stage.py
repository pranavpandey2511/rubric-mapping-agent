"""One isolated hosted stage invocation and its artifact receipt."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from openai import OpenAI

from ..stage_outputs import require_files as _require_files
from ..visual.inspection import create_visual_runtime
from .agent import StageResponse, build_agent
from .skills import create_stage_skill_bundle


LOGGER = logging.getLogger(__name__)
CODE_INTERPRETER_MEMORY_LIMITS = {"1g", "4g", "16g", "64g"}
STAGE_OUTPUT_FILES = {
    "part1": "sections.json",
    "part2": "subsections.json",
    "part3": "items_to_cells.json",
}
PART2_INDEX_OUTPUT_FILE = "subsection_index.json"


def _part3_source_context(sources: dict[str, Path]) -> str:
    if any(name in sources for name in ("subsections", "subsection_index")):
        return "part1_part2"
    if "sections" in sources or "section_summary" in sources:
        return "part1"
    return "none"


def _stage_prompt(
    stage: str,
    python_files: dict[str, str],
    *,
    target_sheet: str | None = None,
) -> str:
    if stage not in STAGE_OUTPUT_FILES:
        raise ValueError(f"Unknown stage {stage!r}")

    listed = "\n".join(
        f"- {name}: python={python_files[name]}" for name in python_files
    )
    output_paths = [f"/mnt/data/{STAGE_OUTPUT_FILES[stage]}"]
    if stage == "part2":
        output_paths.append(f"/mnt/data/{PART2_INDEX_OUTPUT_FILE}")
    rendered_outputs = "\n".join(f"- {path}" for path in output_paths)
    if target_sheet is None:
        target_scope = """
EXECUTION_SCOPE: workbook

This invocation covers the complete workbook. Consider every worksheet needed
for this stage and return one workbook-wide artifact.
"""
    elif stage == "part1":
        target_scope = f"""
EXECUTION_SCOPE: sheet
TARGET_SHEET: {json.dumps(target_sheet)}

This invocation covers only TARGET_SHEET. Inspect cell-level contents only for
that exact worksheet in input.xlsx and complete.xlsx, and return sections only
for that worksheet. Workbook-level names, data-validation references, and
formula references may be queried only to determine whether TARGET_SHEET is
functionally used; do not analyze or emit sections for another worksheet. The
orchestrator will combine worksheet artifacts and assign final section IDs.
"""
    elif stage == "part2":
        target_scope = f"""
EXECUTION_SCOPE: sheet
TARGET_SHEET: {json.dumps(target_sheet)}

This invocation owns only TARGET_SHEET. Return subsections only for Part 1
parents on that exact worksheet. You may inspect workbook-level names and direct
formula relationships for semantic orientation, but do not emit a subsection
or cell for another worksheet. Generate workbook-unique subsection and family
IDs using the required sheet-ordinal ID convention. The orchestrator will
concatenate worksheet artifacts without renaming IDs or relationship endpoints.
"""
    else:
        target_scope = f"""
EXECUTION_SCOPE: sheet
TARGET_SHEET: {json.dumps(target_sheet)}

Evaluate every rubric item, but emit cells only from TARGET_SHEET. Include every
rubric item ID even when its cells list is empty for this worksheet. You may
inspect other worksheets for interpretation and direct relationships, but do
not emit a cell from another worksheet. The orchestrator will union each item's
worksheet results into one workbook-wide artifact.
"""
    if stage == "part1":
        output_contract = """Write compact UTF-8 JSON there with exactly two root keys:
`sections` and `section_summaries`. Keep `sections` schema-compatible. For
every section, add exactly one `section_summaries` entry with the same local
`section_id`, a concise business title, a concise technical detail, and a plain-
language explanation. Use exactly `section_id`, `title`, `detail`, and
`plain_language` in each summary entry. Do not add prose fields inside
`sections`."""
    elif stage == "part2":
        output_contract = """Write `/mnt/data/subsections.json` as compact UTF-8
JSON whose only root key is `subsections`. Write
`/mnt/data/subsection_index.json` separately as the exact semantic family and
relationship index defined by the Part 2 output contract. Author both files
directly. Do not create a combined envelope or a Markdown summary."""
    else:
        output_contract = "Write compact UTF-8 JSON there whose only root key is `items`."
    return f"""TASK_STAGE: {stage}
{target_scope}

Allowed task files:
{listed}

Use the hosted python tool at least once. Its paths above are authoritative.
Do not inspect any task path not listed above.

CONTAINER_OUTPUTS:
{rendered_outputs}

All task files are read-only. Your sole permitted writes are the declared
CONTAINER_OUTPUTS. {output_contract} Do not print or repeat the artifacts and
do not create any other file. Return only the structured receipt
`{{"artifact_paths": {json.dumps(output_paths)}}}`.
"""


def _memory_limit() -> str:
    memory_limit = os.getenv("OPENAI_CODE_INTERPRETER_MEMORY", "4g")
    if memory_limit not in CODE_INTERPRETER_MEMORY_LIMITS:
        choices = ", ".join(sorted(CODE_INTERPRETER_MEMORY_LIMITS))
        raise ValueError(f"OPENAI_CODE_INTERPRETER_MEMORY must be one of: {choices}")
    return memory_limit


def _artifact_receipt(result: dict[str, Any], stage: str) -> StageResponse:
    response = result.get("structured_response")
    try:
        return (
            response
            if isinstance(response, StageResponse)
            else StageResponse.model_validate(response)
        )
    except Exception as exc:
        raise ValueError(f"{stage} agent did not return an artifact receipt") from exc


def _download_container_artifact(
    client: OpenAI,
    container_id: str,
    expected_path: str,
) -> dict[str, Any]:
    matches = [
        item
        for item in client.containers.files.list(container_id, limit=100)
        if item.path == expected_path and item.source == "assistant"
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one generated container artifact at {expected_path}, "
            f"found {len(matches)}"
        )

    response = client.containers.files.content.retrieve(
        matches[0].id,
        container_id=container_id,
    )
    try:
        text = response.read().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Container artifact at {expected_path} is not UTF-8") from exc
    try:
        artifact = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Container artifact at {expected_path} is not JSON") from exc
    if not isinstance(artifact, dict):
        raise ValueError(f"Container artifact at {expected_path} must be a JSON object")
    return artifact


def _invoke_stage(
    stage: str,
    sources: dict[str, Path],
    *,
    target_sheet: str | None = None,
    visual_artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    _require_files(sources.values())
    if stage not in STAGE_OUTPUT_FILES:
        raise ValueError(f"Unknown stage {stage!r}")

    expected_outputs = [f"/mnt/data/{STAGE_OUTPUT_FILES[stage]}"]
    if stage == "part2":
        expected_outputs.append(f"/mnt/data/{PART2_INDEX_OUTPUT_FILE}")
    visual_runtime = create_visual_runtime(
        sources,
        allowed_sheets={target_sheet} if target_sheet is not None else None,
        artifacts_dir=visual_artifacts_dir,
    )
    skill_bundle = None
    client = None
    container = None
    try:
        skill_bundle = create_stage_skill_bundle(
            stage,
            visual_enabled=visual_runtime.enabled,
        )
        client = OpenAI()
        container = client.containers.create(
            name=f"rubric-map-{stage}-{uuid4().hex[:8]}",
            memory_limit=_memory_limit(),
            network_policy={"type": "disabled"},
        )
        python_files: dict[str, str] = {}
        for name, source in sources.items():
            container_name = f"{name}{''.join(source.suffixes)}"
            with source.open("rb") as upload:
                remote_file = client.containers.files.create(
                    container.id,
                    file=(container_name, upload),
                )
            python_files[name] = remote_file.path

        visual_tools = [visual_runtime.tool()] if visual_runtime.enabled else []
        agent = build_agent(
            container.id,
            skills_root=skill_bundle.root,
            visual_tools=visual_tools,
        )
        workbook_label = sources.get("input", Path("workbook")).parent.name
        trace_scope = target_sheet or "workbook"
        trace_metadata = {
            "stage": stage,
            "workbook": workbook_label,
            "execution_scope": "sheet" if target_sheet is not None else "workbook",
        }
        if target_sheet is not None:
            trace_metadata["sheet"] = target_sheet
        if stage == "part1":
            trace_metadata["part1_policy"] = "current"
        if stage == "part3":
            trace_metadata.update(
                {
                    "part3_evidence": "scoring_aware",
                    "part3_context": _part3_source_context(sources),
                    "handoff_json": any(
                        name in sources for name in ("sections", "subsections")
                    ),
                    "handoff_summary": "section_summary" in sources,
                    "part3_retrieval_index": "subsection_index" in sources,
                }
            )
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": _stage_prompt(
                            stage,
                            python_files,
                            target_sheet=target_sheet,
                        ),
                    }
                ]
            },
            config={
                "configurable": {"thread_id": f"{stage}-{uuid4()}"},
                "run_name": f"{stage}:{workbook_label}:{trace_scope}",
                "metadata": trace_metadata,
            },
        )
        receipt = _artifact_receipt(result, stage)
        if receipt.artifact_paths != expected_outputs:
            raise ValueError(
                f"{stage} agent returned unexpected artifact paths "
                f"{receipt.artifact_paths!r}"
            )
        downloaded = [
            _download_container_artifact(client, container.id, expected_output)
            for expected_output in expected_outputs
        ]
        if stage == "part2":
            artifact = {
                "subsections": downloaded[0].get("subsections"),
                "subsection_index": downloaded[1],
            }
            if set(downloaded[0]) != {"subsections"}:
                raise ValueError(
                    "Part 2 agent-generated subsections.json has invalid root keys"
                )
        else:
            artifact = downloaded[0]
    finally:
        if skill_bundle is not None:
            try:
                skill_bundle.close()
            except Exception:
                LOGGER.warning(
                    "Could not remove the temporary stage skill bundle",
                    exc_info=True,
                )
        try:
            visual_runtime.close()
        except Exception:
            LOGGER.warning(
                "Could not close the visual workbook runtime",
                exc_info=True,
            )
        if client is not None and container is not None:
            try:
                client.containers.delete(container.id)
            except Exception:
                LOGGER.warning(
                    "Could not delete expired or unreachable Code Interpreter "
                    "container %s",
                    container.id,
                    exc_info=True,
                )
    return artifact
