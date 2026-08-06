"""Execute an approved plan and turn the SKAI result into a grounded answer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from skai_service import SkaiGrowthService

GUIDANCE_DIR = Path(__file__).with_name("guidance")


@dataclass
class SkaiAgent:
    skai: SkaiGrowthService
    client: OpenAI
    model: str

    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        if plan.get("decision") != "execute":
            raise ValueError(plan.get("limitation") or "This question is unsupported.")
        tool = plan.get("tool")
        arguments = plan["arguments"]
        if tool == "get_promo_heatmap":
            allowed = {
                "x_dim_kind", "y_dim_kind", "market", "period_start",
                "period_end", "start_date", "end_date", "brands", "categories",
                "subcategories", "retailers", "channels", "sku_ids",
                "duration_bin", "depth_bin", "promo_tactics",
            }
            return self.skai.get_promo_heatmap(
                **{key: value for key, value in arguments.items() if key in allowed}
            )
        if tool == "get_market_landscape":
            allowed = {
                "period_start", "period_end", "sku_ids", "brands", "categories",
                "subcategories", "retailers", "channels",
                "pack_size_range_values", "price_tiers", "price_metric", "split_by",
            }
            base_arguments = {
                key: value for key, value in arguments.items() if key in allowed
            }
            comparison_splits = arguments.get("comparison_splits") or []
            compare_by_retailer = arguments.get("compare_by_retailer", False)
            retailers = base_arguments.get("retailers") or []

            if comparison_splits:
                results = {}
                for split in comparison_splits:
                    split_arguments = {**base_arguments, "split_by": split}
                    selected_brands = split_arguments.get("brands") or []
                    if selected_brands:
                        market_arguments = {**split_arguments, "brands": []}
                        results[split] = {
                            "market": self.skai.get_market_landscape(
                                **market_arguments
                            ),
                            "selected_brand": self.skai.get_market_landscape(
                                **split_arguments
                            ),
                        }
                    else:
                        results[split] = self.skai.get_market_landscape(
                            **split_arguments
                        )
                return {"analysis_mode": "multiple_splits", "results": results}

            if compare_by_retailer and retailers:
                results = {}
                for retailer in retailers:
                    retailer_arguments = {
                        **base_arguments,
                        "retailers": [retailer],
                    }
                    results[retailer] = self.skai.get_market_landscape(
                        **retailer_arguments
                    )
                return {"analysis_mode": "retailer_comparison", "results": results}

            return self.skai.get_market_landscape(**base_arguments)
        raise ValueError(f"Unsupported tool: {tool}")

    def answer(
        self, question: str, plan: dict[str, Any], result: dict[str, Any]
    ) -> str:
        # Bound the LLM payload while keeping the API summary and a representative sample.
        if plan.get("tool") == "get_market_landscape":
            if result.get("analysis_mode"):
                def compact(value: dict[str, Any]) -> dict[str, Any]:
                    return {
                        "summary": value.get("summary"),
                        "rows": (value.get("rows") or [])[:100],
                        "envelope": value.get("envelope"),
                    }

                compact_result = {
                    "analysis_mode": result["analysis_mode"],
                    "results": {
                        key: (
                            {
                                "market": compact(value["market"]),
                                "selected_brand": compact(
                                    value["selected_brand"]
                                ),
                            }
                            if "market" in value and "selected_brand" in value
                            else compact(value)
                        )
                        for key, value in result.get("results", {}).items()
                    },
                }
            else:
                compact_result = {
                    "summary": result.get("summary"),
                    "rows": (result.get("rows") or [])[:100],
                    "envelope": result.get("envelope"),
                }
            guidance_file = "category_agent.md"
        else:
            compact_result = {
                "summary": result.get("summary"),
                "data": (result.get("data") or [])[:100],
                "envelope": result.get("envelope"),
            }
            guidance_file = "promo_agent.md"
        guidance = (GUIDANCE_DIR / guidance_file).read_text(encoding="utf-8")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": guidance,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "plan": plan,
                            "skai_result": compact_result,
                        },
                        default=str,
                    ),
                },
            ],
        )
        return response.choices[0].message.content or "No answer was generated."
