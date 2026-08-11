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
            "minItems": 1,
            "maxItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "sku_id": {"type": "string"},
                    "retailer": {"type": "string"},
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
                "required": ["id", "sku_id", "retailer", "direction", "statement", "opportunity", "confidence", "priority", "estimated_value", "value_basis", "evidence_status", "evidence"],
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
        if sku_id:
            source_calls["market_landscape_selected_sku_overall"] = (
                lambda: self.service.get_market_landscape(
                    split_by="brand", sku_ids=[sku_id]
                )
            )
        if retailer:
            source_calls["market_landscape_selected_retailer"] = (
                lambda: self.service.get_market_landscape(
                    split_by="brand", retailers=retailer_filter
                )
            )
            source_calls["price_ladder_selected_retailer"] = (
                lambda: self.service.get_price_ladder(retailers=retailer_filter)
            )
            if sku_id:
                source_calls["market_landscape_selected_sku_retailer"] = (
                    lambda: self.service.get_market_landscape(
                        split_by="brand",
                        sku_ids=[sku_id],
                        retailers=retailer_filter,
                    )
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
                        "You are a rigorous RGM pricing hypothesis agent. Internally evaluate both an INCREASE and a DECREASE in price for the selected SKU-retailer combination, then return exactly ONE hypothesis: the direction with the higher evidence-based probability. Never return both directions for the same combination. Use H-PRICE-UP for an increase or H-PRICE-DOWN for a decrease, and copy the selected sku_id and retailer exactly into the output. "
                        "Use pricing language only. Do not propose promotion mechanics, promotional frequency, trade terms, assortment, mix actions, or generic audits as the opportunity. "
                        "Every hypothesis must contain supporting evidence and counterevidence when the data allows it. Weak or missing evidence should lower confidence, not create a different hypothesis. Never invent elasticity, causality, willingness to pay, financial value, or missing fields. "
                        "Assess competitive price positioning versus SKUs/brands, growth patterns, share patterns, within-brand pack-price consistency, and differences across the selected and comparison retailers. The selected SKU is the analytical focus inside the full-brand Price Pack Curve; compare its price with relevant same-brand pack sizes and explain whether the internal architecture is coherent. "
                        "Use Market Landscape for share/growth/market price context, Price Ladder for competitive average-price positioning, and Price Pack Curve for pack architecture. "
                        "Evidence-card rules learned from reviewer feedback: each card must contain one coherent signal only. Never combine growth and share in one card when they point in opposite directions; create separate cards on opposite sides or omit the ambiguous combination. Say 'sales growth' or 'volume growth', never the vague word 'performance'. Use Price Ladder as the primary source for competitive positioning and check whether positioning is consistent across comparison retailers. Avoid unclear claims such as 'not an unambiguous low-price position'; instead state the exact relevant peer gap and its implication. "
                        "For SKU-level Market Landscape evidence, use the selected-SKU-filtered source and explicitly compare that SKU's growth with the total brand at the selected retailer and overall market. Lead with the selected-retailer observation, then compare with overall and peer retailers. Label every price or growth figure as selected-retailer, overall-market, or peer-retailer. "
                        "For Price Pack Curve, inspect the `skus` records behind neighboring pack points. Use explicit product/form/format differences visible in SKU IDs or names to qualify comparisons. If similar sizes are both above and below the selected price, say the architecture is inconsistent and explain exactly that the price sequence is not monotonic; describe upward headroom as limited, not broad. Do not assume an abbreviation's meaning unless the SKU name or identifier makes the distinction reasonably explicit. "
                        "Translate technical Price Ladder fields into plain commercial language. Do not say 'retailer-gap contribution' without explanation; say that a retailer prices the brand above or below its overall benchmark and give the magnitude and basis. "
                        "Average prices can reflect pack and mix. Estimated value must be 'Not quantified' unless the payload directly supports a defensible value; explain the basis. "
                        "Unavailable or empty sources are data limitations and must never be cited as positive or negative proof. If selected SKU ownership is false or unverified, explicitly make that strong counterevidence for both actions. "
                        "Confidence is the calibrated probability that the surfaced direction is the better of the two price actions given available evidence. Use the full scale and do not default to the low 60s: 50-59 means marginal evidence or an almost even choice; 60-69 means mixed evidence with a slight directional advantage; 70-79 means multiple reasonably consistent signals with manageable counterevidence; 80-89 means strong agreement across at least two relevant sources with limited counterevidence; 90-95 is reserved for unusually complete, consistent, SKU-retailer-specific evidence. Reduce confidence materially for missing sources, brand-level proxies, weak SKU mapping, contradictory retailer patterns, or non-comparable packs. Scores above 95 are not credible for these observational data. Priority must equal confidence so hypotheses can be ranked consistently across SKU-retailer combinations. The opportunity field must be one concise pricing-action sentence; put the analytical rationale in the statement field. Findings must cite actual values from the payload.\n\n"
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
