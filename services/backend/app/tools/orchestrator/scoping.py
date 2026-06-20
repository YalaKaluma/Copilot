from models.copilot.base import ToolInput, ToolParameter, ToolProperty, ToolPropertyItem


def create_request_more_info() -> ToolInput:
    """Create the request_more_information tool definition.

    This tool is used when the orchestrator needs clarification from the user.
    It should be used sparingly and with focused, specific questions.
    """
    return ToolInput(
        name="request_more_information",
        description="""Request specific clarification from the user. Use this SPARINGLY - only when:
1. Brand/product name is genuinely ambiguous (matches multiple entities)
2. The analysis type cannot be determined from context
3. A critical filter is needed that cannot be defaulted

Keep questions brief and offer specific options when possible. When you have clear options,
provide them as `actions` (up to 5) so the UI can render clickable choices. When using
`actions`, keep the question text free of the option list.

Example:
- question: "Which brand did you mean?"
- actions: ["Brand A", "Brand B (Premium)", "Brand B (Value)"]
NOT: "Please provide: 1) time period, 2) market scope, 3) category, 4) share type, 5) competitors..."
""",
        parameters=ToolParameter(
            properties={
                "question": ToolProperty(
                    type="string",
                    description="A brief, focused question for the user. Keep to 1-2 questions maximum.",
                ),
                "actions": ToolProperty(
                    type="array",
                    description="Up to 5 short action options the user can click. Use exact values from available data.",
                    items=ToolPropertyItem(type="string"),
                ),
                "allow_other": ToolProperty(
                    type="boolean",
                    description="Whether to allow a free-text response in addition to actions (default: true).",
                ),
                "enabler_category": ToolProperty(
                    type="string",
                    description="Which enabler this question gathers: objective, scope, or guardrails. Ask in order: objective then scope then guardrails.",
                    enum=["objective", "scope", "guardrails"],
                ),
            },
            required=["question"],
        ),
    )
