"""Streamlit-native pricing decision workspace around the existing Copilot."""

from __future__ import annotations

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
    left, right = st.columns([1, 1.35])
    with left:
        st.subheader("Workspace status")
        st.success("SKAI data connected" if connected else "SKAI connection required")
        st.info("OpenAI configured" if bool(st.session_state.get("workspace_openai_key")) else "OpenAI key is available in Connection settings")
        st.caption("Credentials, API settings and workspace selection are managed on the Connection page.")
    with right:
        st.subheader("Current analysis scope")
        scope = {
            "Market": "US", "Category": "Mexican shelf-stable food", "Brand": "La Costeña",
            "Retailer": "Total market", "Period": "Latest 52 weeks", "Workspace": (tenant or "Not selected").replace("_", " ").title(),
        }
        st.dataframe([scope], use_container_width=True, hide_index=True)


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
    support, counter = st.columns(2)
    supporting = [e for e in h["evidence"] if e[2] == "Supports"]
    opposing = [e for e in h["evidence"] if e[2] != "Supports"]
    for column, title, evidence in ((support, "Supporting evidence", supporting), (counter, "Counterevidence & gaps", opposing)):
        with column:
            st.subheader(title)
            for finding, interpretation, direction, strength, source in evidence:
                with st.container(border=True):
                    st.caption(f"{direction.upper()} · {strength} · {source}")
                    st.markdown(f"**{finding}**")
                    st.write(interpretation)
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


def render_hypotheses(agent, filter_values: dict) -> None:
    """Run and review live, scope-specific pricing hypotheses."""
    _header(
        "Pricing hypotheses",
        "Select a commercial scope and ask the agent to generate evidence-backed hypotheses.",
    )
    brands = _filter_options(filter_values, "brands")
    skus = _filter_options(filter_values, "sku_ids", "skus")
    retailers = _filter_options(filter_values, "retailers", "retailer_groups")
    with st.container(border=True):
        st.caption("ANALYSIS SCOPE")
        lever = st.selectbox(
            "RGM lever",
            ["Pricing", "Promo", "Trade terms", "Mix"],
            key="hypothesis_lever",
        )
        c1, c2, c3 = st.columns(3)
        brand = c1.selectbox("Brand", ["All brands", *brands], key="hypothesis_brand")
        sku = c2.selectbox("SKU", ["All SKUs", *skus], key="hypothesis_sku")
        retailer = c3.selectbox(
            "Retailer", ["All retailers", *retailers], key="hypothesis_retailer"
        )
        st.caption(
            "Retailer filters Market Landscape and Price Ladder. Price Pack Curve "
            "retrieves the full selected-brand architecture and uses the selected "
            "SKU as the focus."
        )
        run_scan = st.button(
            "Generate hypotheses",
            type="primary",
            use_container_width=True,
            disabled=lever != "Pricing",
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
            result, raw = agent.investigate(
                brand=None if brand == "All brands" else brand,
                sku_id=None if sku == "All SKUs" else sku,
                retailer=None if retailer == "All retailers" else retailer,
            )
            st.session_state.generated_hypotheses = result.get("hypotheses", [])
            st.session_state.hypothesis_scan_scope = {
                "brand": brand,
                "sku": sku,
                "retailer": retailer,
                "lever": lever,
                "summary": result.get("scope_summary", ""),
            }
            st.session_state.hypothesis_scan_limitations = result.get(
                "data_limitations", []
            )
            st.session_state.hypothesis_raw_evidence = raw
            st.session_state.hypothesis_source_errors = raw.get(
                "source_errors", {}
            )
            status.update(
                label="Hypothesis generation complete",
                state="complete",
                expanded=False,
            )

    hypotheses = sorted(
        st.session_state.generated_hypotheses,
        key=lambda item: item.get("priority", 0),
        reverse=True,
    )
    if not hypotheses:
        st.info("Choose a scope and run the first live pricing opportunity scan.")
        return

    scope = st.session_state.hypothesis_scan_scope
    st.caption(
        f'LAST SCAN - {scope.get("brand")} - {scope.get("sku")} - '
        f'{scope.get("retailer")}'
    )
    if scope.get("summary"):
        st.write(scope["summary"])
    for limitation in st.session_state.hypothesis_scan_limitations:
        st.warning(limitation)
    for source, error in st.session_state.hypothesis_source_errors.items():
        st.warning(
            f'{source.replace("_", " ").title()} was unavailable; the scan '
            f'continued with the remaining sources. {error}'
        )

    for index, hypothesis in enumerate(hypotheses):
        hypothesis_id = hypothesis.get("id") or f"LIVE-{index + 1}"
        disposition = st.session_state.pricing_dispositions.get(
            hypothesis_id, "Review"
        )
        with st.container(border=True):
            st.caption(
                f'{hypothesis_id} - PRIORITY {hypothesis.get("priority", 0)} - '
                f'{hypothesis.get("evidence_status", "Mixed").upper()}'
            )
            st.markdown(f'**Direction: {hypothesis.get("direction", "Pricing adjustment")}**')
            st.subheader(hypothesis.get("statement", "Pricing opportunity"))
            st.write(hypothesis.get("opportunity", ""))
            m1, m2, m3 = st.columns(3)
            m1.metric("Confidence", f'{hypothesis.get("confidence", 0)}%')
            m2.metric(
                "Estimated value",
                hypothesis.get("estimated_value", "Not quantified"),
            )
            m3.metric("Decision", disposition)
            st.caption(
                f'Value basis: {hypothesis.get("value_basis", "Not provided")}'
            )

            evidence = hypothesis.get("evidence", [])
            supporting = [
                item for item in evidence if item.get("direction") == "Support"
            ]
            opposing = [
                item
                for item in evidence
                if item.get("direction") == "Counterevidence"
            ]
            support_col, counter_col = st.columns(2)
            for column, title, cards in (
                (support_col, "Supporting evidence", supporting),
                (counter_col, "Counterevidence", opposing),
            ):
                with column:
                    st.markdown(f"**{title}**")
                    if not cards:
                        st.caption("No evidence card returned for this side.")
                    for evidence_card in cards:
                        with st.container(border=True):
                            strength = str(evidence_card.get("strength", "")).upper()
                            source = evidence_card.get("source", "")
                            st.caption(f"{strength} - {source}")
                            st.markdown(
                                f'**{evidence_card.get("finding", "Finding")}**'
                            )
                            st.write(evidence_card.get("interpretation", ""))
                            st.caption(evidence_card.get("scope", ""))

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
                    "status": "Recommendation ready",
                    "owner": "Pricing team",
                    "objective": "Margin",
                    "max_volume_loss": "1.5%",
                    "minimum_margin": "To be defined",
                    "protected": "Entry-price pack",
                    "excluded": "None",
                    "timing": "Next list-price window",
                    "selected": "Balanced",
                    "scenarios": deepcopy(SCENARIOS),
                }
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


