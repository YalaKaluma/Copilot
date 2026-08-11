"""Streamlit-native pricing decision workspace around the existing Copilot."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import date

import streamlit as st

from feedback_export import build_hypothesis_feedback_workbook


HYPOTHESES = [
    {
        "id": "H-01", "priority": 96, "confidence": 87, "value": "€0.8–1.2M",
        "statement": "Selected SKUs are underpriced relative to competitors.",
        "scope": "Vilore · La Costeña · 4 priority SKUs · Total Market",
        "period": "Latest 52 weeks vs prior year", "status": "Supported",
        "summary": "La Costeña retains meaningful price headroom on high-velocity packs without leaving the competitive corridor.",
        "tests": ["Brand price ladder", "SKU price-index comparison", "Retailer dispersion", "Elasticity screen"],
        "missing": "Retailer-specific trade terms and competitor response are not yet modeled.",
        "evidence": [
            ("Price index below branded peers", "Average unit price is 6.8% below the branded peer median.", "Supports", "Strong", "Price ladder"),
            ("Low-elasticity core packs", "Two core SKUs combine above-average velocity with modeled elasticity below 0.8.", "Supports", "Strong", "Pricing simulator"),
            ("Walmart gap is narrower", "At Walmart the price gap is only 1.5%, leaving limited room after retailer economics.", "Contradicts", "Moderate", "Retailer price ladder"),
            ("Competitor reaction unknown", "No forward competitor-price response is available.", "Missing", "Material", "Data limitation"),
        ],
    },
    {
        "id": "H-02", "priority": 89, "confidence": 81, "value": "€0.5–0.9M",
        "statement": "Price increases should be differentiated across SKUs.",
        "scope": "Vilore · La Costeña · Core and premium packs", "period": "Latest 52 weeks",
        "status": "Supported", "summary": "Elasticity and competitive gaps vary too widely for one uniform list-price move.",
        "tests": ["Elasticity segmentation", "Pack-role analysis", "Price-point protection"],
        "missing": "Entry-pack switching behavior requires validation.",
        "evidence": [
            ("Headroom clusters in premium packs", "Premium SKUs show lower elasticity and wider peer gaps.", "Supports", "Strong", "Pricing simulator"),
            ("Entry pack anchors architecture", "The smallest pack is close to a key consumer price point.", "Contradicts", "Strong", "Price ladder"),
        ],
    },
    {
        "id": "H-03", "priority": 77, "confidence": 72, "value": "€0.3–0.6M",
        "statement": "Some retailer–SKU combinations have greater pricing headroom than others.",
        "scope": "La Costeña · 7 retailers", "period": "Latest 26 weeks",
        "status": "Mixed", "summary": "Retailer dispersion suggests targeted action, but coverage is uneven.",
        "tests": ["Retailer ladder", "Distribution-weighted price index"],
        "missing": "Two retailers have incomplete competitor observations.",
        "evidence": [
            ("Headroom at Publix and Albertsons", "Price gaps exceed 5% with stable velocity.", "Supports", "Moderate", "Retailer price ladder"),
            ("Limited evidence at UNFI", "Sparse observations make the apparent headroom unreliable.", "Contradicts", "Moderate", "Coverage audit"),
        ],
    },
]

SCENARIOS = [
    {"name": "Conservative", "action": "+2% on selected low-elasticity SKUs", "revenue": "+€0.7M", "margin": "+€0.55M", "volume": "−0.4%", "risk": "Low", "confidence": "80–88%"},
    {"name": "Balanced", "action": "+4% on low-elasticity SKUs; protect entry pack", "revenue": "+€1.1M", "margin": "+€0.85M", "volume": "−1.1%", "risk": "Medium", "confidence": "72–82%"},
    {"name": "Aggressive", "action": "+6% across premium packs", "revenue": "+€1.2M", "margin": "+€0.92M", "volume": "−2.5%", "risk": "High", "confidence": "58–70%"},
    {"name": "Targeted", "action": "+3–5% by retailer and SKU headroom", "revenue": "+€1.0M", "margin": "+€0.88M", "volume": "−0.8%", "risk": "Medium", "confidence": "76–85%"},
]


def initialize_workspace() -> None:
    st.session_state.setdefault("pricing_dispositions", {})
    st.session_state.setdefault("pricing_opportunities", {})
    st.session_state.setdefault("sell_in_stories", {})
    st.session_state.setdefault("hypothesis_detail", None)
    st.session_state.setdefault("opportunity_detail", None)
    st.session_state.setdefault("story_detail", None)
    st.session_state.setdefault("generated_hypotheses", [])
    st.session_state.setdefault("hypothesis_scan_scope", {})
    st.session_state.setdefault("hypothesis_scan_limitations", [])
    st.session_state.setdefault("hypothesis_raw_evidence", {})
    st.session_state.setdefault("hypothesis_source_errors", {})


def _header(title: str, subtitle: str, eyebrow: str = "Pricing decision workspace") -> None:
    st.markdown(f'<p class="sk-eyebrow">{eyebrow}</p><h1>{title}</h1><p class="sk-subtitle">{subtitle}</p>', unsafe_allow_html=True)


def _card_start(css: str = "sk-card") -> None:
    st.markdown(f'<div class="{css}">', unsafe_allow_html=True)


def _card_end() -> None:
    st.markdown('</div>', unsafe_allow_html=True)


def _display_text(value: object, fallback: str = "") -> str:
    """Return agent text without inline-code highlighting."""
    text = str(value or fallback)
    return text.replace("`", "")


def render_home(connected: bool, tenant: str | None) -> None:
    _header("Pricing workspace", "Your agent-led path from commercial hypothesis to customer-ready action.")
    live_hypotheses = st.session_state.get("generated_hypotheses", [])
    hypotheses_review = sum(
        st.session_state.pricing_dispositions.get(
            hypothesis.get("id", f"LIVE-{index + 1}"), "Review"
        )
        == "Review"
        for index, hypothesis in enumerate(live_hypotheses)
    )
    metrics = [
        ("Hypotheses tested", len(live_hypotheses)), ("Requiring review", hypotheses_review),
        ("Active opportunities", len(st.session_state.pricing_opportunities)),
        ("Recommendations ready", sum(o["status"] == "Recommendation ready" for o in st.session_state.pricing_opportunities.values())),
        ("Sell-in stories", len(st.session_state.sell_in_stories)),
    ]
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.metric(label, value)
    st.subheader("Workspace status")
    st.success("SKAI data connected" if connected else "SKAI connection required")
    st.info("OpenAI configured" if bool(st.session_state.get("workspace_openai_key")) else "OpenAI key is available in Connection settings")
    st.caption("Credentials, API settings and workspace selection are managed on the Connection page.")


def render_hypotheses() -> None:
    selected = st.session_state.hypothesis_detail
    if selected:
        hypothesis = next((h for h in HYPOTHESES if h["id"] == selected), None)
        if hypothesis:
            _render_hypothesis_detail(hypothesis)
            return
    _header("Pricing hypotheses", "Ranked by confidence, value at stake and commercial actionability.")
    for h in sorted(HYPOTHESES, key=lambda item: item["priority"], reverse=True):
        disposition = st.session_state.pricing_dispositions.get(h["id"], "Review")
        with st.container(border=True):
            top, action = st.columns([5, 1])
            with top:
                st.caption(f'{h["id"]} · PRIORITY {h["priority"]} · {h["status"].upper()}')
                st.subheader(h["statement"])
                st.write(h["scope"])
                a, b, c = st.columns(3)
                a.metric("Confidence", f'{h["confidence"]}%')
                b.metric("Value at stake", h["value"])
                c.metric("Disposition", disposition)
            with action:
                if st.button("Open case file", key=f'open-{h["id"]}', use_container_width=True):
                    st.session_state.hypothesis_detail = h["id"]
                    st.rerun()


def _render_hypothesis_detail(h: dict) -> None:
    if st.button("← Back to hypotheses"):
        st.session_state.hypothesis_detail = None
        st.rerun()
    _header(h["statement"], h["summary"], f'{h["id"]} · Structured case file')
    m1, m2, m3 = st.columns(3)
    m1.metric("Confidence", f'{h["confidence"]}%')
    m2.metric("Estimated value", h["value"])
    m3.metric("Priority", h["priority"])
    supporting = [e for e in h["evidence"] if e[2] == "Supports"]
    opposing = [e for e in h["evidence"] if e[2] != "Supports"]
    for title, evidence in (
        ("Supporting evidence", supporting),
        ("Counterevidence & gaps", opposing),
    ):
        st.subheader(title)
        for finding, interpretation, direction, strength, source in evidence:
            with st.container(border=True):
                st.caption(f"{direction.upper()} · {strength} · {source}")
                st.write(_display_text(finding))
                st.write(_display_text(interpretation))
                st.caption(f'{h["scope"]} · {h["period"]}')
    st.subheader("Tests and limitations")
    st.write(" · ".join(h["tests"]))
    st.warning(h["missing"])
    disposition = st.radio("Commercial disposition", ["Pursue as opportunity", "Investigate further", "Monitor", "Reject"], horizontal=True, key=f'disposition-{h["id"]}')
    if st.button("Save disposition", type="primary", use_container_width=True):
        st.session_state.pricing_dispositions[h["id"]] = disposition
        if disposition == "Pursue as opportunity":
            opp_id = f'O-{h["id"].split("-")[-1]}'
            st.session_state.pricing_opportunities.setdefault(opp_id, {
                "id": opp_id, "hypothesis_id": h["id"], "statement": h["statement"], "value": h["value"],
                "status": "Recommendation ready", "owner": "Pricing team", "objective": "Margin",
                "max_volume_loss": "1.5%", "minimum_margin": "€0.6M", "protected": "Entry-price pack",
                "excluded": "None", "timing": "Next list-price window", "selected": "Balanced",
                "scenarios": deepcopy(SCENARIOS),
            })
            st.success(f"Opportunity {opp_id} created with full evidence traceability.")
        else:
            st.success("Disposition saved.")


def _filter_options(filter_values: dict, *keys: str) -> list[str]:
    catalog = filter_values.get("filters", filter_values)
    if not isinstance(catalog, dict):
        return []
    for key in keys:
        values = catalog.get(key)
        if not isinstance(values, list):
            continue
        options: list[str] = []
        for value in values:
            if isinstance(value, dict):
                resolved = next(
                    (
                        value.get(candidate)
                        for candidate in ("id", "value", "code", "name", "label")
                        if value.get(candidate) is not None
                    ),
                    None,
                )
            else:
                resolved = value
            if resolved is not None and str(resolved) not in options:
                options.append(str(resolved))
        if options:
            return options
    return []


def _brand_filter_hierarchy(
    agent, brand: str, catalog_retailers: list[str]
) -> tuple[list[str], list[str], list[str]]:
    """Derive valid brand children because SKAI's filter catalog is flat."""
    tenant = st.session_state.get("selected_tenant_code") or "default"
    cache_key = f"hypothesis_filter_hierarchy:{tenant}:{brand}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict):
        return cached["skus"], cached["retailers"], cached.get("warnings", [])

    warnings: list[str] = []
    valid_skus: list[str] = []
    try:
        curve = agent.service.get_price_pack_curve(brands=[brand])
        for row in curve.get("rows", []):
            for sku in row.get("skus", []):
                sku_id = sku.get("sku_id") if isinstance(sku, dict) else None
                if sku_id and sku_id not in valid_skus:
                    valid_skus.append(sku_id)
    except Exception as exc:
        warnings.append(f"Could not derive brand-specific SKUs: {exc}")

    valid_retailers: list[str] = []

    def retailer_has_brand(retailer: str) -> tuple[str, bool]:
        payload = agent.service.get_market_landscape(
            split_by="brand", brands=[brand], retailers=[retailer]
        )
        return retailer, bool(payload.get("rows", []))

    with ThreadPoolExecutor(max_workers=min(7, max(1, len(catalog_retailers)))) as pool:
        futures = {
            pool.submit(retailer_has_brand, retailer): retailer
            for retailer in catalog_retailers
        }
        for future in as_completed(futures):
            retailer = futures[future]
            try:
                resolved, has_data = future.result()
                if has_data:
                    valid_retailers.append(resolved)
            except Exception as exc:
                warnings.append(f"Could not validate {brand} at {retailer}: {exc}")

    valid_skus = sorted(valid_skus)
    valid_retailers = [
        retailer for retailer in catalog_retailers if retailer in valid_retailers
    ]
    hierarchy = {
        "skus": valid_skus,
        "retailers": valid_retailers,
        "warnings": warnings,
    }
    if not warnings:
        st.session_state[cache_key] = hierarchy
    return valid_skus, valid_retailers, warnings


