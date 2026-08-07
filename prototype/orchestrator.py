"""Turn a business question into a small, inspectable SKAI execution plan."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI


AXES = [
    "retailer",
    "brand",
    "sku",
    "channel",
    "duration",
    "discount_depth",
    "time_since_last_promo",
]
MARKET_SPLITS = [
    "brand",
    "category",
    "sub_category",
    "manufacturer",
    "segment",
    "sub_segment",
    "pack_size_range",
    "price_tier",
]

GUIDANCE_DIR = Path(__file__).with_name("guidance")

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["execute", "clarify", "unsupported"],
        },
        "clarification_question": {"type": ["string", "null"]},
        "interpretation": {"type": "string"},
        "limitation": {"type": ["string", "null"]},
        "steps": {"type": "array", "items": {"type": "string"}},
        "tool": {
            "type": "string",
            "enum": ["none", "get_promo_heatmap", "get_market_landscape"],
        },
        "arguments": {
            "type": "object",
            "properties": {
                "x_dim_kind": {"type": "string", "enum": AXES},
                "y_dim_kind": {"type": "string", "enum": AXES},
                "market": {"type": ["string", "null"]},
                "period_start": {"type": ["string", "null"]},
                "period_end": {"type": ["string", "null"]},
                "start_date": {"type": ["string", "null"]},
                "end_date": {"type": ["string", "null"]},
                "brands": {"type": "array", "items": {"type": "string"}},
                "categories": {"type": "array", "items": {"type": "string"}},
                "subcategories": {"type": "array", "items": {"type": "string"}},
                "retailers": {"type": "array", "items": {"type": "string"}},
                "channels": {"type": "array", "items": {"type": "string"}},
                "sku_ids": {"type": "array", "items": {"type": "string"}},
                "duration_bin": {"type": "array", "items": {"type": "string"}},
                "depth_bin": {"type": "array", "items": {"type": "string"}},
                "promo_tactics": {"type": "array", "items": {"type": "string"}},
                "comparison_axes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x_dim_kind": {"type": "string", "enum": AXES},
                            "y_dim_kind": {"type": "string", "enum": AXES},
                        },
                        "required": ["x_dim_kind", "y_dim_kind"],
                        "additionalProperties": False,
                    },
                },
                "pack_size_range_values": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "price_tiers": {"type": "array", "items": {"type": "string"}},
                "price_metric": {
                    "type": "string",
                    "enum": ["price_per_unit", "price_per_scaled_volume"],
                },
                "split_by": {"type": "string", "enum": MARKET_SPLITS},
                "comparison_splits": {
                    "type": "array",
                    "items": {"type": "string", "enum": MARKET_SPLITS},
                },
                "compare_by_retailer": {"type": "boolean"},
            },
            "required": [
                "x_dim_kind",
                "y_dim_kind",
                "market",
                "period_start",
                "period_end",
                "start_date",
                "end_date",
                "brands",
                "categories",
                "subcategories",
                "retailers",
                "channels",
                "sku_ids",
                "duration_bin",
                "depth_bin",
                "promo_tactics",
                "comparison_axes",
                "pack_size_range_values",
                "price_tiers",
                "price_metric",
                "split_by",
                "comparison_splits",
                "compare_by_retailer",
            ],
            "additionalProperties": False,
        },
    },
    "required": [
        "decision",
        "clarification_question",
        "interpretation",
        "limitation",
        "steps",
        "tool",
        "arguments",
    ],
    "additionalProperties": False,
}


@dataclass
class Orchestrator:
    client: OpenAI
    model: str

    def build_plan(
        self,
        question: str,
        filter_values: dict[str, Any] | None = None,
        conversation_context: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        available = json.dumps(filter_values or {}, default=str)[:20_000]
        recent_context = json.dumps(
            (conversation_context or [])[-6:], default=str
        )[:12_000]
        guidance = (GUIDANCE_DIR / "orchestrator.md").read_text(encoding="utf-8")
        tool_guidance = (GUIDANCE_DIR / "heatmap_tool.md").read_text(
            encoding="utf-8"
        )
        market_guidance = (GUIDANCE_DIR / "market_landscape_tool.md").read_text(
            encoding="utf-8"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": f"{guidance}\n\n{tool_guidance}\n\n{market_guidance}",
                },
                {
                    "role": "user",
                    "content": (
                        f"Recent conversation:\n{recent_context}\n\n"
                        f"Current question:\n{question}\n\n"
                        f"Available filters:\n{available}"
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "skai_execution_plan",
                    "strict": True,
                    "schema": PLAN_SCHEMA,
                },
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The orchestrator returned an empty plan.")
        plan = json.loads(content)
        self._normalize_filter_values(plan, filter_values or {})
        return plan

    @staticmethod
    def _normalize_filter_values(
        plan: dict[str, Any], filter_values: dict[str, Any]
    ) -> None:
        """Match user-supplied filter spelling/case to SKAI's catalog values."""
        catalog = filter_values.get("filters", filter_values)
        arguments = plan.get("arguments", {})

        def available_values(key: str) -> list[Any] | None:
            if not isinstance(catalog, dict):
                return None
            aliases = {
                "retailers": ("retailers", "retailer_groups"),
                "subcategories": ("subcategories", "sub_categories"),
                "pack_size_range_values": (
                    "pack_size_range_values",
                    "pack_size_ranges",
                ),
            }
            for candidate in aliases.get(key, (key,)):
                values = catalog.get(candidate)
                if isinstance(values, list) and values:
                    return values
            return None

        for key in (
            "brands",
            "categories",
            "subcategories",
            "retailers",
            "channels",
            "sku_ids",
            "pack_size_range_values",
            "price_tiers",
        ):
            available = available_values(key)
            requested = arguments.get(key)
            if not available or not requested:
                continue
            canonical = {str(value).casefold(): value for value in available}
            arguments[key] = [
                canonical.get(str(value).casefold(), value) for value in requested
            ]

        # Retailer is a Market Landscape filter, not a group-by dimension. An
        # empty selection with compare_by_retailer means compare every group.
        if arguments.get("compare_by_retailer") and not arguments.get("retailers"):
            retailers = available_values("retailers")
            if retailers:
                arguments["retailers"] = retailers
