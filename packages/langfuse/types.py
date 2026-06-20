from enum import Enum


class LangfuseAsType(str, Enum):
    """
    The type of the observation.
    """

    SPAN = "span"
    TOOL = "tool"
    GENERATION = "generation"
    AGENT = "agent"
    CHAIN = "chain"
    RETRIEVER = "retriever"
    EMBEDDING = "embedding"
    EVENT = "event"
    GUARDRAIL = "guardrail"
    EVALUATOR = "evaluator"
