"""Runtime, token-usage, and estimated OpenAI cost accounting."""

from __future__ import annotations

import math
import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from .artifacts import write_json


PRICING_AS_OF = date(2026, 8, 19).isoformat()
LONG_CONTEXT_THRESHOLD_TOKENS = 272_000
MILLION = Decimal(1_000_000)

# Standard-processing prices in USD per 1M tokens. These values intentionally
# live in one auditable table instead of being scattered across orchestration.
MODEL_PRICING_USD_PER_1M: dict[str, dict[str, Decimal]] = {
    "gpt-5.6-sol": {
        "input": Decimal("5.00"),
        "cached_input": Decimal("0.50"),
        "cache_write": Decimal("6.25"),
        "output": Decimal("30.00"),
    },
    "gpt-5.6-terra": {
        "input": Decimal("2.00"),
        "cached_input": Decimal("0.20"),
        "cache_write": Decimal("2.50"),
        "output": Decimal("12.00"),
    },
    "gpt-5.6-luna": {
        "input": Decimal("0.20"),
        "cached_input": Decimal("0.02"),
        "cache_write": Decimal("0.25"),
        "output": Decimal("1.20"),
    },
}

# Current hosted-container list price per 20 minutes. Eligible sessions are
# estimated per minute with a five-minute minimum, matching the pricing note.
CONTAINER_PRICE_USD_PER_20_MINUTES = {
    "1g": Decimal("0.03"),
    "4g": Decimal("0.12"),
    "16g": Decimal("0.48"),
    "64g": Decimal("1.92"),
}
SERVICE_TIER_MULTIPLIER = {
    None: Decimal("1"),
    "auto": Decimal("1"),
    "default": Decimal("1"),
    "standard": Decimal("1"),
    "flex": Decimal("0.5"),
    "fast": Decimal("2"),
    "priority": Decimal("2"),
}


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.00000001")))


def _pricing_model(model: str) -> str | None:
    normalized = model.removeprefix("openai:")
    for known in MODEL_PRICING_USD_PER_1M:
        if normalized == known or normalized.startswith(f"{known}-"):
            return known
    return None


class DetailedUsageCallbackHandler(UsageMetadataCallbackHandler):
    """Collect aggregate LangChain usage and preserve each billable model call."""

    def __init__(self) -> None:
        super().__init__()
        self._calls_lock = threading.Lock()
        self.calls: list[dict[str, Any]] = []

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        super().on_llm_end(response, **kwargs)
        try:
            generation = response.generations[0][0]
        except IndexError:
            return
        if not isinstance(generation, ChatGeneration):
            return
        message = generation.message
        if not isinstance(message, AIMessage) or not message.usage_metadata:
            return
        record = {
            "model": message.response_metadata.get("model_name") or "unknown",
            "service_tier": message.response_metadata.get("service_tier"),
            "usage": deepcopy(dict(message.usage_metadata)),
        }
        with self._calls_lock:
            self.calls.append(record)


def estimate_model_call(call: dict[str, Any]) -> dict[str, Any]:
    """Return normalized token counts and a transparent cost estimate."""

    usage = call.get("usage") or {}
    input_details = usage.get("input_token_details") or {}
    output_details = usage.get("output_token_details") or {}
    input_tokens = int(usage.get("input_tokens", 0))
    output_tokens = int(usage.get("output_tokens", 0))
    cached_input_tokens = int(
        input_details.get("cache_read", input_details.get("priority_cache_read", 0))
        or 0
    )
    cache_write_tokens = int(
        input_details.get(
            "cache_creation", input_details.get("priority_cache_creation", 0)
        )
        or 0
    )
    uncached_input_tokens = max(
        0, input_tokens - cached_input_tokens - cache_write_tokens
    )
    reasoning_tokens = int(
        output_details.get("reasoning", output_details.get("priority_reasoning", 0))
        or 0
    )
    model = str(call.get("model") or "unknown")
    pricing_model = _pricing_model(model)
    service_tier = call.get("service_tier")
    tier_multiplier = SERVICE_TIER_MULTIPLIER.get(service_tier)
    long_context = input_tokens > LONG_CONTEXT_THRESHOLD_TOKENS

    cost: Decimal | None = None
    if pricing_model is not None and tier_multiplier is not None:
        rates = MODEL_PRICING_USD_PER_1M[pricing_model]
        input_multiplier = Decimal("2") if long_context else Decimal("1")
        output_multiplier = Decimal("1.5") if long_context else Decimal("1")
        cost = tier_multiplier * (
            Decimal(uncached_input_tokens)
            * rates["input"]
            * input_multiplier
            + Decimal(cached_input_tokens)
            * rates["cached_input"]
            * input_multiplier
            + Decimal(cache_write_tokens)
            * rates["cache_write"]
            * input_multiplier
            + Decimal(output_tokens) * rates["output"] * output_multiplier
        ) / MILLION

    return {
        "model": model,
        "pricing_model": pricing_model,
        "service_tier": service_tier or "default",
        "long_context_pricing": long_context,
        "tokens": {
            "input": input_tokens,
            "uncached_input": uncached_input_tokens,
            "cached_input": cached_input_tokens,
            "cache_write": cache_write_tokens,
            "output": output_tokens,
            "reasoning_output": reasoning_tokens,
            "total": int(usage.get("total_tokens", input_tokens + output_tokens)),
        },
        "estimated_cost_usd": _money(cost) if cost is not None else None,
        "cost_complete": cost is not None,
    }