def _scope_skus(
    agent, brand: str, retailer_ids: list[str], brand_skus: list[str]
) -> tuple[list[str], list[str]]:
    """Return SKUs with data in every selected retailer."""
    if not retailer_ids:
        return [], []
    tenant = st.session_state.get("selected_tenant_code") or "default"
    selection = "|".join(sorted(retailer_ids))
    cache_key = f"hypothesis_scope_skus:{tenant}:{brand}:{selection}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict):
        return cached["skus"], cached.get("warnings", [])

    available_pairs: set[tuple[str, str]] = set()
    warnings: list[str] = []

    def has_scope_data(retailer: str, sku_id: str) -> tuple[str, str, bool]:
        payload = agent.service.get_market_landscape(
            split_by="brand",
            brands=[brand],
            sku_ids=[sku_id],
            retailers=[retailer],
        )
        return retailer, sku_id, bool(payload.get("rows", []))

    pair_count = len(retailer_ids) * len(brand_skus)
    with ThreadPoolExecutor(max_workers=min(14, max(1, pair_count))) as pool:
        futures = {
            pool.submit(has_scope_data, retailer, sku_id): (retailer, sku_id)
            for retailer in retailer_ids
            for sku_id in brand_skus
        }
        for future in as_completed(futures):
            retailer, sku_id = futures[future]
            try:
                resolved_retailer, resolved_sku, has_data = future.result()
                if has_data:
                    available_pairs.add((resolved_retailer, resolved_sku))
            except Exception as exc:
                warnings.append(f"Could not validate {sku_id} at {retailer}: {exc}")

    ordered = [
        sku_id
        for sku_id in brand_skus
        if all((retailer, sku_id) in available_pairs for retailer in retailer_ids)
    ]
    if not warnings:
        st.session_state[cache_key] = {"skus": ordered, "warnings": warnings}
    return ordered, warnings


