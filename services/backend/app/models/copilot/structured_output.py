from pydantic import BaseModel, ConfigDict, Field


class Scope(BaseModel):
    """Confirmed scope from the scoping phase.

    Note: All fields are required for OpenAI structured output compatibility.
    Use empty lists/strings for "not applicable" cases.
    """

    model_config = ConfigDict(extra="forbid")

    # What the user is asking about
    question_summary: str = Field(
        description="A clear, concise summary of what the user is asking"
    )
    analysis_type: str = Field(
        description="The type of analysis needed (e.g., 'market share', 'pricing', 'promo effectiveness', 'category trends')"
    )

    # Key entities identified
    brands: list[str] = Field(
        description="Specific brands mentioned or identified (empty list if not applicable)"
    )
    categories: list[str] = Field(
        description="Categories or subcategories in scope (empty list if not specified)"
    )

    # Filters and constraints
    time_period: str = Field(
        description="Time period for analysis (e.g., 'L12', 'Q4 2024', 'YTD')"
    )
    retailers: list[str] = Field(
        description="Specific retailers in scope (empty list for all retailers)"
    )
    channels: list[str] = Field(
        description="Specific channels in scope (empty list for all channels)"
    )

    # Additional context
    additional_filters: str = Field(
        description="Any other filters or constraints identified (empty string if none)"
    )
    assumptions_made: list[str] = Field(
        description="Key assumptions or defaults applied (e.g., 'Defaulted to value share')"
    )


class Plan(BaseModel):
    """Execution plan for the orchestrator."""

    model_config = ConfigDict(extra="forbid")

    steps: list[str] = Field(
        description="Ordered list of execution steps. Each step should describe WHAT data or analysis is needed (e.g., 'Retrieve market share data for Brand X in the Snacks category for L12') and WHY it contributes to answering the question. Typically 2-5 steps for most questions."
    )
