from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from rubric_mapping_agent.runtime.agent import StageResponse
from rubric_mapping_agent.workflow import _invoke_stage


class _FakeFiles:
    def __init__(
        self,
        artifact: dict | None = None,
        *,
        generated_count: int = 1,
        raw_content: bytes | None = None,
        generated_artifacts: dict[str, dict] | None = None,
    ) -> None:
        self.uploads: list[tuple[str, str]] = []
        self.upload_sources: list[Path] = []
        self.list_calls: list[tuple[str, int]] = []
        self.downloads: list[tuple[str, str]] = []
        default_content = raw_content or json.dumps(
            artifact
            if artifact is not None
            else {"sections": [], "section_summaries": []}
        ).encode("utf-8")
        if generated_artifacts is None:
            self._generated = [
                SimpleNamespace(
                    id=f"file_generated_{index}",
                    path="/mnt/data/sections.json",
                    source="assistant",
                )
                for index in range(generated_count)
            ]
            self._content_by_id = {
                generated.id: default_content for generated in self._generated
            }
        else:
            self._generated = []
            self._content_by_id = {}
            for index, (path, payload) in enumerate(generated_artifacts.items()):
                generated = SimpleNamespace(
                    id=f"file_generated_{index}",
                    path=path,
                    source="assistant",
                )
                self._generated.append(generated)
                self._content_by_id[generated.id] = json.dumps(payload).encode("utf-8")
        self.content = SimpleNamespace(retrieve=self._retrieve_content)

    def create(self, container_id: str, *, file):
        if isinstance(file, tuple):
            filename, upload = file
        else:
            upload = file
            filename = Path(upload.name).name
        self.uploads.append((container_id, filename))
        self.upload_sources.append(Path(upload.name))
        return SimpleNamespace(path=f"/mnt/data/{filename}")

    def list(self, container_id: str, *, limit: int):
        self.list_calls.append((container_id, limit))
        return self._generated

    def _retrieve_content(self, file_id: str, *, container_id: str):
        self.downloads.append((container_id, file_id))
        return SimpleNamespace(read=lambda: self._content_by_id[file_id])


class _FakeContainers:
    def __init__(self, files: _FakeFiles | None = None) -> None:
        self.files = files or _FakeFiles()
        self.created: list[dict] = []
        self.deleted: list[str] = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(id="cntr_test")

    def delete(self, container_id: str) -> None:
        self.deleted.append(container_id)


class _FakeAgent:
    def __init__(
        self,
        *,
        fail: bool = False,
        artifact_paths: list[str] | None = None,
    ) -> None:
        self.fail = fail
        self.artifact_paths = artifact_paths or ["/mnt/data/sections.json"]
        self.requests: list[dict] = []
        self.configs: list[dict] = []

    def invoke(self, request: dict, *, config: dict):
        self.requests.append(request)
        self.configs.append(config)
        if self.fail:
            raise RuntimeError("agent failed")
        return {
            "structured_response": StageResponse(
                artifact_paths=self.artifact_paths
            )
        }


