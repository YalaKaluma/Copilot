"""Live pricing-opportunity discovery from SKAI pricing evidence."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from skai_service import SkaiGrowthService


GUIDANCE_FILE = Path(__file__).with_name("guidance") / "pricing_hypothesis_agent.md"


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
                                "source": {"type": "string", "enum": ["Market Landscape", "Price Ladder", "Price Pack Curve"]},
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

    def investigate(
        self,
        *,
        brand: str | None,
        sku_id: str | None,
        retailer: str | None,
        comparison_retailers: list[str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Collect live SKAI evidence and turn it into decision hypotheses."""
        retailer_filter = [retailer] if retailer else []
        brand_filter = [brand] if brand else []

        # Keep competitive benchmarks in the ladder and landscape. Brand/SKU are
        # supplied as the analytical focus to the model, not used to erase peers.
        source_calls = {
            "market_landscape_overall": lambda: self.service.get_market_landscape(
                split_by="brand"
            ),
            "price_ladder_overall": lambda: self.service.get_price_ladder(),
            "price_pack_curve": lambda: self.service.get_price_pack_curve(
                brands=brand_filter
            ),
        }
        if retailer:
            source_calls["market_landscape_selected_retailer"] = (
                lambda: self.service.get_market_landscape(
                    split_by="brand", retailers=retailer_filter
                )
            )
            source_calls["price_ladder_selected_retailer"] = (
                lambda: self.service.get_price_ladder(retailers=retailer_filter)
            )
        for peer_retailer in (comparison_retailers or [])[:4]:
            source_calls[f"market_landscape_peer::{peer_retailer}"] = (
                lambda peer=peer_retailer: self.service.get_market_landscape(
                    split_by="brand", retailers=[peer]
                )
            )
            source_calls[f"price_ladder_peer::{peer_retailer}"] = (
                lambda peer=peer_retailer: self.service.get_price_ladder(
                    retailers=[peer]
                )
            )
        raw: dict[str, Any] = {}
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=min(6, len(source_calls))) as executor:
            futures = {
                executor.submit(call): source for source, call in source_calls.items()
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    raw[source] = future.result()
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
            "comparison_retailers": (comparison_retailers or [])[:4],
            "scope_note": (
                "Retailer applies to Market Landscape and Price Ladder. "
                "Price Pack Curve is retrieved for the full selected brand so the "
                "selected SKU can be assessed against its same-brand pack architecture; "
                "it does not support retailer filtering."
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
                        "Assess competitive price positioning versus SKUs/brands, growth patterns, share patterns, within-brand pack-price consistency, and differences across the selected and comparison retailers. The selected SKU is the analytical focus inside the full-brand Price Pack Curve; compare its price with relevant same-brand pack sizes and explain whether the internal architecture is coherent. "
                        "Use Market Landscape for share/growth/market price context, Price Ladder for competitive average-price positioning, and Price Pack Curve for pack architecture. "
                        "Evidence-card rules learned from reviewer feedback: each card must contain one coherent signal only. Never combine growth and share in one card when they point in opposite directions; create separate cards on opposite sides or omit the ambiguous combination. Say 'sales growth' or 'volume growth', never the vague word 'performance'. Use Price Ladder as the primary source for competitive positioning and check whether positioning is consistent across comparison retailers. Avoid unclear claims such as 'not an unambiguous low-price position'; instead state the exact relevant peer gap and its implication. "
                        "Market Landscape does not support SKU grouping in this API. Use it for brand growth/share; use Price Pack Curve for SKU-level growth and pack architecture. "
                        "Average prices can reflect pack and mix. Estimated value must be 'Not quantified' unless the payload directly supports a defensible value; explain the basis. "
                        "Unavailable or empty sources are data limitations and must never be cited as positive or negative proof. If selected SKU ownership is false or unverified, explicitly make that strong counterevidence for both actions. "
                        "Priority combines evidence confidence, potential materiality, and actionability. Findings must cite actual values from the payload.\n\n"
                        + GUIDANCE_FILE.read_text(encoding="utf-8")
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
