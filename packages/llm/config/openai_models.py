"""OpenAI Models Configuration.

Whitelisted models + supported params for Responses API.
Updated: December 2025
"""

DEFAULT_MODEL = "gpt-5.2"

# Map legacy params -> Responses API params
PARAM_MAPPINGS = {
    "max_tokens": "max_output_tokens",
}

# Params allowed for all models
GLOBAL_ALLOWED_PARAMS = [
    "metadata",
    "instructions",
    "previous_response_id",
    "store",
    "seed",
]

MODELS = [
    # ============================================
    # GPT-5.2 Series (December 2025 - Latest)
    # ============================================
    {
        "id": "gpt-5.2",
        "aliases": ["gpt-5.2-thinking", "gpt-5.2-2025-12-11"],
        "name": "GPT-5.2",
        "purpose": "Most advanced frontier model for professional work and long-running agents",
        "supports": {
            "structured_outputs": True,
            "json_schema_strict": True,
            "tools": True,
            "vision": True,
            "reasoning": True,
        },
        "allowed_params": [
            "max_output_tokens",
            "response_format",
            "tools",
            "tool_choice",
            "seed",
            "reasoning",
            "metadata",
            "instructions",
        ],
        "defaults": {
            "max_output_tokens": 16384,
        },
    },
    {
        "id": "gpt-5.2-pro",
        "aliases": [],
        "name": "GPT-5.2 Pro",
        "purpose": "Extended reasoning for most complex professional tasks (Responses API only)",
        "supports": {
            "structured_outputs": True,
            "json_schema_strict": True,
            "tools": True,
            "vision": True,
            "reasoning": True,
        },
        "allowed_params": [
            "max_output_tokens",
            "response_format",
            "tools",
            "tool_choice",
            "seed",
            "reasoning",
            "metadata",
            "instructions",
        ],
        "defaults": {
            "max_output_tokens": 32768,
        },
    },
    # ============================================
    # GPT-5 Series (August 2025)
    # ============================================
    {
        "id": "gpt-5-mini",
        "aliases": ["gpt-5-mini-latest"],
        "name": "GPT-5 Mini",
        "purpose": "Best general-purpose model with great price/performance",
        "supports": {
            "structured_outputs": True,
            "json_schema_strict": True,
            "tools": True,
            "vision": True,
            "reasoning": True,
        },
        "allowed_params": [
            "max_output_tokens",
            "response_format",
            "tools",
            "tool_choice",
            "seed",
            "reasoning",
            "metadata",
            "instructions",
        ],
        "defaults": {
            "max_output_tokens": 1024,
        },
    },
    {
        "id": "gpt-5-nano",
        "aliases": ["gpt-5-nano-latest"],
        "name": "GPT-5 Nano",
        "purpose": "Ultra-low cost for classification and short replies",
        "supports": {
            "structured_outputs": True,
            "json_schema_strict": True,
            "tools": True,
            "vision": True,
            "reasoning": True,
        },
        "allowed_params": [
            "max_output_tokens",
            "response_format",
            "tools",
            "tool_choice",
            "seed",
            "reasoning",
            "metadata",
            "instructions",
        ],
        "defaults": {
            "max_output_tokens": 512,
        },
    },
    {
        "id": "gpt-5",
        "aliases": ["gpt-5-latest"],
        "name": "GPT-5",
        "purpose": "Flagship model (use gpt-5.2 for latest)",
        "supports": {
            "structured_outputs": True,
            "json_schema_strict": True,
            "tools": True,
            "vision": True,
            "reasoning": True,
        },
        "allowed_params": [
            "max_output_tokens",
            "response_format",
            "tools",
            "tool_choice",
            "seed",
            "reasoning",
            "metadata",
            "instructions",
        ],
        "defaults": {
            "max_output_tokens": 4096,
        },
    },
    # ============================================
    # O-Series Reasoning Models
    # ============================================
    {
        "id": "o4-mini",
        "aliases": ["o4-mini-latest"],
        "name": "O4 Mini",
        "purpose": "Cost-efficient deep reasoning for math/coding",
        "supports": {
            "structured_outputs": True,
            "json_schema_strict": True,
            "tools": True,
            "vision": True,
            "reasoning": True,
        },
        "allowed_params": [
            "temperature",
            "max_output_tokens",
            "response_format",
            "tools",
            "tool_choice",
            "seed",
            "reasoning",
            "metadata",
            "instructions",
        ],
        "defaults": {
            "temperature": 0.5,
            "max_output_tokens": 1536,
        },
    },
    {
        "id": "o3",
        "aliases": ["o3-latest"],
        "name": "O3",
        "purpose": "Premium reasoning model for complex tasks",
        "supports": {
            "structured_outputs": True,
            "json_schema_strict": True,
            "tools": True,
            "vision": False,
            "reasoning": True,
        },
        "allowed_params": [
            "max_output_tokens",
            "response_format",
            "tools",
            "tool_choice",
            "seed",
            "reasoning",
            "metadata",
            "instructions",
        ],
        "defaults": {
            "max_output_tokens": 2048,
        },
    },
    # ============================================
    # GPT-4o Series (Legacy but still available)
    # ============================================
    {
        "id": "gpt-4o",
        "aliases": ["gpt-4o-latest"],
        "name": "GPT-4o",
        "purpose": "Full-featured multimodal assistant",
        "supports": {
            "structured_outputs": True,
            "json_schema_strict": True,
            "tools": True,
            "vision": True,
            "reasoning": False,
        },
        "allowed_params": [
            "temperature",
            "max_output_tokens",
            "response_format",
            "tools",
            "tool_choice",
            "seed",
            "metadata",
            "instructions",
        ],
        "defaults": {
            "temperature": 0.7,
            "max_output_tokens": 2048,
        },
    },
    {
        "id": "gpt-4o-mini",
        "aliases": ["gpt-4o-mini-latest"],
        "name": "GPT-4o Mini",
        "purpose": "Low-cost multimodal chat",
        "supports": {
            "structured_outputs": True,
            "json_schema_strict": True,
            "tools": True,
            "vision": True,
            "reasoning": False,
        },
        "allowed_params": [
            "temperature",
            "max_output_tokens",
            "response_format",
            "tools",
            "tool_choice",
            "seed",
            "metadata",
            "instructions",
        ],
        "defaults": {
            "temperature": 0.7,
            "max_output_tokens": 1024,
        },
    },
]
