"""Orchestrator tool to send a chart to the frontend for display in the Charts pane."""

from models.copilot.base import ToolInput, ToolParameter, ToolProperty, ToolPropertyItem


def create_show_chart() -> ToolInput:
    """Create the show_chart tool definition.

    Use when the user asks for a chart or visualization. The chart is displayed
    in the right-pane Charts section. Keep data small (e.g. up to ~10 points).
    """
    return ToolInput(
        name="show_chart",
        description="""Display a chart in the right pane for the user. Use when:
- The user asks for a chart, graph, or visualization
- You have data (e.g. from analysis or handoff) that fits a bar, line, or pie chart
- You want to show a simple comparison (e.g. by brand, region, period)

Provide a short title, chart type (bar/line/pie), and data_points. Keep the number of points small (e.g. up to 10) for clarity.
After calling this, continue the workflow: call move_to_done with your summary for the user, or call another tool (e.g. handoff) for the next step. Do not end the turn with only a text message.""",
        parameters=ToolParameter(
            properties={
                "title": ToolProperty(
                    type="string",
                    description="Short title for the chart (e.g. 'Sales by region', 'Volume uplift by brand').",
                ),
                "chart_type": ToolProperty(
                    type="string",
                    description="Type of chart: 'bar', 'line', or 'pie'.",
                ),
                "data_points": ToolProperty(
                    type="array",
                    description="Data points for the chart. Use strings in 'label:value' form (e.g. ['Rolling 52W:1.23', 'Prior 52W:1.18']) or objects with 'label' and 'value' (e.g. [{\"label\": \"Brand A\", \"value\": 100}]). Labels with colons are supported.",
                    items=ToolPropertyItem(type="string"),
                ),
            },
            required=["title", "chart_type", "data_points"],
        ),
    )