def estimate_container_session(memory_limit: str, duration_seconds: float) -> dict[str, Any]:
    """Estimate one hosted-container session using minute billing and its minimum."""

    unit_price = CONTAINER_PRICE_USD_PER_20_MINUTES.get(memory_limit)
    billed_minutes = max(5, math.ceil(max(0.0, duration_seconds) / 60.0))
    cost = (
        unit_price * Decimal(billed_minutes) / Decimal(20)
        if unit_price is not None
        else None
    )
    return {
        "memory_limit": memory_limit,
        "actual_duration_seconds": round(duration_seconds, 6),
        "billed_minutes": billed_minutes,
        "estimated_cost_usd": _money(cost) if cost is not None else None,
        "cost_complete": cost is not None,
    }


@dataclass(frozen=True)
class InvocationRecord:
    stage: str
    target_sheet: str | None
    duration_seconds: float
    model_calls: tuple[dict[str, Any], ...]
    container: dict[str, Any] | None
    success: bool


class TelemetryCollector:
    """Thread-safe collector shared by workbook- or sheet-scoped invocations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[InvocationRecord] = []

    def record_invocation(
        self,
        *,
        stage: str,
        target_sheet: str | None,
        duration_seconds: float,
        usage_calls: Iterable[dict[str, Any]],
        container_memory: str | None,
        container_created: bool,
        success: bool,
    ) -> None:
        model_calls = tuple(estimate_model_call(call) for call in usage_calls)
        container = (
            estimate_container_session(container_memory, duration_seconds)
            if container_created and container_memory is not None
            else None
        )
        record = InvocationRecord(
            stage=stage,
            target_sheet=target_sheet,
            duration_seconds=duration_seconds,
            model_calls=model_calls,
            container=container,
            success=success,
        )
        with self._lock:
            self._records.append(record)

    def report(self, command: str, wall_time_seconds: float) -> dict[str, Any]:
        with self._lock:
            records = tuple(self._records)

        invocations: list[dict[str, Any]] = []
        for record in records:
            model_costs = [call["estimated_cost_usd"] for call in record.model_calls]
            model_cost_complete = bool(record.model_calls) and all(
                cost is not None for cost in model_costs
            )
            model_cost = sum(float(cost) for cost in model_costs if cost is not None)
            container_cost = (
                record.container["estimated_cost_usd"]
                if record.container is not None
                else None
            )
            cost_complete = (
                model_cost_complete
                and container_cost is not None
                and record.success
            )
            invocations.append(
                {
                    "stage": record.stage,
                    "execution_scope": (
                        "sheet" if record.target_sheet is not None else "workbook"
                    ),
                    "target_sheet": record.target_sheet,
                    "success": record.success,
                    "wall_time_seconds": round(record.duration_seconds, 6),
                    "model_calls": list(record.model_calls),
                    "container": record.container,
                    "totals": {
                        **_token_totals(record.model_calls),
                        "model_call_count": len(record.model_calls),
                        "model_cost_usd": (
                            round(model_cost, 8) if model_cost_complete else None
                        ),
                        "container_cost_usd": container_cost,
                        "total_cost_usd": (
                            round(model_cost + float(container_cost), 8)
                            if cost_complete
                            else None
                        ),
                        "cost_complete": cost_complete,
                    },
                }
            )

        return {
            "schema_version": 1,
            "command": command,
            "pricing": pricing_metadata(),
            "invocations": invocations,
            "totals": aggregate_invocation_totals(
                invocations, wall_time_seconds=wall_time_seconds
            ),
        }

    def write(self, path: Path, command: str, wall_time_seconds: float) -> None:
        write_json(self.report(command, wall_time_seconds), path)


def _token_totals(model_calls: Iterable[dict[str, Any]]) -> dict[str, int]:
    calls = tuple(model_calls)
    return {
        name: sum(int(call["tokens"].get(name, 0)) for call in calls)
        for name in (
            "input",
            "uncached_input",
            "cached_input",
            "cache_write",
            "output",
            "reasoning_output",
            "total",
        )
    }


def aggregate_invocation_totals(
    invocations: Iterable[dict[str, Any]], *, wall_time_seconds: float
) -> dict[str, Any]:
    values = tuple(invocations)
    token_names = (
        "input",
        "uncached_input",
        "cached_input",
        "cache_write",
        "output",
        "reasoning_output",
        "total",
    )
    totals: dict[str, Any] = {
        "wall_time_seconds": round(wall_time_seconds, 6),
        "agent_invocation_wall_time_seconds": round(
            sum(float(value.get("wall_time_seconds", 0)) for value in values), 6
        ),
        "agent_invocation_count": len(values),
        "model_call_count": sum(
            int(value.get("totals", {}).get("model_call_count", 0))
            for value in values
        ),
        "container_sessions": sum(value.get("container") is not None for value in values),
    }
    totals.update(
        {
            name: sum(
                int(value.get("totals", {}).get(name, 0)) for value in values
            )
            for name in token_names
        }
    )
    cost_complete = bool(values) and all(
        bool(value.get("totals", {}).get("cost_complete")) for value in values
    )
    model_costs = [value.get("totals", {}).get("model_cost_usd") for value in values]
    container_costs = [
        value.get("totals", {}).get("container_cost_usd") for value in values
    ]
    totals.update(
        {
            "model_cost_usd": (
                round(sum(float(cost) for cost in model_costs), 8)
                if cost_complete
                else None
            ),
            "container_cost_usd": (
                round(sum(float(cost) for cost in container_costs), 8)
                if cost_complete
                else None
            ),
            "total_cost_usd": (
                round(
                    sum(float(cost) for cost in model_costs + container_costs), 8
                )
                if cost_complete
                else None
            ),
            "cost_complete": cost_complete,
        }
    )
    return totals


def aggregate_stage_reports(
    reports: Iterable[dict[str, Any]], *, wall_time_seconds: float
) -> dict[str, Any]:
    """Aggregate stage-level telemetry without double-counting parallel wall time."""

    values = tuple(reports)
    invocations = [
        invocation
        for report in values
        for invocation in report.get("invocations", [])
    ]
    totals = aggregate_invocation_totals(invocations, wall_time_seconds=wall_time_seconds)
    totals["stage_process_wall_time_seconds"] = round(
        sum(
            float(report.get("totals", {}).get("process_wall_time_seconds", 0))
            for report in values
        ),
        6,
    )
    return totals


def pricing_metadata() -> dict[str, Any]:
    return {
        "currency": "USD",
        "as_of": PRICING_AS_OF,
        "estimated": True,
        "source_url": "https://developers.openai.com/api/docs/pricing",
        "method": (
            "Response token usage multiplied by the published model rates, plus "
            "hosted-container time estimated per minute with a five-minute minimum."
        ),
        "model_rates_usd_per_1m_tokens": {
            model: {name: float(value) for name, value in rates.items()}
            for model, rates in MODEL_PRICING_USD_PER_1M.items()
        },
        "long_context": {
            "threshold_input_tokens_per_request": LONG_CONTEXT_THRESHOLD_TOKENS,
            "input_multiplier": 2.0,
            "output_multiplier": 1.5,
        },
        "container_rates_usd_per_20_minutes": {
            memory: float(value)
            for memory, value in CONTAINER_PRICE_USD_PER_20_MINUTES.items()
        },
        "container_minimum_billed_minutes": 5,
        "limitations": (
            "This is an auditable estimate, not an invoice. Account-specific data "
            "residency uplifts, credits, negotiated pricing, and unreported usage "
            "cannot be inferred locally; cost_complete is false when a call cannot "
            "be priced."
        ),
    }
