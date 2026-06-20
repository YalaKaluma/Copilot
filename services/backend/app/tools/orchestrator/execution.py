from models.copilot.base import ChatEvent, ToolInput, ToolParameter, ToolProperty, Tool
from config.versioning import (
    ResolvedVersion,
    ExecutionAgentConfig,
)
from copilot_agents.inference.execution_agent import ExecutionAgent
from models.skai_api.autogen import FilterOptions
from services.python_repl import PythonREPL
from tools.agent.core import code_execution_tool
from services.llm.openai_client import AsyncOpenaiClient
from services.skai_api import SKAIApi
from tools.skai.tools import (
    OrchestratorHandoffTool,
    get_agent_tools_from_registry,
)


def _tools_for_agent(
    agent_config: ExecutionAgentConfig,
    filter_context: FilterOptions,
) -> list[Tool]:
    """Resolve tools for an execution agent from registry, optionally filtered by config."""

    tools = get_agent_tools_from_registry(filter_context, agent_config.domain)
    if agent_config.tools is None:
        return tools
    names = set(agent_config.tools)
    return [t for t in tools if t.definition.name in names]


def _create_execution_agent(
    session_id: str,
    chat_history: list[ChatEvent],
    llm_service: AsyncOpenaiClient,
    skai_service: SKAIApi,
    version_config: ResolvedVersion,
    agent_config: ExecutionAgentConfig,
    filter_context: FilterOptions,
    prompt_context: dict[str, str],
    python_repl: PythonREPL,
) -> ExecutionAgent:
    """Build an ExecutionAgent from version config and agent config (tools from registry)."""
    tools = _tools_for_agent(agent_config, filter_context)
    other_tools: list[Tool] = []
    if (
        agent_config.code_interpreter_mode is not None
        and agent_config.code_interpreter_mode == "local"
    ):
        other_tools.append(code_execution_tool())

    handoff_tools = [OrchestratorHandoffTool]
    return ExecutionAgent(
        session_id=session_id,
        chat_history=chat_history,
        llm_service=llm_service,
        skai_service=skai_service,
        skai_tools=tools,
        other_tools=other_tools,
        handoff_tools=handoff_tools,
        version_config=version_config,
        agent_config=agent_config,
        prompt_context=prompt_context,
        python_repl=python_repl,
    )


def generate_handoffs(
    session_id: str,
    llm_service: AsyncOpenaiClient,
    skai_service: SKAIApi,
    version_config: ResolvedVersion,
    filter_context: FilterOptions,
    prompt_context: dict[str, str],
    python_repl: PythonREPL,
) -> list[Tool]:
    """Generate handoff tools from version config execution_agents and registry."""

    agent_configs = version_config.config.execution_agents

    handoff_tools: list[Tool] = []
    for agent_config in agent_configs:
        description = agent_config.description

        agent = _create_execution_agent(
            session_id,
            [],
            llm_service,
            skai_service,
            version_config=version_config,
            agent_config=agent_config,
            filter_context=filter_context,
            prompt_context=prompt_context,
            python_repl=python_repl,
        )

        def _make_executor(
            exec_agent: ExecutionAgent,
        ):
            def executor(**kwargs: str):
                question = kwargs.get("question", "")

                return exec_agent.execute(question)

            return executor

        handoff_tools.append(
            Tool(
                definition=ToolInput(
                    name=f"{agent_config.domain}_agent_handoff",
                    description=description,
                    parameters=ToolParameter(
                        properties={
                            "question": ToolProperty(
                                type="string",
                                description=f"The question you want the {agent_config.name} to answer",
                            )
                        },
                        required=["question"],
                    ),
                ),
                executor=_make_executor(agent),
            )
        )
    return handoff_tools
