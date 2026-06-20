"""Unit tests for tools.orchestrator.execution."""

import pytest
from unittest.mock import MagicMock, patch

from config.versioning import (
    AgentModelConfig,
    CopilotVersionConfig,
    ExecutionAgentConfig,
    ResolvedVersion,
)
from models.copilot.base import Tool, ToolInput
from models.skai_api.autogen import FilterOptions, PackSizeFilter
from tools.orchestrator.execution import (
    _tools_for_agent,
    generate_handoffs,
)
from tools.skai.tools import AGENT_TOOL_REGISTRY


@pytest.fixture
def filter_options():
    """Create a filter options for tests."""
    return FilterOptions(
        sku_ids=["1", "2", "3"],
        brands=["1", "2", "3"],
        categories=["1", "2", "3"],
        subcategories=["1", "2", "3"],
        retailers=["1", "2", "3"],
        channels=["1", "2", "3"],
        price_tiers=["1", "2", "3"],
        pack_size=PackSizeFilter(uom="1", ranges=["1", "2", "3"]),
    )


@pytest.fixture
def mock_tool():
    """A minimal Tool for registry mocks."""
    return Tool(
        definition=ToolInput(
            name="skai_get_category_landscape",
            description="Get category landscape",
        ),
        executor=lambda api, args: {},
    )


@pytest.fixture
def mock_tool_filter():
    """Another minimal Tool."""
    return Tool(
        definition=ToolInput(
            name="skai_get_filter_values",
            description="Get filter values",
        ),
        executor=lambda api, args: {},
    )


@pytest.fixture
def execution_agent_config_none_tools():
    """ExecutionAgentConfig with tools=None (use full registry)."""
    return ExecutionAgentConfig(
        domain="category",
        name="category_agent",
        description="Category. Tools: {tools}",
        prompt_id="category_agent:v1",
        tools=None,
    )


@pytest.fixture
def execution_agent_config_filtered_tools():
    """ExecutionAgentConfig with specific tool names (must exist in registry for domain)."""
    return ExecutionAgentConfig(
        domain="category",
        name="category_agent",
        description="Category. Tools: {tools}",
        prompt_id="category_agent:v1",
        tools=["skai_get_category_landscape"],
    )


