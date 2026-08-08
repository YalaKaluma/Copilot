"""Streamlit chat prototype for SKAI Growth."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from agent import SkaiAgent
from feedback_export import build_feedback_workbook
from hypothesis_agent import PricingHypothesisAgent
from orchestrator import Orchestrator
from pricing_workspace import (
    initialize_workspace,
    render_home,
    render_hypotheses,
    render_opportunities,
    render_stories,
)
from skai_auth import CognitoSrpAuthenticator, SkaiAuthError, tenant_codes_from_token
from skai_service import SkaiError, SkaiGrowthService

load_dotenv()


def _escape_currency_for_markdown(text: str) -> str:
    """Prevent dollar amounts from being parsed as inline LaTeX by Streamlit."""
    return re.sub(r"(?<!\\)\$", r"\\$", text)


st.set_page_config(
    page_title="SKAI Growth Copilot",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --sk-ink: #f5f3f5;
        --sk-muted: #9e98a3;
        --sk-canvas: #050506;
        --sk-panel: #1d1c24;
        --sk-panel-raised: #24222c;
        --sk-line: #35323d;
        --sk-burgundy: #a73565;
        --sk-burgundy-soft: #2a1721;
        --sk-magenta: #dc1760;
        --sk-teal: #168b7d;
    }

    .stApp, [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at 70% 0%, rgba(79, 43, 101, .14), transparent 30%),
            radial-gradient(circle at 20% 5%, rgba(0, 128, 113, .09), transparent 25%),
            var(--sk-canvas);
        color: var(--sk-ink);
    }
    [data-testid="stHeader"] { background: rgba(5, 5, 6, .92); }
    [data-testid="stToolbar"] { right: 1rem; }
    [data-testid="stMainBlockContainer"] {
        max-width: 1180px;
        padding-top: 2.2rem;
        padding-bottom: 6rem;
    }
    [data-testid="stSidebar"] {
        background: #0e0d12;
        border-right: 1px solid var(--sk-line);
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.2rem;
    }
    [data-testid="stSidebar"] h2 {
        color: var(--sk-ink);
        font-size: .78rem;
        font-weight: 750;
        letter-spacing: .12em;
        text-transform: uppercase;
        margin-top: 1.25rem;
    }
    [data-testid="stSidebar"] .stButton > button {
        justify-content: flex-start;
        min-height: 2.65rem;
        color: var(--sk-muted);
        background: transparent;
        border: 0;
        border-radius: 7px;
        padding-left: .8rem;
        box-shadow: none;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        color: var(--sk-ink);
        background: #1b1920;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        color: #fff;
        background: #311723;
        border-left: 3px solid var(--sk-magenta);
    }
    h1, h2, h3, p, label, .stMarkdown { color: var(--sk-ink); }

    .sk-brand {
        display: flex;
        align-items: center;
        gap: .7rem;
        min-height: 40px;
    }
    .sk-mark {
        position: relative;
        width: 27px;
        height: 34px;
        flex: 0 0 27px;
    }
    .sk-mark i {
        position: absolute;
        width: 11px;
        height: 11px;
        background: var(--sk-magenta);
        transform: rotate(45deg);
        border-radius: 1px;
    }
    .sk-mark i:nth-child(1) { left: 2px; top: 2px; }
    .sk-mark i:nth-child(2) { left: 11px; top: 11px; background: #f05582; }
    .sk-mark i:nth-child(3) { left: 2px; top: 20px; }
    .sk-brand-name {
        color: var(--sk-ink);
        font-size: 1.08rem;
        font-weight: 680;
        letter-spacing: -.025em;
    }
    .sk-brand-name span { color: var(--sk-magenta); }
    .sk-main-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 0 1.35rem;
        margin-bottom: 1.25rem;
        border-bottom: 1px solid var(--sk-line);
    }
    .sk-main-header h1 {
        color: var(--sk-ink);
        font-size: clamp(1.8rem, 4vw, 2.6rem);
        line-height: 1.05;
        letter-spacing: -.045em;
        margin: 0 0 .45rem;
    }
    .sk-main-header p {
        color: var(--sk-muted);
        margin: 0;
        font-size: .98rem;
    }
    .sk-pill {
        color: #e7a8c3;
        background: var(--sk-burgundy-soft);
        border: 1px solid #5b2a40;
        border-radius: 999px;
        padding: .42rem .8rem;
        font-size: .72rem;
        font-weight: 750;
        letter-spacing: .08em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .sk-eyebrow {
        color: #e477a3 !important;
        font-size: .72rem;
        font-weight: 750;
        letter-spacing: .12em;
        text-transform: uppercase;
        margin: 0 0 .35rem;
    }
    .sk-subtitle { color: var(--sk-muted) !important; margin: -.4rem 0 1.6rem; }

    [data-testid="stTextInput"] input,
    [data-baseweb="select"] > div {
        background: var(--sk-panel) !important;
        color: var(--sk-ink) !important;
        border-color: #4b4852 !important;
        border-radius: 8px;
        box-shadow: none;
    }
    [data-testid="stTextInput"] [data-baseweb="input"] {
        background: var(--sk-panel) !important;
        border: 1px solid #4b4852 !important;
        border-radius: 8px !important;
        box-shadow: none !important;
    }
    [data-testid="stTextInput"] [data-baseweb="input"] input {
        background: transparent !important;
        border: 0 !important;
        color: var(--sk-ink) !important;
    }
    [data-testid="stTextInput"] [data-baseweb="input"] button,
    [data-testid="stTextInput"] [data-baseweb="input"] div {
        background: transparent !important;
        color: var(--sk-muted) !important;
    }
    [data-baseweb="select"] > div,
    [data-baseweb="select"] input,
    [data-baseweb="select"] svg {
        background-color: var(--sk-panel) !important;
        color: var(--sk-ink) !important;
        fill: var(--sk-muted) !important;
    }
    [data-testid="stTextInput"] input:focus,
    [data-baseweb="select"] > div:focus-within {
        border-color: var(--sk-burgundy);
        box-shadow: 0 0 0 1px var(--sk-burgundy);
    }
    .stButton > button,
    .stDownloadButton > button {
        width: 100%;
        color: #f3d8e4;
        background: #18161d;
        border: 1px solid #684057;
        border-radius: 8px;
        font-weight: 650;
    }
    .stButton > button:hover,
    .stDownloadButton > button:hover {
        color: #fff;
        background: var(--sk-burgundy);
        border-color: var(--sk-burgundy);
    }
    [data-testid="stChatMessage"] {
        background: rgba(29, 28, 36, .94);
        border: 1px solid var(--sk-line);
        border-radius: 11px;
        padding: .35rem .65rem;
        margin-bottom: .75rem;
        box-shadow: 0 5px 24px rgba(0, 0, 0, .22);
    }
    [data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"] {
        background: var(--sk-burgundy);
    }
    [data-testid="stChatMessage"] [data-testid="stChatMessageAvatarAssistant"] {
        background: #34313c;
    }
    [data-testid="stStatusWidget"], [data-testid="stExpander"] {
        background: var(--sk-panel);
        border-color: var(--sk-line);
        border-radius: 9px;
    }
    [data-testid="stAlert"] { border-radius: 9px; }
    [data-testid="stChatInput"] {
        background: #111015 !important;
        border: 1px solid #494450;
        border-radius: 11px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, .38);
    }
    [data-testid="stChatInput"]:focus-within { border-color: var(--sk-burgundy); }
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] button {
        background: #111015 !important;
        color: var(--sk-ink) !important;
    }
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"],
    [data-testid="stChatInputContainer"] {
        background: var(--sk-canvas) !important;
        border-color: var(--sk-line) !important;
    }
    [data-testid="stBottom"] {
        border-top: 1px solid #24212a !important;
        box-shadow: 0 -12px 30px rgba(0, 0, 0, .22) !important;
    }
    .stSuccess { color: var(--sk-teal); }
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] textarea::placeholder,
    [data-testid="stTextInput"] input::placeholder {
        color: var(--sk-muted);
    }
    [data-testid="stWidgetLabel"] p,
    [data-testid="stCaptionContainer"] p,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stExpander"] summary,
    [data-baseweb="select"] span {
        color: var(--sk-ink);
    }
    [data-baseweb="popover"] > div,
    [role="listbox"],
    [role="option"] {
        background: var(--sk-panel-raised);
        color: var(--sk-ink);
    }
    [role="option"]:hover { background: #39202c; }
    [data-testid="stAlert"] {
        background: var(--sk-panel-raised);
        color: var(--sk-ink);
        border: 1px solid var(--sk-line);
    }
    [data-testid="stAlert"] p { color: var(--sk-ink); }
    [data-testid="stToggleSwitch"] span { color: var(--sk-ink); }
    code { color: #f0b2cc; background: #281a21; }
    hr { border-color: var(--sk-line); }
    @media (max-width: 760px) {
        .sk-pill { display: none; }
        [data-testid="stMainBlockContainer"] { padding-top: 1.2rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _cognito_settings() -> tuple[str | None, str | None, str | None]:
    return (
        os.getenv("SKAI_COGNITO_REGION"),
        os.getenv("SKAI_COGNITO_USER_POOL_ID"),
        os.getenv("SKAI_COGNITO_CLIENT_ID"),
    )


def _store_login(username: str, password: str) -> None:
    settings = _cognito_settings()
    if not all(settings):
        raise SkaiAuthError("Complete the three SKAI Cognito settings in .env.")
    token = CognitoSrpAuthenticator(*settings).authenticate(username, password)
    st.session_state["skai_token"] = token
    st.session_state["tenant_codes"] = tenant_codes_from_token(token)


# When credentials are stored locally, connect once per Streamlit session so the
# workspace selector is available immediately.
if "skai_token" not in st.session_state:
    env_username = os.getenv("SKAI_USERNAME", "")
    env_password = os.getenv("SKAI_PASSWORD", "")
    if env_username and env_password:
        try:
            _store_login(env_username, env_password)
            st.session_state.pop("auto_login_error", None)
        except Exception as exc:
            st.session_state["auto_login_error"] = str(exc)

initialize_workspace()
st.session_state.setdefault("workspace_page", "Home")
st.session_state.setdefault("workspace_openai_key", os.getenv("OPENAI_API_KEY", ""))
st.session_state.setdefault("workspace_model", os.getenv("OPENAI_MODEL", "gpt-5.6"))
st.session_state.setdefault("workspace_show_raw", False)

skai_url = os.getenv("SKAI_API_URL", "")
openai_key = st.session_state.workspace_openai_key
model = st.session_state.workspace_model
show_raw = st.session_state.workspace_show_raw
tenant_codes = st.session_state.get("tenant_codes", [])
if tenant_codes:
    configured_tenant = os.getenv("SKAI_TENANT_CODE", "akzonobel")
    if st.session_state.get("tenant_code") not in tenant_codes:
        st.session_state["tenant_code"] = (
            configured_tenant if configured_tenant in tenant_codes else tenant_codes[0]
        )
    tenant_code = st.session_state["tenant_code"]
else:
    tenant_code = None

with st.sidebar:
    st.markdown(
        """
        <div class="sk-brand">
          <span class="sk-mark"><i></i><i></i><i></i></span>
          <span class="sk-brand-name">SK RGM <span>AI</span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("PRICING WORKSPACE")
    navigation = [
        ("⌂  Home", "Home"),
        ("✦  Copilot", "Copilot"),
        ("◇  Hypotheses", "Hypotheses"),
        ("◎  Opportunities", "Opportunities"),
        ("▤  Sell-in Stories", "Sell-in Stories"),
        ("⚙  Connection", "Connection"),
    ]
    for label, destination in navigation:
        if st.button(
            label,
            key=f"nav-{destination}",
            type="primary" if st.session_state.workspace_page == destination else "secondary",
            use_container_width=True,
        ):
            st.session_state.workspace_page = destination
            st.rerun()
    st.divider()
    if st.session_state.get("skai_token"):
        st.success(f"Connected · {(tenant_code or 'workspace').replace('_', ' ').title()}")
    else:
        st.caption("SKAI not connected")

