"""Turn an accepted pricing hypothesis into live SKAI simulation scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from skai_service import SkaiGrowthService


PRICE_SCENARIO_SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "scenarios": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": ["Conservative", "Balanced", "Ambitious"],
                    },
                    "new_price": {"type": "number", "exclusiveMinimum": 0},
                    "reason": {"type": "string"},
                },
                "required": ["name", "new_price", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rationale", "scenarios"],
    "additionalProperties": False,
}


@dataclass
class PricingOpportunityAgent:
    service: SkaiGrowthService
    client: OpenAI
    model: str

    def run_scenarios(self, opportunity: dict[str, Any]) -> dict[str, Any]:
        hypothesis = opportunity.get("hypothesis", {})
        scope = opportunity.get("scope", {})
        brand = scope.get("brand")
        sku_id = hypothesis.get("sku_id") or scope.get("sku")
        retailer = hypothesis.get("retailer") or scope.get("retailer")
        if not sku_id or not retailer:
            raise ValueError("The opportunity does not contain one SKU and retailer.")

        base = self.service.get_simulator_base(
            brands=[brand] if brand else None,
            sku_ids=[sku_id],
            retailers=[retailer],
        )
        rows = base.get("rows") or base.get("data") or []
        row = next(
            (
                item
                for item in rows
                if item.get("sku_id") == sku_id
                and str(item.get("retailer", "")).upper() == str(retailer).upper()
            ),
            None,
        )
        if row is None:
            raise ValueError(
                f"SKAI simulator returned no base row for {sku_id} at {retailer}."
            )
        if not row.get("scenario_planning_ready", True):
            raise ValueError("This SKU-retailer row is not ready for scenario planning.")

        current_price = float(row.get("base_non_promo_price") or row["old_price"])
        proposal = self._propose_prices(hypothesis, row, current_price)
        scenarios: list[dict[str, Any]] = []
        for scenario in proposal["scenarios"]:
            new_price = round(float(scenario["new_price"]), 4)
            payload = {
                "price_changes": [
                    {
                        "sku_id": sku_id,
                        "retailer": row["retailer"],
                        "channel": row["channel"],
                        "new_price": new_price,
                        "delisted": False,
                    }
                ],
                "use_cross_elasticities": False,
                "impacted_only": False,
                "horizon": "short_run",
            }
            simulation = self.service.run_price_simulation(
                payload,
                brands=[brand] if brand else None,
                sku_ids=[sku_id],
                retailers=[retailer],
            )
            summary = simulation.get("summary") or {}
            scenarios.append(
                {
                    "name": scenario["name"],
                    "reason": scenario["reason"],
                    "current_price": current_price,
                    "new_price": new_price,
                    "price_change_pct": (new_price / current_price - 1) * 100,
                    "revenue_delta_pct": summary.get("sales_delta_pct"),
                    "margin_delta_pct": summary.get("margin_delta_pct"),
                    "volume_delta_pct": summary.get("volume_delta_pct"),
                    "currency": summary.get("currency"),
                    "raw_summary": summary,
                }
            )
        return {
            "rationale": proposal["rationale"],
            "base_row": row,
            "scenarios": scenarios,
        }

    def _propose_prices(
        self, hypothesis: dict[str, Any], base_row: dict[str, Any], current_price: float
    ) -> dict[str, Any]:
        direction = hypothesis.get("direction", "Increase price")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an RGM pricing scenario designer. Read the accepted "
                        "hypothesis and its evidence, then suggest exactly three distinct "
                        "shelf prices to test: Conservative, Balanced, and Ambitious. "
                        "All prices must follow the accepted direction, remain within 20% "
                        "of the current shelf price, and use commercially sensible price "
                        "points. Do not predict outcomes; the SKAI simulator will do that."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "direction": direction,
                            "current_shelf_price": current_price,
                            "hypothesis": hypothesis,
                            "simulator_base_context": {
                                key: base_row.get(key)
                                for key in (
                                    "sku_id", "retailer", "channel", "old_price",
                                    "base_non_promo_price", "base_promo_price",
                                    "own_elasticity", "elasticity_quality_flag",
                                    "elasticity_quality_score",
                                )
                            },
                        },
                        default=str,
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "pricing_scenario_prices",
                    "strict": True,
                    "schema": PRICE_SCENARIO_SCHEMA,
                },
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The scenario agent returned no price suggestions.")
        proposal = json.loads(content)
        self._validate_prices(proposal, direction, current_price)
        return proposal

    @staticmethod
    def _validate_prices(
        proposal: dict[str, Any], direction: str, current_price: float
    ) -> None:
        prices = [float(item["new_price"]) for item in proposal["scenarios"]]
        if len(set(prices)) != 3:
            raise ValueError("The agent did not return three distinct price points.")
        increasing = direction == "Increase price"
        if any((price <= current_price if increasing else price >= current_price) for price in prices):
            raise ValueError("A suggested price conflicts with the accepted direction.")
        if any(abs(price / current_price - 1) > 0.20 for price in prices):
            raise ValueError("A suggested price exceeds the 20% scenario boundary.")
