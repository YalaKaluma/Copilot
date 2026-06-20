from typing import Literal
from pydantic import BaseModel, Field, model_validator


class IntentClassificationResponse(BaseModel):
    """Response for the intent classification
    Must provide either the archetype or the clarification question and user actions
    """

    reasoning: str | None = Field(
        None,
        description="The reasoning for the intent classification",
    )
    archetype: Literal["A1", "A2", "A3", "A4", "A5", "A6"] | None = Field(
        None, description="The archetype of the user's request if it can be determined"
    )
    domain_label: Literal["D1", "D2", "D3", "D4", "D5", "D6", "DX"] | None = Field(
        None,
        description="The domain label of the user's request if it can be determined",
    )
    clarification_question: str | None = Field(
        None,
        description="The question to ask the user to clarify the request when the archetype is not determined",
    )
    user_actions: list[str] | None = Field(
        None,
        description="The options the user can choose from to answer the question when the archetype is not determined",
    )

    @model_validator(mode="after")
    def validate_required_fields(self) -> "IntentClassificationResponse":
        if self.archetype is None and self.clarification_question is None:
            raise ValueError(
                "Must provide either the archetype or the clarification question"
            )
        return self