page = st.session_state.workspace_page

if page == "Connection":
    st.markdown('<p class="sk-eyebrow">Workspace settings</p><h1>Connection</h1><p class="sk-subtitle">Manage SKAI authentication, workspace scope and model configuration.</p>', unsafe_allow_html=True)
    left, right = st.columns([1.15, .85])
    with left:
        st.subheader("Credentials")
        skai_username = st.text_input("SKAI username", value=os.getenv("SKAI_USERNAME", ""))
        skai_password = st.text_input("SKAI password", value=os.getenv("SKAI_PASSWORD", ""), type="password")
        openai_key = st.text_input("OpenAI API key", value=st.session_state.workspace_openai_key, type="password")
        st.session_state.workspace_openai_key = openai_key
    with right:
        st.subheader("Analysis configuration")
        model = st.text_input("Model", value=st.session_state.workspace_model)
        st.session_state.workspace_model = model
        show_raw = st.toggle("Show raw SKAI response", value=st.session_state.workspace_show_raw)
        st.session_state.workspace_show_raw = show_raw
        if tenant_codes:
            tenant_code = st.selectbox("SKAI workspace", options=tenant_codes, key="tenant_code", format_func=lambda code: code.replace("_", " ").title())
        else:
            st.text_input("SKAI workspace", value="Connect to load available workspaces", disabled=True)
    if st.session_state.get("auto_login_error"):
        st.warning(f"Automatic SKAI login failed: {st.session_state['auto_login_error']}")
    elif st.session_state.get("skai_token"):
        st.success("Connected to SKAI")
    if st.button("Reconnect and test", type="primary", use_container_width=True, key="connection-test"):
        if not all(_cognito_settings()):
            st.error("Complete the three SKAI Cognito settings in .env.")
        elif not (skai_username and skai_password):
            st.error("Enter your SKAI username and password.")
        else:
            try:
                _store_login(skai_username, skai_password)
                token = st.session_state["skai_token"]
                service = SkaiGrowthService(
                    skai_url,
                    market_base_url=os.getenv("SKAI_MARKET_API_URL") or None,
                    tenant_code=tenant_code,
                    token=token,
                    origin=os.getenv("SKAI_API_ORIGIN") or None,
                    referer=os.getenv("SKAI_API_REFERER") or None,
                )
                filters = service.get_filter_values()
                service.close()
                cache_key = f"filter_values:{tenant_code or 'default'}"
                st.session_state[cache_key] = filters
                st.session_state.pop("auto_login_error", None)
                st.success("Connected to SKAI.")
                if tenant_code is None and st.session_state["tenant_codes"]:
                    st.rerun()
            except (SkaiAuthError, SkaiError) as exc:
                st.error(str(exc))
    st.stop()

