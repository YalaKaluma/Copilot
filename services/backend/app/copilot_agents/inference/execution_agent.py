from typing import Any, AsyncGenerator, Awaitable, Callable, Sequence
from openai.types.responses import (
    ResponseCodeInterpreterToolCall,
    ResponseFunctionToolCall,
)
from pydantic import BaseModel
from packages.langfuse.types import LangfuseAsType
from core.exceptions import ToolExecutionError
from services.python_repl import PythonREPL
from services.tracing import observation_context
from services.skai_api import SKAIApi
from services.llm.openai_client import AsyncOpenaiClient
from ..core import Agent
import asyncio
import json
from config.versioning import ExecutionAgentConfig, ResolvedVersion
from models.copilot.base import (
    BuiltinToolInput,
    ChatEvent,
    Tool,
    ToolDefinition,
    ToolInput,
)
from core.logging import get_logger
from models.copilot.orchestrators import (
    OrchestratorEvent,
    OrchestratorEventType,
    OrchestratorStages,
)

logger = get_logger(__name__)


class ExecutionAgent(Agent):
    def __init__(
        self,
        session_id: str,
        chat_history: list[ChatEvent],
        llm_service: AsyncOpenaiClient,
        skai_service: SKAIApi,
        skai_tools: list[Tool],
        other_tools: list[Tool],
        handoff_tools: list[ToolDefinition],
        agent_config: ExecutionAgentConfig,
        version_config: ResolvedVersion,
        prompt_context: dict[str, str],
        python_repl: PythonREPL,
    ):
        super().__init__(
            session_id, chat_history, llm_service, skai_service, version_config
        )
        self._tools = skai_tools + other_tools

        self._handoff_tools = handoff_tools
        self._agent_config = agent_config
        self._prompt_context = prompt_context

        self._skai_tools = [skai_tool.definition.name for skai_tool in skai_tools]
        self._all_tool_mapping = {
            tool.definition.name: tool.executor for tool in self._tools
        }
        self.code_interpreter_mode = agent_config.code_interpreter_mode

        self.code_execution_container_id: str | None = None
        self.python_repl = python_repl

        self.skai_service: SKAIApi = skai_service

    def _event(
        self,
        event_type: OrchestratorEventType,
        content: str,
        **kwargs,
    ) -> OrchestratorEvent:
        metadata = kwargs.pop("metadata", {}) or {}
        if "agent" not in metadata:
            metadata = {**metadata, "agent": self._agent_config.name}
        return OrchestratorEvent(
            event_type=event_type,
            content=content,
            stage=OrchestratorStages.execution,
            metadata=metadata,
            **kwargs,
        )

    async def _execute_single_tool(
        self,
        tool_call: ResponseFunctionToolCall,
        executor: Callable[
            ...,
            Awaitable[BaseModel | dict[str, Any]],
        ],
    ) -> dict[str, Any]:
        """Execute a single tool and return the result as a dictionary.

        Does not modify chat_history — the caller batches all results.
        """
        arguments = json.loads(tool_call.arguments)
        with observation_context(
            name=tool_call.name,
            as_type=LangfuseAsType.TOOL.value,
            input=arguments,
            session_id=self.session_id,
        ) as tool_span:
            try:
                if tool_call.name in self._skai_tools:
                    processed_args = {"agent": self, "args": arguments}
                else:
                    processed_args = {"agent": self, **arguments}
                tool_data = await executor(**processed_args)

                if isinstance(tool_data, dict):
                    result_json = tool_data
                else:
                    result_json = tool_data.model_dump(mode="json")
                if tool_span:
                    tool_span.update(output=result_json)
                return result_json
            except Exception as e:
                logger.error(
                    f"{self._agent_config.name} tool {tool_call.name} failed: {e}"
                )
                if tool_span:
                    tool_span.update(
                        level="ERROR",
                        status_message=f"Tool {tool_call.name} failed: {str(e)}",
                    )
                raise ToolExecutionError(tool_call.name, e)

    def _build_prompt_messages(self) -> list[ChatEvent]:
        """Build system prompt messages: versioned if available, else code-built."""

        agent_content = self._version_config.get_prompt(
            key=self._agent_config.name,
            context=self._prompt_context,
        )

        return [
            ChatEvent(role="system", content=agent_content),
        ]

    # TODO: add this back if required later or remove completely
    # async def summarise_data(
    #     self,
    #     data: dict[str, Any] | list[dict[str, Any]],
    #     instructions: str,
    #     tool_name: str,
    # ) -> str:
    #     prompt_context = {
    #         "source_data": json.dumps(data),
    #         "instruction_set": instructions,
    #         "data_type": tool_name,
    #     }

    #     summarisation_content = self._version_config.get_prompt(
    #         key="data_summarisation",
    #         context=prompt_context,
    #     )

    #     if not summarisation_content:
    #         raise ValueError("Summarisation prompt not found")

    #     summarisation_messages = [
    #         ChatEvent(role="user", content=summarisation_content),
    #     ]

    #     with observation_context(
    #         name="summarise_data",
    #         as_type=LangfuseAsType.GENERATION.value,
    #         input_messages=summarisation_messages,
    #         session_id=self.session_id,
    #     ) as span:
    #         summarisation_response = await self.llm_service.request(
    #             chat_history=summarisation_messages,
    #             model="gpt-5-mini",
    #         )
    #         summary = summarisation_response.output_text
    #         if span:
    #             span.update(output=summary)
    #     return summary

    def _get_all_tools(self) -> Sequence[ToolDefinition]:
        all_tools: Sequence[ToolDefinition] = [i.definition for i in self._tools]

        all_tools.extend(self._handoff_tools)
        if (
            self.code_interpreter_mode is not None
            and self.code_interpreter_mode == "openai"
            and self.code_execution_container_id
        ):
            all_tools.append(
                BuiltinToolInput(
                    container=self.code_execution_container_id,
                )
            )
        return all_tools

    async def _execute(self, question: str):
        logger.info(
            f"{self._agent_config.name} executing question: {question[:100]}..."
        )
        self.chat_history.append(ChatEvent(role="user", content=question))

        if (
            self.code_interpreter_mode is not None
            and self.code_interpreter_mode == "openai"
        ):
            self.code_execution_container_id = (
                await self.llm_service.create_or_get_container(
                    name=f"code-interpreter-{self._agent_config.name}",
                    memory_limit="1g",
                    container_id=self.code_execution_container_id,
                )
            )

        all_tools = self._get_all_tools()
        handoff_inputs: list[ToolInput] = [
            tool for tool in self._handoff_tools if isinstance(tool, ToolInput)
        ]
        handoff_names = {tool.name for tool in handoff_inputs}
        iteration = 0

        trace_tools: list[ToolInput] = [
            tool for tool in all_tools if isinstance(tool, ToolInput)
        ]

        base_input_messages = self._build_prompt_messages()

        while True:
            iteration += 1
            logger.info(f"{self._agent_config.name} iteration {iteration}")

            input_messages = base_input_messages + self.chat_history

            handoff_arguments = None
            handoff_tool_name = None
            with observation_context(
                name="request_tool_call",
                as_type=LangfuseAsType.GENERATION.value,
                model=self._version_config.config.model.model_id,
                input_messages=input_messages,
                session_id=self.session_id,
                tools=trace_tools,
            ) as span:
                tool_responses = await self.llm_service.request_tools_batch(
                    input_messages,
                    self._version_config.config.model.model_id,
                    tools=all_tools,
                    reasoning_effort="none",  # TODO: add this in versioning config later
                )

                if not tool_responses.tools and not tool_responses.text:
                    logger.warning(
                        f"{self._agent_config.name} received empty response from LLM at iteration {iteration}, retrying"
                    )
                    if span:
                        span.update(
                            level="ERROR",
                            status_message="No responses returned from LLM",
                        )
                    continue
                else:
                    if span:
                        span.update(output=tool_responses.model_dump(mode="json"))

            # If no function calls, handle the non-function response
            if not tool_responses.tools:
                if tool_responses.text:
                    handoff_arguments = {
                        "answer": tool_responses.text,
                        "actions": [],
                        "allow_other": False,
                    }
                    handoff_tool_name = handoff_inputs[0].name
                else:
                    logger.info(
                        f"{self._agent_config.name} got message instead of tool call, prompting hand_back"
                    )
                    self.chat_history.append(
                        ChatEvent(
                            role="assistant",
                            content="You must call hand_back with your answer if it is ready. Otherwise, continue calling tools.",
                        )
                    )
                    continue

            code_calls: list[ResponseCodeInterpreterToolCall] = []
            function_calls: list[ResponseFunctionToolCall] = []
            for item in tool_responses.tools:
                if isinstance(item, ResponseCodeInterpreterToolCall):
                    code_calls.append(item)
                elif isinstance(item, ResponseFunctionToolCall):
                    if item.name in handoff_names:
                        handoff_arguments = json.loads(item.arguments)
                        handoff_tool_name = item.name
                    else:
                        function_calls.append(item)

            if code_calls:
                logger.info(
                    f"{self._agent_config.name} received {len(code_calls)} code interpreter call(s)"
                )

                result_payload = (
                    tool_responses.text or "No results from code interpreter"
                )
                code_snippets = []
                for call in code_calls:
                    code_snippets.append(call.code)
                yield self._event(
                    event_type=OrchestratorEventType.tool_call,
                    content="code_interpreter called",
                    tool_name="code_interpreter",
                    tool_args={"code": code_snippets, "called_times": len(code_calls)},
                )
                yield self._event(
                    event_type=OrchestratorEventType.tool_result,
                    content="code_interpreter completed",
                    tool_name="code_interpreter",
                    tool_result={"result": result_payload},
                )

                self.chat_history.append(
                    ChatEvent(
                        role="system",
                        content=f"[Called code_interpreter {len(code_calls)} times]",
                    )
                )
                self.chat_history.append(
                    ChatEvent(
                        role="tool",
                        content=f"Code interpreter completed with result: {result_payload}",
                    )
                )
            if (num_regular := len(function_calls)) > 0:
                logger.info(
                    f"{self._agent_config.name} executing {num_regular} tool(s) in parallel: "
                    f"{[c.name for c in function_calls]}"
                )

                # Validate all tool names exist before executing any
                unknown = [
                    c.name
                    for c in function_calls
                    if c.name not in self._all_tool_mapping
                ]
                if unknown:
                    logger.error(f"{self._agent_config.name} unknown tools: {unknown}")
                    yield self._event(
                        event_type=OrchestratorEventType.error,
                        content=f"Unknown tools requested: {unknown}",
                    )
                    yield self._event(
                        event_type=OrchestratorEventType.tool_result,
                        content="hand_back completed",
                        tool_name=handoff_inputs[0].name,
                        tool_result={
                            "answer": f"Internal error: unknown tools {unknown}.",
                        },
                    )
                    return

                # Yield tool_call events for all tools
                tasks = []
                for fc in function_calls:
                    tasks.append(
                        self._execute_single_tool(
                            fc,
                            self._all_tool_mapping[fc.name],
                        )
                    )
                    yield self._event(
                        event_type=OrchestratorEventType.tool_call,
                        content=f"{fc.name} called",
                        tool_name=fc.name,
                        tool_args=json.loads(fc.arguments),
                    )

                try:
                    results = await asyncio.gather(*tasks)
                except ToolExecutionError as e:
                    logger.error(
                        f"{self._agent_config.name} tool execution failed: {e}"
                    )
                    yield self._event(
                        event_type=OrchestratorEventType.error,
                        content=str(e),
                        tool_name=e.tool_name,
                    )
                    yield self._event(
                        event_type=OrchestratorEventType.tool_result,
                        content="hand_back completed",
                        tool_name=handoff_inputs[0].name,
                        tool_result={
                            "answer": f"{str(e)}. User may need to update parameters or try again.",
                            "actions": [
                                "Adjust parameters",
                                "Try a different question",
                            ],
                        },
                    )
                    return

                for fc, result_json in zip(function_calls, results):
                    tool_name = fc.name
                    tool_id = fc.call_id
                    tool_result_content = json.dumps(result_json)
                    self.chat_history.append(
                        ChatEvent(
                            role="system",
                            content=f"[Called {tool_name} with tool call ID {tool_id}]",
                        )
                    )
                    self.chat_history.append(
                        ChatEvent(
                            role="tool",
                            tool_call_id=tool_id,
                            content=tool_result_content,
                        )
                    )
                    logger.info(
                        f"{self._agent_config.name} appended {tool_name} result to chat_history ({len(tool_result_content)} chars)"
                    )
                    yield self._event(
                        event_type=OrchestratorEventType.tool_result,
                        content=f"{tool_name} completed",
                        tool_name=tool_name,
                        tool_result=result_json,
                    )

                # If model also sent hand_back alongside regular tools, ignore it —
                # the model pre-formulated the answer before seeing actual results.
                # Let the loop continue so it can hand_back after seeing the data.
                if handoff_arguments is not None:
                    logger.info(
                        f"{self._agent_config.name} ignoring premature hand_back alongside "
                        f"{num_regular} tool calls; will re-prompt after results"
                    )
                continue

            # Pure handoff with no regular tools or with code interpreter
            if handoff_arguments is not None:
                logger.info(f"{self._agent_config.name} handing back")
                self.chat_history.append(
                    ChatEvent(
                        role="assistant",
                        content=f"""
                        ## Final Answer

                        {handoff_arguments["answer"]}
                        """,
                    )
                )
                yield self._event(
                    event_type=OrchestratorEventType.tool_call,
                    content="hand_back called",
                    tool_name=handoff_tool_name,
                    tool_args={"question": question, "iteration": iteration},
                )
                yield self._event(
                    event_type=OrchestratorEventType.tool_result,
                    content="hand_back completed",
                    tool_name=handoff_tool_name,
                    tool_result=handoff_arguments,
                )
                return

        # Loop only exits via hand_back return, text only return or error return above

    async def execute(self, question: str) -> AsyncGenerator[OrchestratorEvent, None]:
        with observation_context(
            name=f"{self._agent_config.name}_execute",
            as_type=LangfuseAsType.AGENT.value,
            input={"question": question},
            model=self._version_config.config.model.model_id,
            session_id=self.session_id,
        ) as span:
            event = None
            async for event in self._execute(question):
                yield event
            if span and event:
                span.update(output=event.model_dump(mode="json"))
