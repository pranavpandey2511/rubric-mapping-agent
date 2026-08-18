from __future__ import annotations

import unittest
from unittest.mock import patch

from rubric_mapping_agent.handoff import (
    HandoffPolicy,
    SummaryRecord,
    render_section_summary,
    validate_section_summary,
)


class HandoffTests(unittest.TestCase):
    def test_handoff_channels_are_enabled_by_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            policy = HandoffPolicy.from_environment()

        self.assertTrue(policy.include_json)
        self.assertTrue(policy.include_summary)

    def test_handoff_channels_accept_common_boolean_spellings(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "RUBRIC_MAP_HANDOFF_JSON": "off",
                "RUBRIC_MAP_HANDOFF_SUMMARY": "yes",
            },
            clear=True,
        ):
            policy = HandoffPolicy.from_environment()

        self.assertFalse(policy.include_json)
        self.assertTrue(policy.include_summary)

    def test_invalid_handoff_value_is_rejected(self) -> None:
        with patch.dict(
            "os.environ", {"RUBRIC_MAP_HANDOFF_JSON": "sometimes"}, clear=True
        ):
            with self.assertRaisesRegex(ValueError, "RUBRIC_MAP_HANDOFF_JSON"):
                HandoffPolicy.from_environment()

    def test_section_summary_omits_coordinates_and_validates(self) -> None:
        sections = [
            {
                "section_id": "section_001",
                "sheet": "Model",
                "cells": ["B2", "C2", "B3", "C3", "E2", "E3"],
            }
        ]
        records = [
            SummaryRecord(
                identifier="section_001",
                title="Revenue Build",
                detail="Contains historical and projected revenue calculations.",
                plain_language="Shows past sales and expected future sales.",
            )
        ]

        rendered = render_section_summary(sections, records)
        validate_section_summary(rendered, sections)

        self.assertNotIn("Cell ranges", rendered)
        self.assertNotIn("B2", rendered)
        with self.assertRaisesRegex(ValueError, "wrong worksheet"):
            validate_section_summary(rendered.replace("`Model`", "`Other`"), sections)


if __name__ == "__main__":
    unittest.main()
