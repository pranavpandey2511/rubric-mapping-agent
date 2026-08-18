from __future__ import annotations

import copy
import unittest

from rubric_mapping_agent.retrieval_index import validate_subsection_index


class RetrievalIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.subsections = [
            {
                "subsection_id": "subsection_s001_001",
                "parent_section_id": "section_001",
                "sheet": "Model",
                "cells": ["C2", "D2", "E2"],
                "roles": ["projected", "calculation"],
            }
        ]
        self.eligible = {("Model", "D2"), ("Model", "E2")}
        self.payload = {
            "schema_version": 2,
            "generated_by": "part2_agent",
            "families": [
                {
                    "family_id": "subsection_s001_001_family_01",
                    "subsection_id": "subsection_s001_001",
                    "parent_section_id": "section_001",
                    "sheet": "Model",
                    "object_name": "Projected Revenue",
                    "aliases": ["Sales"],
                    "changed_cells": ["D2", "E2"],
                    "anchor_cells": ["C2"],
                    "roles": ["projected", "calculation"],
                    "scope": {
                        "period_type": "projected",
                        "period_headers": [
                            {"cell": "D1", "label": "FY2025E"},
                            {"cell": "E1", "label": "FY2026E"},
                        ],
                    },
                    "orientation": "row",
                    "calculation_kind": "calculation",
                    "formula_signatures": ["=R[0]C[-1]*(1+R[4]C[0])"],
                }
            ],
            "relationships": [],
        }

    def test_accepts_complete_agent_authored_index(self) -> None:
        validate_subsection_index(
            self.payload,
            subsections=self.subsections,
            eligible=self.eligible,
        )

    def test_rejects_non_agent_provenance(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["generated_by"] = "host_builder"
        with self.assertRaisesRegex(ValueError, "Part 2 agent"):
            validate_subsection_index(
                payload,
                subsections=self.subsections,
                eligible=self.eligible,
            )

    def test_rejects_incomplete_changed_cell_coverage(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["families"][0]["changed_cells"] = ["D2"]
        with self.assertRaisesRegex(ValueError, "does not cover"):
            validate_subsection_index(
                payload,
                subsections=self.subsections,
                eligible=self.eligible,
            )

    def test_rejects_anchor_outside_subsection(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["families"][0]["anchor_cells"] = ["A1"]
        with self.assertRaisesRegex(ValueError, "anchors outside"):
            validate_subsection_index(
                payload,
                subsections=self.subsections,
                eligible=self.eligible,
            )

    def test_rejects_unknown_relationship_family(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["relationships"] = [
            {
                "source_family_id": "subsection_s001_001_family_01",
                "target_family_id": "missing_family",
                "relationship": "feeds",
            }
        ]
        with self.assertRaisesRegex(ValueError, "invalid family lineage"):
            validate_subsection_index(
                payload,
                subsections=self.subsections,
                eligible=self.eligible,
            )


if __name__ == "__main__":
    unittest.main()
