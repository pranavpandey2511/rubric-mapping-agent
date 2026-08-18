from __future__ import annotations

import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.tools import ToolException
from openpyxl import Workbook

from rubric_mapping_agent.visual.inspection import (
    ViewportCapture,
    VisualWorkbookConfig,
    VisualWorkbookRuntime,
    _normalized_range,
)


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class _FakeBackend:
    def __init__(self) -> None:
        self.requests = []
        self.closed = False

    def capture(self, request):
        self.requests.append(request)
        return ViewportCapture(
            png=PNG_1X1,
            engine="fake",
            sheet=request.sheet,
            requested_range=f"{request.sheet}!{request.cell_range}",
            visible_range=f"{request.sheet}!{request.cell_range}",
            zoom=request.zoom,
            width=1,
            height=1,
        )

    def close(self) -> None:
        self.closed = True


class VisualWorkbookConfigTests(unittest.TestCase):
    def test_visual_backend_defaults_to_off(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = VisualWorkbookConfig.from_env()

        self.assertEqual(config.backend, "off")
        self.assertEqual((config.width, config.height), (1440, 900))

    def test_visual_backend_and_viewport_are_loaded_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RUBRIC_MAP_VISUAL_BACKEND": "libreoffice_pdf",
                "RUBRIC_MAP_VISUAL_WIDTH": "1280",
                "RUBRIC_MAP_VISUAL_HEIGHT": "720",
            },
            clear=True,
        ):
            config = VisualWorkbookConfig.from_env()

        self.assertEqual(config.backend, "libreoffice_pdf")
        self.assertEqual((config.width, config.height), (1280, 720))

    def test_invalid_backend_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"RUBRIC_MAP_VISUAL_BACKEND": "computer"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "must be one of"):
                VisualWorkbookConfig.from_env()


class ViewportPlanningTests(unittest.TestCase):
    def test_anchor_expands_to_a_deterministic_range(self) -> None:
        self.assertEqual(
            _normalized_range(
                anchor="B3",
                cell_range=None,
                navigation="absolute",
                rows=5,
                columns=3,
                previous_range=None,
            ),
            "B3:D7",
        )

    def test_page_down_keeps_three_rows_of_overlap(self) -> None:
        self.assertEqual(
            _normalized_range(
                anchor=None,
                cell_range=None,
                navigation="page_down",
                rows=40,
                columns=14,
                previous_range="B3:D7",
            ),
            "B5:D9",
        )

    def test_unbounded_column_range_is_rejected(self) -> None:
        with self.assertRaisesRegex(ToolException, "bounded A1 rectangle"):
            _normalized_range(
                anchor=None,
                cell_range="A:B",
                navigation="absolute",
                rows=40,
                columns=14,
                previous_range=None,
            )


class VisualWorkbookToolTests(unittest.TestCase):
    def _runtime(self, root: Path, *, artifacts_dir: Path | None = None):
        workbook = root / "complete.xlsx"
        workbook.write_bytes(b"staged workbook")
        backend = _FakeBackend()
        runtime = VisualWorkbookRuntime(
            VisualWorkbookConfig(backend="libreoffice_pdf"),
            {"complete": workbook},
            allowed_sheets={"Model"},
            artifacts_dir=artifacts_dir,
            backend=backend,
        )
        return runtime, backend

    def test_tool_returns_metadata_and_an_original_detail_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, backend = self._runtime(Path(temp_dir))
            result = runtime.tool().invoke(
                {
                    "workbook": "complete",
                    "sheet": "Model",
                    "anchor": "B3",
                    "rows": 5,
                    "columns": 3,
                    "zoom": 125,
                }
            )

        metadata = json.loads(result[0]["text"])
        self.assertEqual(metadata["requested_range"], "Model!B3:D7")
        self.assertEqual(metadata["visible_range"], "Model!B3:D7")
        self.assertEqual(metadata["zoom"], 125)
        self.assertEqual(metadata["zoom_mode"], "calc_percentage")
        self.assertEqual(result[1]["type"], "image_url")
        self.assertEqual(result[1]["image_url"]["detail"], "original")
        self.assertTrue(
            result[1]["image_url"]["url"].startswith("data:image/png;base64,")
        )
        self.assertEqual(backend.requests[0].cell_range, "B3:D7")

    def test_tool_persists_png_and_metadata_when_artifacts_are_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifacts_dir = root / "visual-inspection"
            runtime, _ = self._runtime(root, artifacts_dir=artifacts_dir)
            result = runtime.tool().invoke(
                {
                    "workbook": "complete",
                    "sheet": "Model",
                    "cell_range": "A1:C5",
                }
            )

            returned_metadata = json.loads(result[0]["text"])
            png_path = artifacts_dir / returned_metadata["artifact_png"]
            metadata_path = artifacts_dir / returned_metadata["artifact_metadata"]
            self.assertEqual(png_path.read_bytes(), PNG_1X1)
            self.assertEqual(
                json.loads(metadata_path.read_text(encoding="utf-8")),
                returned_metadata,
            )
            self.assertEqual(
                sorted(path.suffix for path in artifacts_dir.iterdir()),
                [".json", ".png"],
            )

    def test_tool_keeps_navigation_state_per_workbook_and_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, backend = self._runtime(Path(temp_dir))
            tool = runtime.tool()
            tool.invoke(
                {
                    "workbook": "complete",
                    "sheet": "Model",
                    "cell_range": "A1:C5",
                }
            )
            tool.invoke(
                {
                    "workbook": "complete",
                    "sheet": "Model",
                    "navigation": "page_down",
                }
            )

        self.assertEqual(
            [request.cell_range for request in backend.requests],
            ["A1:C5", "A3:C7"],
        )

    def test_tool_rejects_a_sheet_outside_the_stage_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, backend = self._runtime(Path(temp_dir))
            result = runtime.tool().invoke(
                {
                    "workbook": "complete",
                    "sheet": "Other",
                    "anchor": "A1",
                }
            )

        self.assertIn("outside this stage scope", result)
        self.assertEqual(backend.requests, [])

    def test_close_closes_the_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, backend = self._runtime(Path(temp_dir))
            runtime.close()

        self.assertTrue(backend.closed)

    def test_ui_capture_uses_the_process_wide_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "complete.xlsx"
            workbook.write_bytes(b"staged workbook")
            backend = _FakeBackend()
            runtime = VisualWorkbookRuntime(
                VisualWorkbookConfig(backend="libreoffice_ui"),
                {"complete": workbook},
                allowed_sheets={"Model"},
                backend=backend,
            )
            lock = MagicMock()
            with patch(
                "rubric_mapping_agent.visual.inspection."
                "_LIBREOFFICE_UI_CAPTURE_LOCK",
                lock,
            ):
                runtime.tool().invoke(
                    {
                        "workbook": "complete",
                        "sheet": "Model",
                        "cell_range": "A1:B2",
                    }
                )

        lock.__enter__.assert_called_once_with()
        lock.__exit__.assert_called_once()

    def test_pdf_capture_uses_the_runtime_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime, _ = self._runtime(Path(temp_dir))
            lock = MagicMock()
            runtime._capture_lock = lock
            runtime.tool().invoke(
                {
                    "workbook": "complete",
                    "sheet": "Model",
                    "cell_range": "A1:B2",
                }
            )

        lock.__enter__.assert_called_once_with()
        lock.__exit__.assert_called_once()


