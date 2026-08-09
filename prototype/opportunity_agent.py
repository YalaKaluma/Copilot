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

SCENARIO_COMPARISON_SCHEMA = {
    "type": "object",
    "properties": {
        "scenario_assessments": {
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
                    "verdict": {"type": "string"},
                    "pros": {"type": "array", "items": {"type": "string"}},
                    "cons": {"type": "array", "items": {"type": "string"}},
                    "evidence_fit": {"type": "string"},
                    "best_use_case": {"type": "string"},
                },
                "required": [
                    "name", "verdict", "pros", "cons", "evidence_fit",
                    "best_use_case",
                ],
                "additionalProperties": False,
            },
        },
        "recommended_scenario": {
            "type": "string",
            "enum": ["Conservative", "Balanced", "Ambitious"],
        },
        "recommendation_reason": {"type": "string"},
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "scenario_assessments", "recommended_scenario",
        "recommendation_reason", "caveats",
    ],
    "additionalProperties": False,
}


@dataclass
class PricingOpportunityAgent:
    service: SkaiGrowthService
    client: OpenAI
    model: str

    def compare_existing_scenarios(
        self, opportunity: dict[str, Any]
    ) -> dict[str, Any]:
        """Add the full decision comparison to scenarios already simulated."""
        hypothesis = opportunity.get("hypothesis", {})
        base_row = opportunity.get("simulator_base_row") or {}
        scenarios = opportunity.get("scenarios") or []
        if not base_row or len(scenarios) != 3:
            raise ValueError("Three completed simulations are required for comparison.")
        for scenario in scenarios:
            summary = scenario.get("raw_summary") or {}
            for field, source_key in (
                ("revenue_delta_pct", "sales_delta_pct"),
                ("margin_delta_pct", "margin_delta_pct"),
                ("volume_delta_pct", "volume_delta_pct"),
            ):
                refreshed = self._summary_metric(summary, [], source_key)
                if refreshed is not None:
                    scenario[field] = refreshed
        return self._compare_scenarios(
            opportunity, hypothesis, base_row, scenarios
        )

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
        proposal = self._propose_prices(
            opportunity, hypothesis, row, current_price
        )
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
            simulation_rows = simulation.get("rows") or []
            scenarios.append(
                {
                    "name": scenario["name"],
                    "reason": scenario["reason"],
                    "current_price": current_price,
                    "new_price": new_price,
                    "price_change_pct": (new_price / current_price - 1) * 100,
                    "revenue_delta_pct": self._summary_metric(
                        summary, simulation_rows, "sales_delta_pct"
                    ),
                    "margin_delta_pct": self._summary_metric(
                        summary, simulation_rows, "margin_delta_pct"
                    ),
                    "volume_delta_pct": self._summary_metric(
                        summary, simulation_rows, "volume_delta_pct"
                    ),
                    "currency": summary.get("currency"),
                    "raw_summary": summary,
                }
            )
        comparison = self._compare_scenarios(opportunity, hypothesis, row, scenarios)
        return {
            "rationale": proposal["rationale"],
            "base_row": row,
            "scenarios": scenarios,
            "comparison": comparison,
        }

    @staticmethod
    def _summary_metric(
        summary: dict[str, Any], rows: list[dict[str, Any]], key: str
    ) -> float | None:
        """Use tenant KPIs first, then summary and row-level margin values."""
        own_kpis = summary.get("kpis_own") or {}
        value = own_kpis.get(key)
        if value is None:
            value = summary.get(key)
        if value is not None:
            return float(value)
        if key != "margin_delta_pct":
            return None
        eligible = [
            row for row in rows
            if row.get("is_produced_by_tenant", True)
            and row.get("margin_value_base") is not None
            and row.get("margin_value_new") is not None
        ]
        if not eligible:
            return None
        base_margin = sum(float(row["margin_value_base"]) for row in eligible)
        new_margin = sum(float(row["margin_value_new"]) for row in eligible)
        return None if base_margin == 0 else (new_margin / base_margin - 1) * 100

    def _compare_scenarios(
        self,
        opportunity: dict[str, Any],
        hypothesis: dict[str, Any],
        base_row: dict[str, Any],
        scenarios: list[dict[str, Any]],
    ) -> dict[str, Any]:
        clean_scenarios = [
            {key: value for key, value in scenario.items() if key != "raw_summary"}
            for scenario in scenarios
        ]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior RGM decision agent. Compare all three live "
                        "SKAI pricing simulations and recommend one. For each move, "
                        "explain concrete pros, cons, evidence fit, and when it would be "
                        "the right choice. Consider every available lens: revenue, margin, "
                        "volume and guardrails; accepted supporting and counterevidence; "
                        "selected-retailer versus overall and peer-retailer positioning; "
                        "competitive Price Ladder signals; SKU and brand growth/share; "
                        "same-brand pack-price architecture; current price-point logic; "
                        "elasticity quality and model caveats. Do not invent missing margin "
                        "or other metrics. If margin is unavailable, say so and base the "
                        "decision on available outcomes. Be commercially specific and "
                        "make trade-offs explicit rather than repeating the table."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "decision_context": {
                                key: opportunity.get(key)
                                for key in (
                                    "objective", "max_volume_loss", "minimum_margin",
                                    "protected", "excluded", "timing",
                                )
                            },
                            "accepted_hypothesis": hypothesis,
                            "simulator_context": {
                                key: base_row.get(key)
                                for key in (
                                    "sku_id", "retailer", "channel", "old_price",
                                    "base_non_promo_price", "own_elasticity",
                                    "elasticity_quality_flag", "elasticity_quality_score",
                                    "elasticity_quality_warnings",
                                )
                            },
                            "simulated_scenarios": clean_scenarios,
                        },
                        default=str,
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "pricing_scenario_comparison",
                    "strict": True,
                    "schema": SCENARIO_COMPARISON_SCHEMA,
                },
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The scenario comparison agent returned no result.")
        return json.loads(content)

    def _propose_prices(
        self,
        opportunity: dict[str, Any],
        hypothesis: dict[str, Any],
        base_row: dict[str, Any],
        current_price: float,
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
                            "decision_context": {
                                key: opportunity.get(key)
                                for key in (
                                    "objective", "max_volume_loss", "minimum_margin",
                                    "protected", "excluded", "timing",
                                )
                            },
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
