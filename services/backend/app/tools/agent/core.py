from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from pydantic import BaseModel

from copilot_agents.core import Agent
from core.exceptions import ToolExecutionError
from core.logging import get_logger
from models.copilot.base import (
    BuiltinToolInput,
    Tool,
    ToolInput,
    ToolParameter,
    ToolProperty,
    ToolPropertyItem,
)
from packages.langfuse.types import LangfuseAsType
from services.tracing import observation_context

logger = get_logger(__name__)


def generate_hand_back():
    return ToolInput(
        name="hand_back",
        description="Hand back to the orchestrator with a short answer. Keep it concise: 1–3 sentences. Your analysis or a brief 'no data' message. Do not repeat full parameters or long explanations. If the user must choose next steps, include up to 5 `actions`.",
        parameters=ToolParameter(
            properties={
                "answer": ToolProperty(
                    type="string",
                    description="Short answer (1–3 sentences). Your key finding or a brief message if no data. Be concise.",
                ),
                "actions": ToolProperty(
                    type="array",
                    description="Optional: up to 5 short action options user can select when you cannot answer the question fully",
                    items=ToolPropertyItem(type="string"),
                    nullable=True,
                ),
                "allow_other": ToolProperty(
                    type="boolean",
                    description="Optional: whether to allow free-text response in addition to actions (default true).",
                    nullable=True,
                ),
            },
            required=["answer"],
        ),
    )


def generate_code_interpreter_tool() -> BuiltinToolInput:
    return BuiltinToolInput(
        type="code_interpreter",
        container={
            "type": "auto",
            "memory_limit": "1g",
        },
    )


async def _execute_code(agent: Agent, code: str, **kwargs: Any) -> dict[str, Any]:
    """Run Python code in a subprocess; return stdout and stderr.

    Uses a REPL-style wrapper so that a trailing expression (e.g. len(df))
    is evaluated and printed to stdout, not only explicit print() calls.
    """
    python_repl = agent.python_repl
    if python_repl is None:
        raise ValueError("Local code execution is unavailable for this agent.")
    result = python_repl.run(code)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "ok": result.ok,
    }


#     proc = await asyncio.create_subprocess_exec(
#         "uv",
#         "run",
#         "python",
#         "-u",
#         "-c",
#         _REPL_WRAPPER,
#         stdin=asyncio.subprocess.PIPE,
#         stdout=asyncio.subprocess.PIPE,
#         stderr=asyncio.subprocess.PIPE,
#     )
#     try:
#         stdout, stderr = await asyncio.wait_for(
#             proc.communicate(input=code.encode("utf-8")),
#             timeout=30.0,
#         )
#     except asyncio.TimeoutError:
#         proc.kill()
#         await proc.wait()
#         return {
#             "stdout": "(process timed out)",
#             "stderr": "Execution timed out after 30 seconds.",
#             "returncode": 1,
#         }
#     out = stdout.decode("utf-8", errors="replace")
#     err = stderr.decode("utf-8", errors="replace")
#     return {
#         "stdout": out,
#         "stderr": err,
#         "returncode": proc.returncode,
#     }


# _REPL_WRAPPER = """
# import ast
# import sys
# code = sys.stdin.read()
# namespace = {}
# try:
#     tree = ast.parse(code)
# except SyntaxError:
#     exec(code, namespace)
#     sys.exit(0)
# if not tree.body:
#     sys.exit(0)
# last = tree.body[-1]
# if isinstance(last, ast.Expr):
#     if len(tree.body) > 1:
#         mod = ast.Module(body=tree.body[:-1], type_ignores=[])
#         exec(compile(mod, "<user>", "exec"), namespace)
#     result = eval(compile(ast.Expression(body=last.value), "<user>", "eval"), namespace)
#     print(result)
# else:
#     exec(code, namespace)
# """


def code_execution_tool() -> Tool:
    return Tool(
        definition=ToolInput(
            name="code_execution",
            description="Execute the given code in python sandbox and return the result.",
            parameters=ToolParameter(
                properties={
                    "code": ToolProperty(
                        type="string", description="The code to execute."
                    ),
                },
                required=["code"],
            ),
        ),
        executor=_execute_code,
    )


async def execute_tool_for_agent(
    agent: Agent,
    tool_name: str,
    arguments: dict[str, Any],
    executor: Callable[..., Awaitable[BaseModel | dict[str, Any]]],
    skai_tool_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Execute a Tool executor consistently across agent types."""

    skai_tool_name_set = set(skai_tool_names)
    with observation_context(
        name=tool_name,
        as_type=LangfuseAsType.TOOL.value,
        input=arguments,
        session_id=agent.session_id,
    ) as tool_span:
        try:
            if tool_name in skai_tool_name_set:
                processed_args = {"agent": agent, "args": arguments}
            else:
                processed_args = {"agent": agent, **arguments}
            tool_data = await executor(**processed_args)
            result_json = (
                tool_data
                if isinstance(tool_data, dict)
                else tool_data.model_dump(mode="json")
            )
            if tool_span:
                tool_span.update(output=result_json)
            return result_json
        except Exception as exc:
            logger.error("Tool %s failed: %s", tool_name, exc)
            if tool_span:
                tool_span.update(
                    level="ERROR",
                    status_message=f"Tool {tool_name} failed: {str(exc)}",
                )
            raise ToolExecutionError(tool_name, exc) from exc
