from __future__ import annotations

import unittest

from scripts.run_examples import build_assignment_eval_results


class AllExamplesReportTests(unittest.TestCase):
    def test_assignment_report_contains_per_example_metrics_and_runtime(self) -> None:
        metrics = {"precision": 0.8, "recall": 0.9, "f1": 0.847}
        stage_value = {
            "evaluation": {"metrics": metrics},
            "runtime": {"wall_time_seconds": 10.0, "total_cost_usd": 0.5},
        }
        batch_report = {
            "pricing": {"currency": "USD", "estimated": True},
            "examples": {
                "keysight": {
                    "run_evaluation": "artifacts/example-runs/keysight/run/evaluation.json",
                    "stages": {
                        "part1": stage_value,
                        "part2": {"evaluation": None, "runtime": {}},
                        "part3": stage_value,
                    },
                    "totals": {"wall_time_seconds": 20.0, "total_cost_usd": 1.0},
                }
            },
            "stages": {"part1": {}, "part2": {}, "part3": {}},
            "totals": {"wall_time_seconds": 20.0, "total_cost_usd": 1.0},
        }

        report = build_assignment_eval_results(batch_report)

        self.assertEqual(report["examples"]["keysight"]["part1"], metrics)
        self.assertEqual(report["examples"]["keysight"]["part3"], metrics)
        self.assertEqual(report["summary"]["part1_task_macro"], metrics)
        self.assertEqual(
            report["examples"]["keysight"]["runtime"]["total"][
                "total_cost_usd"
            ],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