if page == "Home":
    render_home(bool(st.session_state.get("skai_token")), tenant_code)
    st.stop()
if page == "Hypotheses":
    if not st.session_state.get("skai_token"):
        st.error("Connect to SKAI on the Connection page before running hypotheses.")
        st.stop()
    if not openai_key:
        st.error("Add the OpenAI API key on the Connection page first.")
        st.stop()
    hypothesis_service = SkaiGrowthService(
        skai_url,
        market_base_url=os.getenv("SKAI_MARKET_API_URL") or None,
        tenant_code=tenant_code,
        token=st.session_state["skai_token"],
        origin=os.getenv("SKAI_API_ORIGIN") or None,
        referer=os.getenv("SKAI_API_REFERER") or None,
    )
    try:
        cache_key = f"filter_values:{tenant_code or 'default'}"
        hypothesis_filters = st.session_state.get(cache_key)
        if hypothesis_filters is None:
            hypothesis_filters = hypothesis_service.get_filter_values()
            st.session_state[cache_key] = hypothesis_filters
        hypothesis_agent = PricingHypothesisAgent(
            hypothesis_service, OpenAI(api_key=openai_key), model
        )
        render_hypotheses(hypothesis_agent, hypothesis_filters)
    except Exception as exc:
        st.error(f"Could not generate pricing hypotheses: {exc}")
    finally:
        hypothesis_service.close()
    st.stop()