class TestToolsForAgent:
    """Tests for _tools_for_agent."""

    def test_tools_none_returns_all_from_registry(
        self, execution_agent_config_none_tools, filter_options
    ):
        tools = _tools_for_agent(execution_agent_config_none_tools, filter_options)
        # Registry values are callables: domain -> (FilterOptions -> list[Tool])
        expected_tools = AGENT_TOOL_REGISTRY["category"](filter_options)
        assert len(tools) == len(expected_tools)
        names = [t.definition.name for t in tools]
        assert (
            "skai_get_category_landscape" in names or "skai_get_filter_values" in names
        )

    def test_tools_list_filters_registry(
        self, execution_agent_config_filtered_tools, filter_options
    ):
        tools = _tools_for_agent(execution_agent_config_filtered_tools, filter_options)
        requested = {"skai_get_category_landscape"}
        for t in tools:
            assert t.definition.name in requested
        assert len(tools) >= 1

    def test_tools_nonexistent_names_returns_empty(self, filter_options):
        config = ExecutionAgentConfig(
            domain="category",
            name="category_agent",
            description="Tools: {tools}",
            prompt_id="category_agent:v1",
            tools=["nonexistent_tool_name_xyz"],
        )
        tools = _tools_for_agent(config, filter_options)
        assert len(tools) == 0

    def test_filter_options_incorporated_into_tool_parameter_enums(
        self, execution_agent_config_none_tools
    ):
        """Tools from _tools_for_agent have parameter enums from the given FilterOptions."""
        filter_options = FilterOptions(
            sku_ids=["SKU-A", "SKU-B"],
            brands=["Acme", "Globex"],
            categories=["Beverages", "Snacks"],
            subcategories=["Soda", "Chips"],
            retailers=["Store1", "Store2"],
            channels=["Grocery", "Convenience"],
            price_tiers=["Premium", "Value"],
            pack_size=PackSizeFilter(uom="oz", ranges=["12", "24"]),
        )
        tools = _tools_for_agent(execution_agent_config_none_tools, filter_options)
        # Category landscape uses common filter properties (brands, retailers, etc.)
        landscape = next(
            (t for t in tools if t.definition.name == "skai_get_category_landscape"),
            None,
        )
        assert landscape is not None
        params = landscape.definition.parameters
        assert params is not None
        props = params.properties
        assert "brands" in props
        assert props["brands"].type == "array"
        assert props["brands"].items.type == "string"
        assert props["brands"].items.enum == ["Acme", "Globex"]
        assert "retailers" in props
        assert props["retailers"].type == "array"
        assert props["retailers"].items.type == "string"
        assert props["retailers"].items.enum == ["Store1", "Store2"]
        assert "categories" in props
        assert props["categories"].type == "array"
        assert props["categories"].items.type == "string"
        assert props["categories"].items.enum == ["Beverages", "Snacks"]
        assert "subcategories" in props
        assert props["subcategories"].type == "array"
        assert props["subcategories"].items.type == "string"
        assert props["subcategories"].items.enum == ["Soda", "Chips"]
        assert "channels" in props
        assert props["channels"].type == "array"
        assert props["channels"].items.type == "string"
        assert props["channels"].items.enum == ["Grocery", "Convenience"]

    def test_different_filter_options_produce_different_tool_enums(
        self, execution_agent_config_none_tools
    ):
        """Changing FilterOptions changes the enums in tool definitions."""
        filter_a = FilterOptions(
            sku_ids=[],
            brands=["OnlyBrandA"],
            categories=[],
            subcategories=[],
            retailers=[],
            channels=[],
            price_tiers=[],
            pack_size=PackSizeFilter(uom="", ranges=[]),
        )
        filter_b = FilterOptions(
            sku_ids=[],
            brands=["OnlyBrandB"],
            categories=[],
            subcategories=[],
            retailers=[],
            channels=[],
            price_tiers=[],
            pack_size=PackSizeFilter(uom="", ranges=[]),
        )
        tools_a = _tools_for_agent(execution_agent_config_none_tools, filter_a)
        tools_b = _tools_for_agent(execution_agent_config_none_tools, filter_b)
        landscape_a = next(
            (t for t in tools_a if t.definition.name == "skai_get_category_landscape"),
            None,
        )
        landscape_b = next(
            (t for t in tools_b if t.definition.name == "skai_get_category_landscape"),
            None,
        )
        assert landscape_a is not None and landscape_b is not None
        brands_a = landscape_a.definition.parameters.properties["brands"].items.enum
        brands_b = landscape_b.definition.parameters.properties["brands"].items.enum
        assert brands_a == ["OnlyBrandA"]
        assert brands_b == ["OnlyBrandB"]


