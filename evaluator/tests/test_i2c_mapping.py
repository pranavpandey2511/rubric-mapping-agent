from __future__ import annotations

import unittest

from rubric_mapping_eval.common import EvaluationError
from rubric_mapping_eval.i2c_mapping import (
    evaluate_item_mappings,
    parse_item_mapping,
    parse_rubric,
)


def rubric_payload() -> dict:
    return {
        "criteria": {
            "criterion_1": {
                "criterion_id": 1,
                "grading": [{"item_id": "1.1"}, {"item_id": "1.2"}],
            },
            "criterion_2": {
                "criterion_id": 2,
                "grading": [{"item_id": "2.1"}],
            },
        }
    }


def gold_payload() -> dict:
    return {
        "items": [
            {
                "item_id": "1.1",
                "cells": [
                    {"sheet": "M", "address": "A1"},
                    {"sheet": "M", "address": "A2"},
                ],
            },
            {
                "item_id": "1.2",
                "cells": [{"sheet": "M", "address": "B1"}],
            },
            {
                "item_id": "2.1",
                "cells": [{"sheet": "M", "address": "C1"}],
            },
        ]
    }


def predicted_payload() -> dict:
    return {
        "items": [
            {
                "item_id": "1.1",
                "cells": [
                    {"sheet": "M", "address": "A1"},
                    {"sheet": "M", "address": "A3"},
                ],
            },
            {
                "item_id": "1.2",
                "cells": [{"sheet": "M", "address": "B1"}],
            },
            {"item_id": "2.1", "cells": []},
        ]
    }


class I2CMappingTests(unittest.TestCase):
    def test_item_and_criterion_aggregation(self) -> None:
        predicted = parse_item_mapping(
            predicted_payload(), context="predicted", allow_empty_cells=True
        )
        gold = parse_item_mapping(gold_payload(), context="gold", allow_empty_cells=False)
        criteria = parse_rubric(rubric_payload())

        result = evaluate_item_mappings(predicted, gold, criteria)

        self.assertEqual(result["evaluation"], "i2c_mapping")
        self.assertEqual(result["items"]["1.1"]["precision"], 0.5)
        self.assertEqual(result["items"]["1.1"]["recall"], 0.5)
        self.assertEqual(result["items"]["1.1"]["f1"], 0.5)
        self.assertEqual(result["items"]["2.1"]["f1"], 0.0)
        self.assertEqual(
            result["criteria"]["criterion_1"]["metrics"],
            {"precision": 0.75, "recall": 0.75, "f1": 0.75},
        )
        self.assertEqual(
            result["summary"]["criterion_macro"],
            {"precision": 0.375, "recall": 0.375, "f1": 0.375},
        )
        self.assertEqual(
            result["summary"]["item_macro"],
            {"precision": 0.5, "recall": 0.5, "f1": 0.5},
        )
        self.assertEqual(result["summary"]["mapped_item_fraction"], 2 / 3)

    def test_missing_item_is_validation_error(self) -> None:
        predicted_payload_value = predicted_payload()
        predicted_payload_value["items"].pop()
        predicted = parse_item_mapping(
            predicted_payload_value, context="predicted", allow_empty_cells=True
        )
        gold = parse_item_mapping(gold_payload(), context="gold", allow_empty_cells=False)

        with self.assertRaisesRegex(EvaluationError, "missing item_ids"):
            evaluate_item_mappings(predicted, gold, parse_rubric(rubric_payload()))

    def test_empty_gold_item_is_validation_error(self) -> None:
        payload = gold_payload()
        payload["items"][0]["cells"] = []
        with self.assertRaisesRegex(EvaluationError, "must not be empty in gold"):
            parse_item_mapping(payload, context="gold", allow_empty_cells=False)

    def test_rejects_duplicate_cell(self) -> None:
        payload = predicted_payload()
        payload["items"][0]["cells"] = [
            {"sheet": "M", "address": "A1"},
            {"sheet": "M", "address": "A1"},
        ]
        with self.assertRaisesRegex(EvaluationError, "duplicate cell"):
            parse_item_mapping(payload, context="predicted", allow_empty_cells=True)


if __name__ == "__main__":
    unittest.main()