def render_opportunities() -> None:
    selected = st.session_state.opportunity_detail
    if selected and selected in st.session_state.pricing_opportunities:
        _render_opportunity(st.session_state.pricing_opportunities[selected])
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
                if st.button("Review decision", key=f'opp-{opp["id"]}', use_container_width=True):
                    st.session_state.opportunity_detail = opp["id"]
                    st.rerun()


def _render_opportunity(opp: dict) -> None:
    if st.button("← Back to opportunities"):
        st.session_state.opportunity_detail = None
        st.rerun()
    _header(opp["statement"], f'Traceable to {opp["hypothesis_id"]}; simulation runs in the agent intelligence layer.', opp["id"])
    st.subheader("Business objective and guardrails")
    with st.form(f'guardrails-{opp["id"]}'):
        c1, c2 = st.columns(2)
        opp["objective"] = c1.selectbox("Primary objective", ["Revenue", "Margin", "Volume", "Share"], index=["Revenue", "Margin", "Volume", "Share"].index(opp["objective"]))
        opp["max_volume_loss"] = c2.text_input("Maximum acceptable volume loss", opp["max_volume_loss"])
        opp["minimum_margin"] = c1.text_input("Minimum margin improvement", opp["minimum_margin"])
        opp["protected"] = c2.text_input("Protected SKUs or price points", opp["protected"])
        opp["excluded"] = c1.text_input("Excluded retailers or channels", opp["excluded"])
        opp["timing"] = c2.text_input("Timing constraints", opp["timing"])
        if st.form_submit_button("Update constraints"):
            st.session_state.pricing_opportunities[opp["id"]] = opp
            st.success("Constraints updated; the agent would rerun the background scenarios.")
    st.subheader("Agent-generated scenarios")
    st.caption("Business outcomes are shown; simulator controls and technical parameters stay hidden.")
    st.dataframe(opp["scenarios"], use_container_width=True, hide_index=True)
    names = [s["name"] for s in opp["scenarios"]]
    opp["selected"] = st.radio("Scenario for decision", names, index=names.index(opp["selected"]), horizontal=True)
    selected = next(s for s in opp["scenarios"] if s["name"] == opp["selected"])
    with st.container(border=True):
        st.caption("INTEGRATED AGENT RECOMMENDATION")
        st.subheader(f'Choose the {selected["name"]} scenario')
        st.write(f'{selected["action"]}. It is expected to deliver **{selected["margin"]} margin** and **{selected["revenue"]} revenue**, with **{selected["volume"]} volume**. Confidence: {selected["confidence"]}.')
        st.write(f'It best balances the **{opp["objective"].lower()}** objective with the **{opp["max_volume_loss"]}** volume-loss guardrail. Main risks are elasticity error and retailer response; mitigate through staged retailer validation and a competitor-price check.')
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
        ("7. Recommended action", scenario["action"]),
        ("8. Expected impact", f'Revenue {scenario["revenue"]}; margin {scenario["margin"]}; volume {scenario["volume"]}.'),
        ("9. Risks and mitigations", "Validate elasticity and retailer acceptance; stage execution, protect the entry pack and monitor competitor response."),
    ]
    for title, body in sections:
        with st.container(border=True):
            st.subheader(title)
            st.write(body)
    st.caption(f'Traceability: {hypothesis["id"]} → {opp["id"]} → {scenario["name"]} scenario → {story["id"]}')
    st.button("Export executive summary (coming soon)", disabled=True)
    st.button("Export one-slide recommendation (coming soon)", disabled=True)