class TestGenerateHandoffs:
    """Tests for generate_handoffs."""

    @pytest.fixture
    def mock_version_config(self):
        """A real ResolvedVersion with minimal config so .config has all needed attributes."""
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Category. Tools: {tools}",
                    prompt_id="category_agent:v1",
                    tools=None,
                ),
            ],
            model=AgentModelConfig(model_id="gpt-5.2"),
            prompts={"base": "base:v1", "category_agent": "category_agent:v1"},
        )
        return ResolvedVersion(config=config, prompts_dir_root=None)

    def test_returns_list_of_tools(self, mock_version_config, filter_options):
        with patch("tools.orchestrator.execution.ExecutionAgent") as mock_agent_class:
            mock_agent_class.return_value.execute = MagicMock(return_value=MagicMock())
            handoffs = generate_handoffs(
                session_id="s1",
                llm_service=MagicMock(),
                skai_service=MagicMock(),
                version_config=mock_version_config,
                filter_context=filter_options,
                prompt_context={},
                python_repl=MagicMock(),
            )
        assert isinstance(handoffs, list)
        assert len(handoffs) == 1
        assert isinstance(handoffs[0], Tool)
        assert handoffs[0].definition.name == "category_agent_handoff"

    def test_handoff_has_question_parameter(self, mock_version_config, filter_options):
        with patch("tools.orchestrator.execution.ExecutionAgent"):
            handoffs = generate_handoffs(
                session_id="s1",
                llm_service=MagicMock(),
                skai_service=MagicMock(),
                version_config=mock_version_config,
                filter_context=filter_options,
                prompt_context={},
                python_repl=MagicMock(),
            )
        assert "question" in (handoffs[0].definition.parameters.properties or {})
        assert "question" in (handoffs[0].definition.parameters.required or [])

    def test_description_includes_tools_placeholder(
        self, mock_version_config, filter_options
    ):
        with patch("tools.orchestrator.execution.ExecutionAgent"):
            handoffs = generate_handoffs(
                session_id="s1",
                llm_service=MagicMock(),
                skai_service=MagicMock(),
                version_config=mock_version_config,
                filter_context=filter_options,
                prompt_context={},
                python_repl=MagicMock(),
            )
        desc = handoffs[0].definition.description
        assert "Category" in desc
        assert "Tools:" in desc

    def test_multiple_agents_return_multiple_handoff_tools(self, filter_options):
        """generate_handoffs returns one tool per execution_agent with correct names."""
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Category. Tools: {tools}",
                    prompt_id="category_agent:v1",
                    tools=None,
                ),
                ExecutionAgentConfig(
                    domain="channel",
                    name="channel_agent",
                    description="Channel. Tools: {tools}",
                    prompt_id="channel_agent:v1",
                    tools=None,
                ),
            ],
            model=AgentModelConfig(model_id="gpt-5.2"),
            prompts={
                "base": "base:v1",
                "category_agent": "category_agent:v1",
                "channel_agent": "channel_agent:v1",
            },
        )
        version_config = ResolvedVersion(config=config, prompts_dir_root=None)
        with patch("tools.orchestrator.execution.ExecutionAgent") as mock_agent:
            mock_agent.return_value.execute = MagicMock(return_value=MagicMock())
            handoffs = generate_handoffs(
                session_id="s1",
                llm_service=MagicMock(),
                skai_service=MagicMock(),
                version_config=version_config,
                filter_context=filter_options,
                prompt_context={},
                python_repl=MagicMock(),
            )
        assert len(handoffs) == 2
        names = {t.definition.name for t in handoffs}
        assert names == {"category_agent_handoff", "channel_agent_handoff"}

    def test_handoff_executor_calls_create_execution_agent_with_args(
        self, mock_version_config, filter_options
    ):
        """Handoff executor builds ExecutionAgent with session_id, filter_context, etc."""
        with patch(
            "tools.orchestrator.execution._create_execution_agent"
        ) as mock_create:
            mock_agent = MagicMock()
            mock_agent.execute = MagicMock(return_value=MagicMock())
            mock_create.return_value = mock_agent
            handoffs = generate_handoffs(
                session_id="session-123",
                llm_service=MagicMock(),
                skai_service=MagicMock(),
                version_config=mock_version_config,
                filter_context=filter_options,
                prompt_context={},
                python_repl=MagicMock(),
            )
            assert len(handoffs) == 1
            # Call executor inside the patch block so _create_execution_agent is mocked
            handoffs[0].executor(question="test question")
            mock_create.assert_called_once()
            args, kwargs = mock_create.call_args
            assert args[0] == "session-123"
            assert args[1] == []
            assert kwargs["filter_context"] is filter_options
            assert kwargs["agent_config"].domain == "category"
            assert kwargs["version_config"] is mock_version_config
