from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import _list_skills

from rubric_mapping_agent.runtime.agent import SKILLS_ROOT, SYSTEM_PROMPT, build_agent


class AgentConfigurationTests(unittest.TestCase):
    def test_imports_do_not_load_workflow_or_dotenv(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; import rubric_mapping_agent; "
                    "assert 'rubric_mapping_agent.workflow' not in sys.modules; "
                    "import rubric_mapping_agent.runtime.agent; "
                    "assert 'dotenv' not in sys.modules"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_skill_source_uses_real_project_skills_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_root = Path(temp_dir)
            with (
                patch("rubric_mapping_agent.runtime.agent.ChatOpenAI"),
                patch(
                    "rubric_mapping_agent.runtime.agent.create_deep_agent"
                ) as create_agent,
            ):
                build_agent("cntr_test", skills_root=skills_root)

        backend = create_agent.call_args.kwargs["backend"]
        self.assertEqual(backend.cwd, skills_root.resolve())
        self.assertEqual(create_agent.call_args.kwargs["skills"], ["/"])
        self.assertEqual(
            create_agent.call_args.kwargs["tools"],
            [{"type": "code_interpreter", "container": "cntr_test"}],
        )
        self.assertNotIn(
            "inspect_workbook_view",
            create_agent.call_args.kwargs["system_prompt"],
        )
        self.assertNotIn("xlsx-rubric-mapping", SYSTEM_PROMPT)

    def test_project_skills_root_discovers_excel_and_rubric_mapping(self) -> None:
        backend = FilesystemBackend(root_dir=SKILLS_ROOT, virtual_mode=True)

        names = {skill["name"] for skill in _list_skills(backend, "/")}

        self.assertIn("excel", names)
        self.assertIn("xlsx-rubric-mapping", names)

    def test_visual_tool_is_appended_and_visual_prompt_is_enabled(self) -> None:
        visual_tool = object()
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_root = Path(temp_dir)
            with (
                patch("rubric_mapping_agent.runtime.agent.ChatOpenAI"),
                patch(
                    "rubric_mapping_agent.runtime.agent.create_deep_agent"
                ) as create_agent,
            ):
                build_agent(
                    "cntr_test",
                    skills_root=skills_root,
                    visual_tools=[visual_tool],
                )

        tools = create_agent.call_args.kwargs["tools"]
        self.assertEqual(
            tools[0],
            {"type": "code_interpreter", "container": "cntr_test"},
        )
        self.assertIs(tools[1], visual_tool)
        self.assertIn(
            "inspect_workbook_view",
            create_agent.call_args.kwargs["system_prompt"],
        )


if __name__ == "__main__":
    unittest.main()
