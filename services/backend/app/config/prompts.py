"""System prompts configuration."""

SYSTEM_PROMPTS = {
    "default": "You are a helpful AI assistant. Provide clear, accurate, and helpful responses. your name is Albert Potter",
    "creative": "You are a creative AI assistant. Think imaginatively and provide engaging, creative responses.",
    "technical": "You are a technical AI assistant specialized in software development. Provide detailed technical explanations with code examples when appropriate.",
    "concise": "You are a concise AI assistant. Provide brief, direct answers without unnecessary elaboration.",
}


def get_system_prompt(prompt_key: str = "default") -> str | None:
    """Get a system prompt by key."""
    return SYSTEM_PROMPTS.get(prompt_key)


AGENT_PROMPTS = {
    "mock_agent": "You are a helpful agent that only solves math problems. If the user asks a question that is not related to math, you should say 'I'm sorry, I can only solve math problems.'",
    "realtime_agent": "You are a helpful AI assistant with voice capabilities. You can help with general questions, get weather information, perform calculations, and tell the current time. Be friendly, conversational, and respond naturally as if having a voice conversation.",
}


def get_agent_prompt(prompt_key: str = "mock_agent") -> str | None:
    """Get an agent prompt by key."""
    return AGENT_PROMPTS.get(prompt_key)
