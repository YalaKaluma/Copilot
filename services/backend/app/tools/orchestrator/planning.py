from models.copilot.base import (
    ToolInput,
    ToolParameter,
    ToolProperty,
    ToolPropertyItem,
)


def create_plan() -> ToolInput:
    """Create a tool that publishes the execution plan to the orchestrator."""
    return ToolInput(
        name="create_plan",
        description=(
            "Publish the execution plan after scoping is complete. "
            "Provide an ordered list of steps."
        ),
        parameters=ToolParameter(
            properties={
                "steps": ToolProperty(
                    type="array",
                    items=ToolPropertyItem(type="string"),
                    description="Ordered list of execution steps.",
                ),
                "assumptions_used": ToolProperty(
                    type="array",
                    items=ToolPropertyItem(type="string"),
                    description="Optional. Key defaults or assumptions applied (e.g. 'Time range: L12', 'Objective: profit/ROI').",
                ),
            },
            required=["steps"],
        ),
    )


def create_plan_update() -> ToolInput:
    return ToolInput(
        name="plan_update",
        description=(
            "Mark the next incomplete plan steps as completed and return the updated plan "
            "formatted as markdown. Provide the step numbers in the order they were completed."
        ),
        parameters=ToolParameter(
            properties={
                "step_numbers": ToolProperty(
                    type="array",
                    items=ToolPropertyItem(type="integer"),
                    description="Ordered list of step numbers to mark as completed.",
                ),
            },
            required=["step_numbers"],
        ),
    )