@unittest.skipUnless(
    os.getenv("RUBRIC_MAP_RUN_LIBREOFFICE_TESTS") == "1",
    "set RUBRIC_MAP_RUN_LIBREOFFICE_TESTS=1 for the local renderer smoke test",
)
class LibreOfficePdfIntegrationTests(unittest.TestCase):
    def test_pdf_backend_renders_a_staged_range_to_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workbook_path = root / "workbook.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Model"
            sheet["A1"] = "Revenue"
            sheet["B1"] = 125
            sheet["A2"] = "Cost"
            sheet["B2"] = 80
            workbook.save(workbook_path)
            workbook.close()

            runtime = VisualWorkbookRuntime(
                VisualWorkbookConfig(
                    backend="libreoffice_pdf",
                    width=800,
                    height=600,
                ),
                {"complete": workbook_path},
                allowed_sheets={"Model"},
            )
            try:
                result = runtime.tool().invoke(
                    {
                        "workbook": "complete",
                        "sheet": "Model",
                        "cell_range": "A1:B2",
                    }
                )
            finally:
                runtime.close()

        self.assertIsInstance(result, list)
        metadata = json.loads(result[0]["text"])
        self.assertEqual(metadata["engine"], "libreoffice_pdf")
        self.assertEqual(metadata["visible_range"], "Model!A1:B2")
        self.assertIsNone(metadata["zoom"])
        self.assertEqual(metadata["zoom_mode"], "fit_range")
        self.assertGreater(metadata["image_width"], 0)
        self.assertGreater(metadata["image_height"], 0)


@unittest.skipUnless(
    os.getenv("RUBRIC_MAP_RUN_LIBREOFFICE_UI_TESTS") == "1",
    "set RUBRIC_MAP_RUN_LIBREOFFICE_UI_TESTS=1 for the visible UI smoke test",
)
class LibreOfficeUiIntegrationTests(unittest.TestCase):
    def test_ui_backend_positions_calc_and_captures_its_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workbook_path = root / "workbook.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Model"
            sheet["D12"] = "Target"
            sheet["E12"] = 125
            workbook.save(workbook_path)
            workbook.close()

            runtime = VisualWorkbookRuntime(
                VisualWorkbookConfig(
                    backend="libreoffice_ui",
                    width=900,
                    height=650,
                    capture_delay_seconds=0.1,
                ),
                {"complete": workbook_path},
                allowed_sheets={"Model"},
            )
            try:
                result = runtime.tool().invoke(
                    {
                        "workbook": "complete",
                        "sheet": "Model",
                        "cell_range": "D12:E15",
                        "zoom": 125,
                    }
                )
            finally:
                runtime.close()

        self.assertIsInstance(result, list)
        metadata = json.loads(result[0]["text"])
        self.assertEqual(metadata["engine"], "libreoffice_ui")
        self.assertEqual(metadata["requested_range"], "Model!D12:E15")
        self.assertEqual(metadata["zoom"], 125)
        self.assertEqual(metadata["zoom_mode"], "calc_percentage")
        self.assertGreater(metadata["image_width"], 0)
        self.assertGreater(metadata["image_height"], 0)


if __name__ == "__main__":
    unittest.main()