if page == "Opportunities":
    render_opportunities()
    st.stop()
if page == "Sell-in Stories":
    render_stories()
    st.stop()

st.markdown(
    """
    <div class="sk-main-header">
      <div>
        <h1>Growth Copilot</h1>
        <p>Ask a commercial question, inspect the plan, and run it on SKAI.</p>
      </div>
      <span class="sk-pill">Analytics prototype</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "feedback_session_id" not in st.session_state:
    st.session_state.feedback_session_id = str(uuid4())

with st.sidebar:
    if st.session_state.messages:
        feedback_bytes = build_feedback_workbook(
            st.session_state.messages,
            session_id=st.session_state.feedback_session_id,
            tenant_code=tenant_code,
            model=model,
        )
        st.download_button(
            "Download feedback workbook",
            data=feedback_bytes,
            file_name=(
                "skai_copilot_feedback_"
                f"{datetime.now(UTC):%Y%m%d_%H%M%S}.xlsx"
            ),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(_escape_currency_for_markdown(message["content"]))
        if message.get("plan"):
            with st.expander("Execution plan"):
                st.json(message["plan"])
        if show_raw and message.get("raw"):
            with st.expander("Raw SKAI response"):
                st.json(message["raw"])

question = st.chat_input("Which promotions are producing the best ROI by retailer?")
if question:
    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
            "timestamp": datetime.now(UTC).isoformat(),
            "tenant": tenant_code,
            "model": model,
        }
    )
    with st.chat_message("user"):
        st.markdown(question)

    if not (st.session_state.get("skai_token") and openai_key):
        answer = "Please connect to SKAI and add the OpenAI API key first."
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "timestamp": datetime.now(UTC).isoformat(),
                "tenant": tenant_code,
                "model": model,
            }
        )
        with st.chat_message("assistant"):
            st.warning(answer)
    else:
        with st.chat_message("assistant"):
            try:
                llm = OpenAI(api_key=openai_key)
                service = SkaiGrowthService(
                    skai_url,
                    market_base_url=os.getenv("SKAI_MARKET_API_URL") or None,
                    tenant_code=tenant_code,
                    token=st.session_state["skai_token"],
                    origin=os.getenv("SKAI_API_ORIGIN") or None,
                    referer=os.getenv("SKAI_API_REFERER") or None,
                )
                with st.status("Understanding the question and building a plan..."):
                    cache_key = f"filter_values:{tenant_code or 'default'}"
                    filters = st.session_state.get(cache_key)
                    if filters is None:
                        filters = service.get_filter_values()
                        st.session_state[cache_key] = filters
                    conversation_context = [
                        {
                            "role": message["role"],
                            "content": message["content"],
                        }
                        for message in st.session_state.messages[:-1]
                    ]
                    plan = Orchestrator(llm, model).build_plan(
                        question,
                        filters,
                        conversation_context=conversation_context,
                    )
                    st.write("Plan ready")
                    if plan["decision"] == "clarify":
                        result = {}
                        answer = plan["clarification_question"] or (
                            "Could you clarify which measure you want to use?"
                        )
                        st.write("Clarification needed")
                    elif plan["decision"] == "unsupported":
                        result = {}
                        answer = plan["limitation"] or (
                            "This question cannot be answered with the promotion "
                            "heatmap endpoint."
                        )
                        st.write("Question is outside the heatmap's capabilities")
                    else:
                        agent = SkaiAgent(service, llm, model)
                        result = agent.execute(plan)
                        st.write("SKAI analysis complete")
                        answer = agent.answer(question, plan, result)
                service.close()
                st.markdown(_escape_currency_for_markdown(answer))
                with st.expander("Execution plan"):
                    st.json(plan)
                if show_raw:
                    with st.expander("Raw SKAI response"):
                        st.json(result)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                        "plan": plan,
                        "raw": result,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "tenant": tenant_code,
                        "model": model,
                    }
                )
            except Exception as exc:
                st.error(str(exc))