class CodeInterpreterLifecycleTests(unittest.TestCase):
    def _sources(self, root: Path) -> dict[str, Path]:
        input_path = root / "source.xlsx"
        instructions_path = root / "instructions.md"
        input_path.write_bytes(b"xlsx")
        instructions_path.write_text("instructions", encoding="utf-8")
        return {"input": input_path, "instructions": instructions_path}

    def test_stage_uploads_sources_directly_and_deletes_container(self) -> None:
        client = SimpleNamespace(containers=_FakeContainers())
        agent = _FakeAgent()
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch("rubric_mapping_agent.runtime.stage.build_agent", return_value=agent),
                patch.dict(
                    "os.environ",
                    {
                        "OPENAI_CODE_INTERPRETER_MEMORY": "4g",
                    },
                ),
            ):
                artifact = _invoke_stage("part1", sources, target_sheet="Model")

        self.assertEqual(
            artifact,
            {"sections": [], "section_summaries": []},
        )
        self.assertEqual(client.containers.deleted, ["cntr_test"])
        self.assertEqual(
            client.containers.created[0]["network_policy"], {"type": "disabled"}
        )
        self.assertEqual(client.containers.created[0]["memory_limit"], "4g")
        self.assertEqual(
            client.containers.files.uploads,
            [("cntr_test", "input.xlsx"), ("cntr_test", "instructions.md")],
        )
        self.assertEqual(
            client.containers.files.upload_sources,
            [sources["input"], sources["instructions"]],
        )
        self.assertEqual(client.containers.files.list_calls, [("cntr_test", 100)])
        self.assertEqual(
            client.containers.files.downloads,
            [("cntr_test", "file_generated_0")],
        )
        prompt = agent.requests[0]["messages"][0]["content"]
        self.assertIn("python=/mnt/data/input.xlsx", prompt)
        self.assertNotIn("rubric.json", prompt.lower())
        self.assertIn("CONTAINER_OUTPUTS:\n- /mnt/data/sections.json", prompt)
        self.assertIn("`sections` and `section_summaries`", prompt)
        self.assertIn("Do not print", prompt)
        self.assertIn('TARGET_SHEET: "Model"', prompt)
        self.assertEqual(
            agent.configs[0]["metadata"],
            {
                "stage": "part1",
                "workbook": Path(sources["input"]).parent.name,
                "execution_scope": "sheet",
                "sheet": "Model",
                "part1_policy": "current",
            },
        )

    def test_part2_downloads_two_direct_agent_generated_files(self) -> None:
        files = _FakeFiles(
            generated_artifacts={
                "/mnt/data/subsections.json": {"subsections": []},
                "/mnt/data/subsection_index.json": {
                    "schema_version": 2,
                    "generated_by": "part2_agent",
                    "families": [],
                    "relationships": [],
                },
            }
        )
        client = SimpleNamespace(containers=_FakeContainers(files))
        agent = _FakeAgent(
            artifact_paths=[
                "/mnt/data/subsections.json",
                "/mnt/data/subsection_index.json",
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch("rubric_mapping_agent.runtime.stage.build_agent", return_value=agent),
            ):
                artifact = _invoke_stage("part2", sources, target_sheet="Model")

        self.assertEqual(
            artifact,
            {
                "subsections": [],
                "subsection_index": {
                    "schema_version": 2,
                    "generated_by": "part2_agent",
                    "families": [],
                    "relationships": [],
                },
            },
        )
        self.assertEqual(len(files.downloads), 2)
        prompt = agent.requests[0]["messages"][0]["content"]
        self.assertIn("/mnt/data/subsections.json", prompt)
        self.assertIn("/mnt/data/subsection_index.json", prompt)
        self.assertIn("Do not create a combined envelope", prompt)

    def test_enabled_visual_runtime_is_scoped_attached_and_closed(self) -> None:
        client = SimpleNamespace(containers=_FakeContainers())
        agent = _FakeAgent()
        visual_tool = object()
        skill_bundle = SimpleNamespace(
            root=Path("/tmp/visual-stage-skills"),
            close=Mock(),
        )
        visual_runtime = SimpleNamespace(
            enabled=True,
            tool=Mock(return_value=visual_tool),
            close=Mock(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch(
                    "rubric_mapping_agent.runtime.stage.create_visual_runtime",
                    return_value=visual_runtime,
                ) as create_runtime,
                patch(
                    "rubric_mapping_agent.runtime.stage.create_stage_skill_bundle",
                    return_value=skill_bundle,
                ) as create_skill_bundle,
                patch(
                    "rubric_mapping_agent.runtime.stage.build_agent",
                    return_value=agent,
                ) as build_agent,
            ):
                _invoke_stage("part1", sources, target_sheet="Model")

        self.assertEqual(
            create_runtime.call_args.kwargs["allowed_sheets"], {"Model"}
        )
        self.assertEqual(create_runtime.call_args.args[0], sources)
        self.assertEqual(build_agent.call_args.args, ("cntr_test",))
        self.assertEqual(
            build_agent.call_args.kwargs["visual_tools"], [visual_tool]
        )
        self.assertEqual(
            build_agent.call_args.kwargs["skills_root"], skill_bundle.root
        )
        create_skill_bundle.assert_called_once_with("part1", visual_enabled=True)
        skill_bundle.close.assert_called_once_with()
        visual_runtime.close.assert_called_once_with()

    def test_disabled_visual_runtime_selects_normal_skill_bundle(self) -> None:
        client = SimpleNamespace(containers=_FakeContainers())
        agent = _FakeAgent()
        skill_bundle = SimpleNamespace(
            root=Path("/tmp/normal-stage-skills"),
            close=Mock(),
        )
        visual_runtime = SimpleNamespace(
            enabled=False,
            close=Mock(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch(
                    "rubric_mapping_agent.runtime.stage.create_visual_runtime",
                    return_value=visual_runtime,
                ),
                patch(
                    "rubric_mapping_agent.runtime.stage.create_stage_skill_bundle",
                    return_value=skill_bundle,
                ) as create_skill_bundle,
                patch(
                    "rubric_mapping_agent.runtime.stage.build_agent",
                    return_value=agent,
                ) as build_agent,
            ):
                _invoke_stage("part1", sources, target_sheet="Model")

        create_skill_bundle.assert_called_once_with("part1", visual_enabled=False)
        self.assertEqual(build_agent.call_args.kwargs["visual_tools"], [])
        self.assertEqual(
            build_agent.call_args.kwargs["skills_root"], skill_bundle.root
        )
        skill_bundle.close.assert_called_once_with()
        visual_runtime.close.assert_called_once_with()

    def test_container_is_deleted_when_the_agent_fails(self) -> None:
        client = SimpleNamespace(containers=_FakeContainers())
        agent = _FakeAgent(fail=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch("rubric_mapping_agent.runtime.stage.build_agent", return_value=agent),
            ):
                with self.assertRaisesRegex(RuntimeError, "agent failed"):
                    _invoke_stage("part1", sources, target_sheet="Model")

        self.assertEqual(client.containers.deleted, ["cntr_test"])

    def test_large_generated_artifact_uses_file_transport(self) -> None:
        artifact = {
            "sections": [
                {
                    "section_id": "section_001",
                    "sheet": "Model",
                    "cells": [f"A{index}" for index in range(1, 5_297)],
                }
            ],
            "section_summaries": [
                {
                    "section_id": "section_001",
                    "title": "Model Output",
                    "detail": "Contains the modeled output rows.",
                    "plain_language": "Shows the model results.",
                }
            ],
        }
        client = SimpleNamespace(
            containers=_FakeContainers(_FakeFiles(artifact))
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch(
                    "rubric_mapping_agent.runtime.stage.build_agent",
                    return_value=_FakeAgent(),
                ),
            ):
                result = _invoke_stage("part1", sources, target_sheet="Model")

        self.assertEqual(result, artifact)
        self.assertEqual(client.containers.deleted, ["cntr_test"])

    def test_missing_generated_artifact_deletes_container(self) -> None:
        client = SimpleNamespace(
            containers=_FakeContainers(_FakeFiles(generated_count=0))
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch(
                    "rubric_mapping_agent.runtime.stage.build_agent",
                    return_value=_FakeAgent(),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "found 0"):
                    _invoke_stage("part1", sources, target_sheet="Model")

        self.assertEqual(client.containers.deleted, ["cntr_test"])

    def test_invalid_generated_json_deletes_container(self) -> None:
        client = SimpleNamespace(
            containers=_FakeContainers(_FakeFiles(raw_content=b"not-json"))
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch(
                    "rubric_mapping_agent.runtime.stage.build_agent",
                    return_value=_FakeAgent(),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "is not JSON"):
                    _invoke_stage("part1", sources, target_sheet="Model")

        self.assertEqual(client.containers.deleted, ["cntr_test"])

    def test_wrong_receipt_path_deletes_container(self) -> None:
        client = SimpleNamespace(containers=_FakeContainers())
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch(
                    "rubric_mapping_agent.runtime.stage.build_agent",
                    return_value=_FakeAgent(artifact_paths=["/mnt/data/wrong.json"]),
                ),
            ):
                with self.assertRaisesRegex(ValueError, "unexpected artifact path"):
                    _invoke_stage("part1", sources, target_sheet="Model")

        self.assertEqual(client.containers.deleted, ["cntr_test"])

    def test_part1_can_run_with_workbook_scope(self) -> None:
        client = SimpleNamespace(containers=_FakeContainers())
        agent = _FakeAgent()
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.runtime.stage.OpenAI", return_value=client),
                patch(
                    "rubric_mapping_agent.runtime.stage.build_agent",
                    return_value=agent,
                ),
            ):
                _invoke_stage("part1", sources)

        self.assertEqual(len(client.containers.created), 1)
        prompt = agent.requests[0]["messages"][0]["content"]
        self.assertIn("EXECUTION_SCOPE: workbook", prompt)
        self.assertNotIn("TARGET_SHEET", prompt)
        self.assertEqual(
            agent.configs[0]["metadata"]["execution_scope"], "workbook"
        )


if __name__ == "__main__":
    unittest.main()
