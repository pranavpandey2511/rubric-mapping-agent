from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rubric_mapping_agent.agent import StageResponse
from rubric_mapping_agent.workflow import _invoke_stage


class _FakeFiles:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str]] = []

    def create(self, container_id: str, *, file):
        filename = Path(file.name).name
        self.uploads.append((container_id, filename))
        return SimpleNamespace(path=f"/mnt/data/{filename}")


class _FakeContainers:
    def __init__(self) -> None:
        self.files = _FakeFiles()
        self.created: list[dict] = []
        self.deleted: list[str] = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(id="cntr_test")

    def delete(self, container_id: str) -> None:
        self.deleted.append(container_id)


class _FakeAgent:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requests: list[dict] = []

    def invoke(self, request: dict, *, config: dict):
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("agent failed")
        return {
            "structured_response": StageResponse(artifact={"sections": []})
        }


class CodeInterpreterLifecycleTests(unittest.TestCase):
    def _sources(self, root: Path) -> dict[str, Path]:
        input_path = root / "source.xlsx"
        instructions_path = root / "instructions.md"
        input_path.write_bytes(b"xlsx")
        instructions_path.write_text("instructions", encoding="utf-8")
        return {"input": input_path, "instructions": instructions_path}

    def test_stage_uploads_only_staged_files_and_deletes_container(self) -> None:
        client = SimpleNamespace(containers=_FakeContainers())
        agent = _FakeAgent()
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.workflow.OpenAI", return_value=client),
                patch("rubric_mapping_agent.workflow.build_agent", return_value=agent),
                patch.dict(
                    "os.environ", {"OPENAI_CODE_INTERPRETER_MEMORY": "4g"}
                ),
            ):
                artifact = _invoke_stage("part1", sources)

        self.assertEqual(artifact, {"sections": []})
        self.assertEqual(client.containers.deleted, ["cntr_test"])
        self.assertEqual(
            client.containers.created[0]["network_policy"], {"type": "disabled"}
        )
        self.assertEqual(client.containers.created[0]["memory_limit"], "4g")
        self.assertEqual(
            client.containers.files.uploads,
            [("cntr_test", "input.xlsx"), ("cntr_test", "instructions.md")],
        )
        prompt = agent.requests[0]["messages"][0]["content"]
        self.assertIn("python=/mnt/data/input.xlsx", prompt)
        self.assertNotIn("rubric.json", prompt.lower())

    def test_container_is_deleted_when_the_agent_fails(self) -> None:
        client = SimpleNamespace(containers=_FakeContainers())
        agent = _FakeAgent(fail=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = self._sources(Path(temp_dir))
            with (
                patch("rubric_mapping_agent.workflow.OpenAI", return_value=client),
                patch("rubric_mapping_agent.workflow.build_agent", return_value=agent),
            ):
                with self.assertRaisesRegex(RuntimeError, "agent failed"):
                    _invoke_stage("part1", sources)

        self.assertEqual(client.containers.deleted, ["cntr_test"])


if __name__ == "__main__":
    unittest.main()
