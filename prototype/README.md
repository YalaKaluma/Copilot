# SKAI Growth Streamlit prototype

This folder extracts the smallest useful slice of the full copilot:

1. `skai_auth.py` signs in through SKAI's Cognito user pool.
2. `skai_service.py` uses the temporary bearer token to call SKAI.
3. `orchestrator.py` converts a question into a visible, structured plan.
4. `agent.py` executes the plan and produces an evidence-grounded answer.
5. `app.py` provides the Streamlit chat UI.
6. `pricing_workspace.py` adds the pricing decision workspace around the unchanged
   Copilot flow: Home, Hypotheses, Opportunities, and Sell-in Stories.

The pricing workspace uses realistic in-session mock hypotheses and scenario
results where a live analytical capability is not yet connected. Pursuing a
hypothesis creates a traceable opportunity; approving a scenario creates a
sell-in story. The pricing simulator remains behind the experience rather than
being exposed as a user-operated screen.

The prototype supports `GET /api/v1/promo/heatmap`,
`GET /api/v1/pricing/market-landscape`, `GET /api/v1/pricing/brand-ladder`,
`GET /api/v1/pricing/simulator/base`, and
`POST /api/v1/pricing/simulator/run`. It also calls `GET /api/v1/filter-values` so
the planner uses valid SKAI dimensions and filters.

Both endpoints use `SKAI_API_URL` by default. `SKAI_MARKET_API_URL` is only an
optional override for deployments that expose Market Landscape on a separate,
currently resolvable gateway.

## Run

From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

Fill `.env` with `SKAI_API_URL`, the three `SKAI_COGNITO_*` settings, and
optionally `OPENAI_API_KEY`. Enter your personal SKAI username and password in
the sidebar; values entered only in the sidebar are not written to disk.

For local convenience, `SKAI_USERNAME` and `SKAI_PASSWORD` can also be stored in
`.env`, which is excluded from Git. When set, the sidebar fields are populated
automatically. Treat this as plaintext local credential storage and use it only
on a trusted computer.

After login, the app reads tenant groups from the Cognito token and presents a
workspace selector. The selected code is sent to SKAI as `X-Tenant-Code` on all
filter and analytical requests. `SKAI_TENANT_CODE` optionally sets the initial
workspace.

When `SKAI_USERNAME` and `SKAI_PASSWORD` are present in `.env`, authentication
runs automatically once per Streamlit session, so the workspace dropdown is
visible immediately. The reconnect button remains available for expired tokens
or changed credentials.

## Flow

```text
Question -> Orchestrator -> JSON plan -> SKAI agent -> SKAI API -> grounded answer
```

The plan and optional raw response stay visible in the UI, which makes it easy
to check whether a wrong answer came from question interpretation, API filters,
or answer synthesis.

## Continuous improvement feedback

After the conversation contains at least one message, the sidebar offers a
downloadable Excel feedback workbook. It includes a complete conversation log
and one review row per assistant response, with validated rating, issue category,
comments, suggested-answer, prompt/guideline-improvement, and review-status
fields. Return the completed workbook to group recurring issues and update the
guidance files or routing prompts.

## Agent guidance

The `guidance/` directory contains a heatmap-only adaptation of the original
copilot's orchestrator, promo-agent guardrails, and tool documentation. The
prototype loads these files at runtime. Questions outside the heatmap's evidence
boundary are explicitly qualified or declined rather than routed to unavailable
endpoints.
