"""Exposes Assistant and AgentLoop over HTTP for manual tests."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from langchain_core.messages import ToolCall

from harness.agent_loop import AgentLoop
from harness.assistant import Assistant
from harness.run_result import RunResult


class TestController:
    """Exposes ``Assistant`` and ``AgentLoop`` over HTTP for manual tests.

    It plays the part of the Spring ``@RestController``. Each ``add_api_route`` line plays
    the part of one ``@GetMapping``.

    Example: ``GET http://localhost:8080/askAutoToolCall?input=how many error events in checkout service?``
    """

    def __init__(self, assistant: Assistant, agent_loop: AgentLoop) -> None:
        self.assistant = assistant
        self.agent_loop = agent_loop
        self.router = APIRouter()
        self.router.add_api_route("/askAutoToolCall", self.ask_auto_tool_call, response_class=PlainTextResponse)
        self.router.add_api_route("/askHaltToolCall", self.ask_halt_tool_call)
        self.router.add_api_route("/run", self.run)

    def ask_auto_tool_call(self, input: str) -> str:
        """Sends the question to the model. The agent runs the tools.

        Args:
            input: the question; the request fails without it

        Returns:
            the model's text reply
        """
        return self.assistant.ask_auto_tool_call(input)

    def ask_halt_tool_call(self, input: str) -> list[ToolCall]:
        """Sends the question to the model and returns its tool calls without running them.

        Args:
            input: the question; the request fails without it

        Returns:
            the tool calls as JSON: name, args, id, and type
        """
        return self.assistant.ask_halt_tool_call(input)

    def run(self, input: str) -> RunResult:
        """Runs the handwritten agent loop for the question.

        Args:
            input: the question; the request fails without it

        Returns:
            the run result as JSON: answer, reason, steps, and tokens
        """
        return self.agent_loop.run(input)