def render_hypotheses(agent, filter_values: dict) -> None:
    """Run and review live, scope-specific pricing hypotheses."""
    _header(
        "Pricing hypotheses",
        "Select a commercial scope and ask the agent to generate evidence-backed hypotheses.",
    )
    brands = _filter_options(filter_values, "brands")
    catalog_retailers = _filter_options(filter_values, "retailers", "retailer_groups")
    if not brands:
        st.error("SKAI did not return any brands for this workspace.")
        return
    with st.container(border=True):
        st.caption("ANALYSIS SCOPE")
        lever = st.selectbox(
            "RGM lever",
            ["Pricing", "Promo", "Trade terms", "Mix"],
            key="hypothesis_lever",
        )
        if st.session_state.get("hypothesis_brand") not in brands:
            st.session_state["hypothesis_brand"] = brands[0] if brands else None
        brand = st.selectbox("Brand", brands, key="hypothesis_brand")
        with st.spinner("Loading valid retailers and SKUs for this brand..."):
            brand_skus, retailers, hierarchy_warnings = _brand_filter_hierarchy(
                agent, brand, catalog_retailers
            )
        c2, c3 = st.columns(2)
        selected_retailer_state = st.session_state.get("hypothesis_retailers", [])
        valid_selected_retailers = [
            retailer for retailer in selected_retailer_state if retailer in retailers
        ]
        if valid_selected_retailers != selected_retailer_state:
            st.session_state["hypothesis_retailers"] = (
                valid_selected_retailers or retailers[:1]
            )
        selected_retailers = c2.multiselect(
            "Retailers", retailers, default=retailers[:1], key="hypothesis_retailers"
        )
        with st.spinner("Loading SKUs available at every selected retailer..."):
            skus, sku_warnings = _scope_skus(
                agent, brand, selected_retailers, brand_skus
            )
        selected_sku_state = st.session_state.get("hypothesis_skus", [])
        valid_selected_skus = [sku for sku in selected_sku_state if sku in skus]
        if valid_selected_skus != selected_sku_state:
            st.session_state["hypothesis_skus"] = valid_selected_skus or skus[:1]
        selected_skus = c3.multiselect(
            "SKUs", skus, default=skus[:1], key="hypothesis_skus"
        )
        combination_count = len(selected_skus) * len(selected_retailers)
        for warning in [*hierarchy_warnings, *sku_warnings]:
            st.warning(warning)
        st.caption(
            f"{combination_count} SKU-retailer combination(s) selected. The agent "
            "will retain one winning price direction for each combination."
        )
        run_scan = st.button(
            "Generate hypotheses",
            type="primary",
            use_container_width=True,
            disabled=(lever != "Pricing" or combination_count == 0),
        )

    if lever != "Pricing":
        st.info(
            f"{lever} hypothesis logic is not connected yet. This iteration "
            "supports Pricing; the other levers are included to establish the "
            "future workspace structure."
        )
        return

    if run_scan:
        with st.status(
            "Collecting SKAI evidence and testing pricing hypotheses...",
            expanded=True,
        ) as status:
            st.write("Reading Market Landscape")
            st.write("Reading Price Ladder")
            st.write("Reading Price Pack Curve")
            generated, limitations, errors, raw_evidence = [], [], {}, {}
            progress = st.progress(0, text="Starting perimeter scan")
            combinations = [
                (sku_id, retailer_id)
                for sku_id in selected_skus
                for retailer_id in selected_retailers
            ]
            for position, (sku_id, retailer_id) in enumerate(combinations, start=1):
                progress.progress(
                    (position - 1) / len(combinations),
                    text=f"Analyzing {sku_id} at {retailer_id}",
                )
                peers = [
                    candidate for candidate in retailers if candidate != retailer_id
                ][:4]
                scope_key = f"{sku_id} | {retailer_id}"
                try:
                    result, raw = agent.investigate(
                        brand=None if brand == "All brands" else brand,
                        sku_id=sku_id,
                        retailer=retailer_id,
                        comparison_retailers=peers,
                    )
                except Exception as exc:
                    errors[f"{scope_key} / hypothesis generation"] = str(exc)
                    continue
                raw_evidence[scope_key] = raw
                for hypothesis in result.get("hypotheses", []):
                    hypothesis["sku_id"] = sku_id
                    hypothesis["retailer"] = retailer_id
                    hypothesis["id"] = f'{hypothesis.get("id", "H-PRICE")}-{position:03d}'
                    generated.append(hypothesis)
                limitations.extend(
                    f"{scope_key}: {item}"
                    for item in result.get("data_limitations", [])
                )
                errors.update(
                    {f"{scope_key} / {source}": error for source, error in raw.get("source_errors", {}).items()}
                )
            progress.progress(1.0, text="Perimeter scan complete")
            st.session_state.generated_hypotheses = generated
            st.session_state.hypothesis_scan_scope = {
                "brand": brand,
                "skus": selected_skus,
                "retailers": selected_retailers,
                "combination_count": combination_count,
                "lever": lever,
                "summary": f"Generated {len(generated)} ranked hypotheses across {combination_count} selected combinations.",
            }
            st.session_state.hypothesis_scan_limitations = limitations
            st.session_state.hypothesis_raw_evidence = raw_evidence
            st.session_state.hypothesis_source_errors = errors
            status.update(
                label="Hypothesis generation complete",
                state="complete",
                expanded=False,
            )

    hypotheses = sorted(
        st.session_state.generated_hypotheses,
        key=lambda item: item.get("confidence", 0),
        reverse=True,
    )
    if not hypotheses:
        for source, error in st.session_state.hypothesis_source_errors.items():
            st.warning(f"{source}: {error}")
        st.info("Select at least one SKU and retailer, then generate hypotheses.")
        return

    scope = st.session_state.hypothesis_scan_scope
    st.caption(
        f'LAST SCAN - {scope.get("brand")} - {scope.get("combination_count", 0)} COMBINATIONS'
    )
    limitations = st.session_state.hypothesis_scan_limitations
    source_errors = st.session_state.hypothesis_source_errors
    if scope.get("summary") or limitations or source_errors:
        with st.expander("Analysis limitations", expanded=False):
            if scope.get("summary"):
                st.write(_display_text(scope["summary"]))
            for limitation in limitations:
                st.warning(_display_text(limitation))
            for source, error in source_errors.items():
                st.warning(
                    f'{source.replace("_", " ").title()} was unavailable; the scan '
                    f'continued with the remaining sources. {_display_text(error)}'
                )

    for index, hypothesis in enumerate(hypotheses):
        hypothesis_id = hypothesis.get("id") or f"LIVE-{index + 1}"
        label = (
            f'#{index + 1} · {hypothesis.get("direction", "Price adjustment")} · '
            f'{hypothesis.get("sku_id", "SKU")} · {hypothesis.get("retailer", "Retailer")} · '
            f'{hypothesis.get("confidence", 0)}% confidence'
        )
        with st.expander(label, expanded=False):
            st.caption(
                f'{hypothesis_id} - RANK {index + 1} - '
                f'{hypothesis.get("evidence_status", "Mixed").upper()}'
            )
            direction_col, confidence_col = st.columns([4, 1])
            direction_col.markdown(
                f'**Direction: {hypothesis.get("direction", "Pricing adjustment")}**'
            )
            confidence_col.markdown(
                '<div style="text-align:right;font-weight:700">'
                f'{hypothesis.get("confidence", 0)}% confidence</div>',
                unsafe_allow_html=True,
            )
            st.subheader(
                _display_text(hypothesis.get("statement"), "Pricing opportunity")
            )
            st.write(_display_text(hypothesis.get("opportunity")))

            evidence = hypothesis.get("evidence", [])
            supporting = [
                item for item in evidence if item.get("direction") == "Support"
            ]
            opposing = [
                item
                for item in evidence
                if item.get("direction") == "Counterevidence"
            ]
            for title, cards in (
                ("Supporting evidence", supporting),
                ("Counterevidence", opposing),
            ):
                st.subheader(title)
                if not cards:
                    st.caption("No evidence returned for this section.")
                for evidence_card in cards:
                    with st.container(border=True):
                        st.write(
                            _display_text(evidence_card.get("finding"), "Finding")
                        )
                        with st.expander("Evidence details", expanded=False):
                            strength = str(
                                evidence_card.get("strength", "")
                            ).upper()
                            source = _display_text(evidence_card.get("source"))
                            if strength or source:
                                st.caption(
                                    " · ".join(
                                        item for item in (strength, source) if item
                                    )
                                )
                            interpretation = _display_text(
                                evidence_card.get("interpretation")
                            )
                            if interpretation:
                                st.write(interpretation)
                            scope_text = _display_text(evidence_card.get("scope"))
                            if scope_text:
                                st.caption(scope_text)

            accept, reject, _ = st.columns([1, 1, 3])
            if accept.button(
                "Accept opportunity",
                key=f"accept-{hypothesis_id}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.pricing_dispositions[hypothesis_id] = "Accepted"
                opportunity_id = f"O-LIVE-{index + 1}"
                st.session_state.pricing_opportunities[opportunity_id] = {
                    "id": opportunity_id,
                    "hypothesis_id": hypothesis_id,
                    "statement": hypothesis.get("opportunity")
                    or hypothesis.get("statement"),
                    "hypothesis": deepcopy(hypothesis),
                    "value": hypothesis.get("estimated_value", "Not quantified"),
                    "evidence": deepcopy(evidence),
                    "scope": deepcopy(scope),
                    "status": "Awaiting simulation",
                    "owner": "Pricing team",
                    "objective": "Margin",
                    "max_volume_loss": "1.5%",
                    "minimum_margin": "To be defined",
                    "protected": "Entry-price pack",
                    "excluded": "None",
                    "timing": "Next list-price window",
                    "selected": None,
                    "scenarios": [],
                }
                st.session_state.pricing_opportunities[opportunity_id]["scope"].update(
                    {
                        "sku": hypothesis.get("sku_id"),
                        "retailer": hypothesis.get("retailer"),
                    }
                )
                st.rerun()
            if reject.button(
                "Reject", key=f"reject-{hypothesis_id}", use_container_width=True
            ):
                st.session_state.pricing_dispositions[hypothesis_id] = "Rejected"
                st.rerun()

    with st.expander("Raw SKAI evidence used by the hypothesis agent"):
        st.json(st.session_state.hypothesis_raw_evidence)

    workbook = build_hypothesis_feedback_workbook(
        hypotheses,
        scope=scope,
        source_errors=st.session_state.hypothesis_source_errors,
        raw_evidence=st.session_state.hypothesis_raw_evidence,
        tenant_code=st.session_state.get("selected_tenant_code"),
        model=st.session_state.get("workspace_model", ""),
    )
    st.download_button(
        "Download hypothesis & evidence feedback workbook",
        data=workbook,
        file_name=f"pricing_hypothesis_feedback_{date.today():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )


def render_opportunities(agent=None) -> None:
    selected = st.session_state.opportunity_detail
    if selected and selected in st.session_state.pricing_opportunities:
        _render_opportunity(st.session_state.pricing_opportunities[selected], agent)
        return
    _header("Pricing opportunities", "Commercial decisions created from pursued hypotheses.")
    if not st.session_state.pricing_opportunities:
        st.info("No opportunities yet. Open a supported hypothesis and choose Pursue as opportunity.")
        return
    for opp in st.session_state.pricing_opportunities.values():
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.caption(f'{opp["id"]} · {opp["status"]} · Owner: {opp["owner"]}')
                st.subheader(opp["statement"])
                st.write(f'Value at stake: **{opp["value"]}** · Source hypothesis: **{opp["hypothesis_id"]}**')
            with c2:
                if st.button("Define RGM Action", key=f'opp-{opp["id"]}', use_container_width=True):
                    st.session_state.opportunity_detail = opp["id"]
                    st.rerun()


def _delta(value) -> str:
    return "Not available" if value is None else f"{float(value):+.2f}%"


def _scenario_score(scenario: dict, objective: str, max_volume_loss: str) -> float:
    margin = scenario.get("margin_delta_pct")
    revenue = scenario.get("revenue_delta_pct")
    volume = scenario.get("volume_delta_pct")
    try:
        volume_floor = -abs(float(str(max_volume_loss).replace("%", "").strip()))
    except ValueError:
        volume_floor = float("-inf")
    if volume is not None and float(volume) < volume_floor:
        return -1_000_000 + float(volume)
    primary = {
        "Margin": margin,
        "Revenue": revenue,
        "Volume": volume,
        "Share": volume,
    }.get(objective)
    if primary is None:
        primary = revenue if revenue is not None else volume
    return float(primary) if primary is not None else float("-inf")


def _run_opportunity_scenarios(opp: dict, agent) -> None:
    """Generate, simulate, and rank three price actions for one opportunity."""
    result = agent.run_scenarios(opp)
    opp["scenario_rationale"] = result["rationale"]
    opp["simulator_base_row"] = result["base_row"]
    opp["scenarios"] = result["scenarios"]
    opp["scenario_comparison"] = result.get("comparison", {})
    recommendation_name = opp["scenario_comparison"].get("recommended_scenario")
    recommended = next(
        (
            scenario for scenario in opp["scenarios"]
            if scenario["name"] == recommendation_name
        ),
        max(
            opp["scenarios"],
            key=lambda scenario: _scenario_score(
                scenario, opp["objective"], opp["max_volume_loss"]
            ),
        ),
    )
    opp["selected"] = recommended["name"]
    opp["recommended_scenario"] = recommended["name"]
    opp["status"] = "Recommendation ready"
    opp["simulation_attempted"] = True
    opp.pop("simulation_error", None)
    st.session_state.pricing_opportunities[opp["id"]] = opp


def _comparison_conclusion(opp: dict, recommended: dict) -> str:
    objective = opp["objective"]
    metric_key = {
        "Margin": "margin_delta_pct",
        "Revenue": "revenue_delta_pct",
        "Volume": "volume_delta_pct",
        "Share": "volume_delta_pct",
    }[objective]
    metric_label = objective.lower()
    if recommended.get(metric_key) is None:
        metric_key = "revenue_delta_pct"
        metric_label = "revenue (margin was unavailable)"
    others = [
        scenario for scenario in opp["scenarios"]
        if scenario["name"] != recommended["name"]
    ]
    alternatives = ", ".join(
        f'{scenario["name"]} at {_delta(scenario.get(metric_key))}'
        for scenario in others
    )
    return (
        f'**{recommended["name"]} is the strongest scenario.** It delivers '
        f'**{_delta(recommended.get(metric_key))} {metric_label}** with '
        f'**{_delta(recommended.get("volume_delta_pct"))} volume**, versus '
        f'{alternatives}. It is the best available result after applying the '
        f'{opp["max_volume_loss"]} volume-loss guardrail.'
    )


def _render_opportunity(opp: dict, agent=None) -> None:
    if opp.get("scenarios") and "current_price" not in opp["scenarios"][0]:
        # Replace the original design-only mock scenarios for live opportunities.
        opp["scenarios"] = []
        opp["selected"] = None
        opp["status"] = "Awaiting simulation"
    if st.button("← Back to opportunities"):
        st.session_state.opportunity_detail = None
        st.rerun()
    _header(opp["statement"], f'Traceable to {opp["hypothesis_id"]}; simulation runs in the agent intelligence layer.', opp["id"])
    if not opp.get("scenarios") and agent is not None and not opp.get("simulation_attempted"):
        with st.status("Designing prices and running the SKAI simulator...", expanded=True) as status:
            try:
                st.write("Reading the accepted hypothesis and evidence")
                st.write("Resolving the current SKU-retailer shelf price")
                st.write("Running Conservative, Balanced, and Ambitious prices")
                _run_opportunity_scenarios(opp, agent)
                status.update(label="Three simulations complete", state="complete", expanded=False)
                st.rerun()
            except Exception as exc:
                opp["simulation_attempted"] = True
                opp["simulation_error"] = str(exc)
                st.session_state.pricing_opportunities[opp["id"]] = opp
                status.update(label="Simulation could not be completed", state="error")
                st.error(str(exc))
    if (
        opp.get("scenarios")
        and not opp.get("scenario_comparison")
        and agent is not None
        and not opp.get("comparison_attempted")
    ):
        with st.status("Comparing the three RGM moves...", expanded=True) as status:
            try:
                opp["scenario_comparison"] = agent.compare_existing_scenarios(opp)
                opp["comparison_attempted"] = True
                recommendation_name = opp["scenario_comparison"].get(
                    "recommended_scenario"
                )
                if recommendation_name:
                    opp["recommended_scenario"] = recommendation_name
                    opp["selected"] = recommendation_name
                st.session_state.pricing_opportunities[opp["id"]] = opp
                status.update(
                    label="Scenario comparison complete",
                    state="complete",
                    expanded=False,
                )
                st.rerun()
            except Exception as exc:
                opp["comparison_attempted"] = True
                st.session_state.pricing_opportunities[opp["id"]] = opp
                status.update(label="Comparison could not be completed", state="error")
                st.error(str(exc))

    with st.expander("Business objective and guardrails", expanded=False):
        with st.form(f'guardrails-{opp["id"]}'):
            c1, c2 = st.columns(2)
            opp["objective"] = c1.selectbox("Primary objective", ["Revenue", "Margin", "Volume", "Share"], index=["Revenue", "Margin", "Volume", "Share"].index(opp["objective"]))
            opp["max_volume_loss"] = c2.text_input("Maximum acceptable volume loss", opp["max_volume_loss"])
            opp["minimum_margin"] = c1.text_input("Minimum margin improvement", opp["minimum_margin"])
            opp["protected"] = c2.text_input("Protected SKUs or price points", opp["protected"])
            opp["excluded"] = c1.text_input("Excluded retailers or channels", opp["excluded"])
            opp["timing"] = c2.text_input("Timing constraints", opp["timing"])
            if st.form_submit_button("Update constraints"):
                if opp.get("scenarios"):
                    recommended = max(
                        opp["scenarios"],
                        key=lambda scenario: _scenario_score(
                            scenario, opp["objective"], opp["max_volume_loss"]
                        ),
                    )
                    opp["recommended_scenario"] = recommended["name"]
                    opp["selected"] = recommended["name"]
                st.session_state.pricing_opportunities[opp["id"]] = opp
                st.success("Constraints updated and the scenarios were re-ranked.")
    st.subheader("Agent-generated scenarios")
    st.caption(
        "The agent proposes three prices from the accepted evidence. SKAI then "
        "projects revenue, margin, and volume for each price."
    )
    if agent is None and not opp.get("scenarios"):
        st.warning("Connect to SKAI and provide an OpenAI key to run price scenarios.")
    if opp.get("simulation_error") and st.button(
        "Retry scenario simulations", use_container_width=True, disabled=agent is None
    ):
        with st.status("Designing prices and running the SKAI simulator...", expanded=True) as status:
            try:
                _run_opportunity_scenarios(opp, agent)
                status.update(label="Three simulations complete", state="complete", expanded=False)
                st.rerun()
            except Exception as exc:
                status.update(label="Simulation could not be completed", state="error")
                st.error(str(exc))

    if not opp.get("scenarios"):
        st.info("The scenario comparison will appear once the simulations complete.")
        return
    if opp.get("scenario_rationale"):
        st.write(opp["scenario_rationale"])
    table = [
        {
            "Scenario": scenario["name"],
            "Current price": f'{scenario["current_price"]:.2f}',
            "Test price": f'{scenario["new_price"]:.2f}',
            "Price change": _delta(scenario["price_change_pct"]),
            "Revenue": _delta(scenario.get("revenue_delta_pct")),
            "Margin": _delta(scenario.get("margin_delta_pct")),
            "Volume": _delta(scenario.get("volume_delta_pct")),
        }
        for scenario in opp["scenarios"]
    ]
    st.dataframe(table, use_container_width=True, hide_index=True)
    recommended_name = opp.get("recommended_scenario") or opp.get("selected")
    recommended = next(
        scenario for scenario in opp["scenarios"]
        if scenario["name"] == recommended_name
    )
    st.subheader("Scenario comparison")
    comparison = opp.get("scenario_comparison") or {}
    assessments = comparison.get("scenario_assessments") or []
    if assessments:
        columns = st.columns(3)
        for column, assessment in zip(columns, assessments):
            with column:
                with st.container(border=True):
                    st.subheader(assessment["name"])
                    st.write(assessment["verdict"])
                    st.markdown("**Pros**")
                    for item in assessment.get("pros", []):
                        st.markdown(f"- {item}")
                    st.markdown("**Cons**")
                    for item in assessment.get("cons", []):
                        st.markdown(f"- {item}")
                    st.markdown("**Fit with the evidence**")
                    st.write(assessment.get("evidence_fit", ""))
                    st.markdown("**Best use case**")
                    st.write(assessment.get("best_use_case", ""))
        with st.container(border=True):
            st.caption("AGENT COMPARATIVE CONCLUSION")
            st.subheader(f'{comparison.get("recommended_scenario", recommended["name"])} is the preferred move')
            st.write(comparison.get("recommendation_reason", ""))
            for caveat in comparison.get("caveats", []):
                st.warning(caveat)
    else:
        for scenario in opp["scenarios"]:
            st.markdown(
                f'- **{scenario["name"]}:** price {_delta(scenario["price_change_pct"])}, '
                f'revenue {_delta(scenario.get("revenue_delta_pct"))}, '
                f'margin {_delta(scenario.get("margin_delta_pct"))}, and '
                f'volume {_delta(scenario.get("volume_delta_pct"))}.'
            )
        st.write(_comparison_conclusion(opp, recommended))
    names = [s["name"] for s in opp["scenarios"]]
    selected_index = names.index(opp["selected"]) if opp.get("selected") in names else 0
    opp["selected"] = st.radio(
        "Scenario for decision", names, index=selected_index, horizontal=True
    )
    selected = next(s for s in opp["scenarios"] if s["name"] == opp["selected"])
    with st.container(border=True):
        st.caption("INTEGRATED AGENT RECOMMENDATION")
        st.subheader(f'Choose the {selected["name"]} scenario')
        st.write(
            f'Test a price of **{selected["new_price"]:.2f}** '
            f'({_delta(selected["price_change_pct"])}). SKAI projects '
            f'**{_delta(selected.get("margin_delta_pct"))} margin**, '
            f'**{_delta(selected.get("revenue_delta_pct"))} revenue**, and '
            f'**{_delta(selected.get("volume_delta_pct"))} volume**.'
        )
        st.write(selected.get("reason", ""))
        if selected.get("margin_delta_pct") is None:
            st.warning(
                "SKAI did not provide margin inputs for this perimeter. The "
                "recommendation therefore uses the available revenue and volume results."
            )
        st.write(
            f'It is ranked against the **{opp["objective"].lower()}** objective '
            f'and the **{opp["max_volume_loss"]}** volume-loss guardrail.'
        )
    c1, c2, c3 = st.columns(3)
    if c1.button("Approve recommendation", type="primary", use_container_width=True):
        story_id = f'S-{opp["id"].split("-")[-1]}'
        st.session_state.sell_in_stories[story_id] = {"id": story_id, "opportunity_id": opp["id"], "scenario": deepcopy(selected), "created": str(date.today())}
        opp["status"] = "Approved"
        st.success(f"Recommendation approved and sell-in story {story_id} created.")
    if c2.button("Request additional scenario", use_container_width=True):
        opp["status"] = "Additional scenario requested"
        st.info("Request recorded for the pricing agent.")
    if c3.button("Reject recommendation", use_container_width=True):
        opp["status"] = "Rejected"
        st.warning("Recommendation rejected; the opportunity and evidence remain available.")


def render_stories() -> None:
    selected = st.session_state.story_detail
    if selected and selected in st.session_state.sell_in_stories:
        _render_story(st.session_state.sell_in_stories[selected])
        return
    _header("Sell-in stories", "Decision-ready narratives built from approved pricing recommendations.")
    if not st.session_state.sell_in_stories:
        st.info("Approve an opportunity recommendation to create the first sell-in story.")
        return
    for story in st.session_state.sell_in_stories.values():
        with st.container(border=True):
            st.caption(f'{story["id"]} · Created {story["created"]}')
            st.subheader(f'{story["scenario"]["name"]} pricing recommendation')
            if st.button("Preview story", key=f'story-{story["id"]}'):
                st.session_state.story_detail = story["id"]
                st.rerun()


def _render_story(story: dict) -> None:
    if st.button("← Back to sell-in stories"):
        st.session_state.story_detail = None
        st.rerun()
    opp = st.session_state.pricing_opportunities[story["opportunity_id"]]
    hypothesis = opp.get("hypothesis") or next(
        h for h in HYPOTHESES if h["id"] == opp["hypothesis_id"]
    )
    scenario = story["scenario"]
    if opp.get("hypothesis"):
        scope = opp.get("scope", {})
        context = ", ".join(
            str(scope.get(key)) for key in ("brand", "sku", "retailer")
            if scope.get(key)
        )
        support_findings = "; ".join(
            item.get("finding", "")
            for item in hypothesis.get("evidence", [])
            if item.get("direction") == "Support"
        )
        counter_findings = "; ".join(
            item.get("finding", "")
            for item in hypothesis.get("evidence", [])
            if item.get("direction") == "Counterevidence"
        )
    else:
        context = f'{hypothesis["scope"]}, {hypothesis["period"]}'
        support_findings = "; ".join(
            item[0] for item in hypothesis["evidence"] if item[2] == "Supports"
        )
        counter_findings = "; ".join(
            item[0] for item in hypothesis["evidence"] if item[2] != "Supports"
        )
    _header("Customer pricing story", "A traceable narrative ready for decision and retailer sell-in.", story["id"])
    sections = [
        ("1. Business context", f'{context}. The objective is {opp["objective"].lower()} growth within a maximum {opp["max_volume_loss"]} volume decline.'),
        ("2. Pricing hypothesis", hypothesis["statement"]),
        ("3. Evidence", support_findings),
        ("4. Counterevidence", counter_findings),
        ("5. Confirmed opportunity", f'{opp["statement"]} Estimated value: {opp["value"]}.'),
        ("6. Scenarios considered", ", ".join(s["name"] for s in opp["scenarios"])),
        (
            "7. Recommended action",
            scenario.get("reason") or scenario.get("action", "Run the selected price scenario."),
        ),
        (
            "8. Expected impact",
            f'Revenue {_delta(scenario.get("revenue_delta_pct")) if "revenue_delta_pct" in scenario else scenario.get("revenue")}; '
            f'margin {_delta(scenario.get("margin_delta_pct")) if "margin_delta_pct" in scenario else scenario.get("margin")}; '
            f'volume {_delta(scenario.get("volume_delta_pct")) if "volume_delta_pct" in scenario else scenario.get("volume")}.'
        ),
        ("9. Risks and mitigations", "Validate elasticity and retailer acceptance; stage execution, protect the entry pack and monitor competitor response."),
    ]
    for title, body in sections:
        with st.container(border=True):
            st.subheader(title)
            st.write(body)
    st.caption(f'Traceability: {hypothesis["id"]} → {opp["id"]} → {scenario["name"]} scenario → {story["id"]}')
    st.button("Export executive summary (coming soon)", disabled=True)
    st.button("Export one-slide recommendation (coming soon)", disabled=True)
