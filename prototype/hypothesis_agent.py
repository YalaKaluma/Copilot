"""Live pricing-opportunity discovery from SKAI pricing evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from skai_service import SkaiGrowthService


HYPOTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "scope_summary": {"type": "string"},
        "data_limitations": {"type": "array", "items": {"type": "string"}},
        "hypotheses": {
            "type": "array",
            "minItems": 2,
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "direction": {"type": "string", "enum": ["Increase price", "Decrease price"]},
                    "statement": {"type": "string"},
                    "opportunity": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "priority": {"type": "integer", "minimum": 0, "maximum": 100},
                    "estimated_value": {"type": "string"},
                    "value_basis": {"type": "string"},
                    "evidence_status": {"type": "string", "enum": ["Supported", "Mixed", "Not supported"]},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["Support", "Counterevidence"]},
                                "finding": {"type": "string"},
                                "interpretation": {"type": "string"},
                                "strength": {"type": "string", "enum": ["Strong", "Moderate", "Weak"]},
                                "source": {"type": "string", "enum": ["Market Landscape", "Brand Ladder", "Price Pack Curve"]},
                                "scope": {"type": "string"},
                            },
                            "required": ["direction", "finding", "interpretation", "strength", "source", "scope"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "direction", "statement", "opportunity", "confidence", "priority", "estimated_value", "value_basis", "evidence_status", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scope_summary", "data_limitations", "hypotheses"],
    "additionalProperties": False,
}


@dataclass
class PricingHypothesisAgent:
    service: SkaiGrowthService
    client: OpenAI
    model: str

    def investigate(self, *, brand: str | None, sku_id: str | None, retailer: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        """Collect live SKAI evidence and turn it into decision hypotheses."""
        retailer_filter = [retailer] if retailer else []
        sku_filter = [sku_id] if sku_id else []
        brand_filter = [brand] if brand else []

        # Keep competitive benchmarks in the ladder and landscape. Brand/SKU are
        # supplied as the analytical focus to the model, not used to erase peers.
        source_calls = {
            "market_landscape_overall": lambda: self.service.get_market_landscape(
                split_by="brand"
            ),
            "brand_ladder_overall": lambda: self.service.get_price_ladder(),
            "price_pack_curve": lambda: self.service.get_price_pack_curve(
                brands=brand_filter, sku_ids=sku_filter
            ),
        }
        if retailer:
            source_calls["market_landscape_selected_retailer"] = (
                lambda: self.service.get_market_landscape(
                    split_by="brand", retailers=retailer_filter
                )
            )
            source_calls["brand_ladder_selected_retailer"] = (
                lambda: self.service.get_price_ladder(retailers=retailer_filter)
            )
        raw: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for source, call in source_calls.items():
            try:
                raw[source] = call()
            except Exception as exc:
                errors[source] = str(exc)
        if not raw:
            return (
                {
                    "scope_summary": "No SKAI pricing evidence source returned data.",
                    "data_limitations": [
                        f'{source.replace("_", " ").title()}: {error}'
                        for source, error in errors.items()
                    ],
                    "hypotheses": [],
                },
                {"source_errors": errors},
            )
        if errors:
            raw["source_errors"] = errors
        compact = {
            key: self._compact(value)
            for key, value in raw.items()
            if key != "source_errors"
        }
        if errors:
            compact["unavailable_sources"] = errors
        scope = {
            "brand": brand or "All brands",
            "sku_id": sku_id or "All SKUs",
            "retailer": retailer or "All retailers",
            "scope_note": (
                "Retailer applies to Market Landscape and Brand Ladder. "
                "The Price Pack Curve endpoint supports brand/SKU but not retailer."
            ),
        }
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a rigorous RGM pricing hypothesis agent. Return exactly two directional hypotheses and no other commercial lever: H-PRICE-UP tests an INCREASE in price; H-PRICE-DOWN tests a DECREASE in price. "
                        "Use pricing language only. Do not propose promotion mechanics, promotional frequency, trade terms, assortment, mix actions, or generic audits as the opportunity. "
                        "Every hypothesis must contain supporting evidence and counterevidence when the data allows it. Weak or missing evidence should lower confidence, not create a different hypothesis. Never invent elasticity, causality, willingness to pay, financial value, or missing fields. "
                        "Assess competitive price positioning versus SKUs/brands, growth patterns, share patterns, within-brand pack-price consistency, and differences between overall-market and selected-retailer results. "
                        "Use Market Landscape for share/growth/market price context, Brand Ladder for competitive average-price positioning, and Price Pack Curve for pack architecture. "
                        "Average prices can reflect pack and mix. Estimated value must be 'Not quantified' unless the payload directly supports a defensible value; explain the basis. "
                        "Unavailable or empty sources are data limitations and must never be cited as positive or negative proof. If selected SKU ownership is false or unverified, explicitly make that strong counterevidence for both actions. "
                        "Priority combines evidence confidence, potential materiality, and actionability. Findings must cite actual values from the payload."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"selected_scope": scope, "skai_evidence": compact}, default=str),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "pricing_hypotheses", "strict": True, "schema": HYPOTHESIS_SCHEMA},
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The pricing hypothesis agent returned no result.")
        return json.loads(content), raw

    @staticmethod
    def _compact(payload: dict[str, Any]) -> dict[str, Any]:
        """Keep the response grounded while limiting model input size."""
        compact: dict[str, Any] = {}
        for key in ("summary", "kpis", "filters_applied", "filtersApplied"):
            if key in payload:
                compact[key] = payload[key]
        rows = payload.get("rows")
        data = payload.get("data")
        if isinstance(rows, list):
            compact["rows"] = rows[:150]
        if isinstance(data, list):
            compact["data"] = data[:150]
        if not compact:
            return {"payload_excerpt": json.dumps(payload, default=str)[:45_000]}
        return compact
