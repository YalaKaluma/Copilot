from models.copilot.base import ToolInput, ToolParameter, ToolProperty
from models.copilot.orchestrators import OrchestratorStages


def orchestrator_move_stage(available_stage: OrchestratorStages) -> ToolInput:
    if available_stage == OrchestratorStages.done:
        return ToolInput(
            name="move_to_done",
            description=(
                "Call when you have data or an answer that addresses the user's question. "
                "Use to finish and present the result. Call this after an agent handoff returns "
                "the requested data—do not hand off again."
            ),
            parameters=ToolParameter(
                properties={
                    "answer": ToolProperty(
                        type="string",
                        description="Final user-facing answer to present.",
                    ),
                    "confidence": ToolProperty(
                        type="string",
                        description="Confidence in the answer given the data available.",
                        enum=["high", "medium", "low"],
                    ),
                    "assumptions_and_risks": ToolProperty(
                        type="string",
                        description="Brief summary of defaults used, data gaps, and material risks (e.g. cannibalization, baseline not available).",
                    ),
                },
                required=["answer"],
            ),
        )
    return ToolInput(
        name=f"move_to_{available_stage}",
        description=f"Move the orchestrator to the {available_stage} stage",
    )


def return_to_user_tool() -> ToolInput:
    """Tool for the orchestrator to return control to the user when execution cannot proceed.

    Used when:
    - A critical step fails and cannot be recovered
    - The request cannot be fulfilled as specified
    - The user needs to provide different information
    """
    return ToolInput(
        name="return_to_user",
        description="""Return control to the user when you cannot proceed with execution.

Use this when:
- A tool execution has failed and cannot be recovered
- You've already tried an alternative approach that also failed
- The user's request cannot be fulfilled as specified
- You need clarification or different input from the user

Do NOT use this for normal completion - use move_to_done instead.""",
        parameters=ToolParameter(
            properties={
                "reason": ToolProperty(
                    type="string",
                    description="Clear explanation of why execution cannot proceed. Include what you tried and what failed.",
                ),
                "suggestion": ToolProperty(
                    type="string",
                    description="Optional suggestion for what the user could do differently or provide to help.",
                ),
                "partial_results": ToolProperty(
                    type="string",
                    description="Optional summary of any results that were successfully obtained before the failure.",
                ),
            },
            required=["reason"],
        ),
    )
