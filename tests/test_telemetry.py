from __future__ import annotations

import unittest

from rubric_mapping_agent.telemetry import (
    TelemetryCollector,
    estimate_container_session,
    estimate_model_call,
)


class TelemetryTests(unittest.TestCase):
    def test_terra_cost_separates_cached_input_and_output(self) -> None:
        result = estimate_model_call(
            {
                "model": "gpt-5.6-terra",
                "service_tier": "default",
                "usage": {
                    "input_tokens": 1_000,
                    "output_tokens": 100,
                    "total_tokens": 1_100,
                    "input_token_details": {"cache_read": 200},
                    "output_token_details": {"reasoning": 40},
                },
            }
        )

        self.assertEqual(result["tokens"]["uncached_input"], 800)
        self.assertEqual(result["tokens"]["cached_input"], 200)
        self.assertEqual(result["tokens"]["reasoning_output"], 40)
        self.assertAlmostEqual(result["estimated_cost_usd"], 0.00284)
        self.assertTrue(result["cost_complete"])

    def test_long_context_multiplier_is_applied_per_call(self) -> None:
        result = estimate_model_call(
            {
                "model": "gpt-5.6-sol-2026-08-01",
                "usage": {
                    "input_tokens": 300_000,
                    "output_tokens": 10_000,
                    "total_tokens": 310_000,
                },
            }
        )

        self.assertTrue(result["long_context_pricing"])
        self.assertAlmostEqual(result["estimated_cost_usd"], 3.45)

    def test_unknown_model_is_not_silently_priced_as_zero(self) -> None:
        result = estimate_model_call(
            {
                "model": "unknown-model",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        )

        self.assertIsNone(result["estimated_cost_usd"])
        self.assertFalse(result["cost_complete"])

    def test_container_uses_five_minute_minimum(self) -> None:
        result = estimate_container_session("4g", 61.0)

        self.assertEqual(result["billed_minutes"], 5)
        self.assertAlmostEqual(result["estimated_cost_usd"], 0.03)

    def test_collector_aggregates_model_and_container_cost(self) -> None:
        collector = TelemetryCollector()
        collector.record_invocation(
            stage="part1",
            target_sheet="Model",
            duration_seconds=61.0,
            usage_calls=(
                {
                    "model": "gpt-5.6-terra",
                    "usage": {
                        "input_tokens": 1_000,
                        "output_tokens": 100,
                        "total_tokens": 1_100,
                    },
                },
            ),
            container_memory="4g",
            container_created=True,
            success=True,
        )

        report = collector.report("part1", 62.0)

        self.assertEqual(report["totals"]["model_call_count"], 1)
        self.assertEqual(report["totals"]["container_sessions"], 1)
        self.assertAlmostEqual(report["totals"]["total_cost_usd"], 0.0332)
        self.assertTrue(report["totals"]["cost_complete"])


if __name__ == "__main__":
    unittest.main()
