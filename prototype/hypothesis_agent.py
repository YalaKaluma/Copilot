"""Live pricing-opportunity discovery from SKAI pricing evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from skai_service import SkaiError, SkaiGrowthService


HYPOTHESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "scope_summary": {"type": "string"},
        "data_limitations": {"type": "array", "items": {"type": "string"}},
        "hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
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
                "required": ["id", "statement", "opportunity", "confidence", "priority", "estimated_value", "value_basis", "evidence_status", "evidence"],
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
            "market_landscape": lambda: self.service.get_market_landscape(
                split_by="brand", retailers=retailer_filter
            ),
            "brand_ladder": lambda: self.service.get_price_ladder(
                retailers=retailer_filter
            ),
            "price_pack_curve": lambda: self.service.get_price_pack_curve(
                brands=brand_filter, sku_ids=sku_filter
            ),
        }
        raw: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for source, call in source_calls.items():
            try:
                raw[source] = call()
            except SkaiError as exc:
                errors[source] = str(exc)
        if not raw:
            joined = "; ".join(f"{source}: {error}" for source, error in errors.items())
            raise SkaiError(f"No pricing evidence source was available. {joined}")
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
                        "You are a rigorous RGM pricing hypothesis agent. Identify 2-5 commercially distinct pricing opportunities from the supplied live SKAI data. "
                        "Every hypothesis must contain both supporting evidence and counterevidence when the data allows it. Never invent elasticity, causality, willingness to pay, financial value, or missing fields. "
                        "Use Market Landscape for share/growth/market price context, Brand Ladder for competitive average-price positioning, and Price Pack Curve for pack architecture. "
                        "Average prices can reflect pack and mix. Estimated value must be 'Not quantified' unless the payload directly supports a defensible value; explain the basis. "
                        "Unavailable sources are explicitly listed in the payload. Treat each as a data limitation and never claim evidence from it. "
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
