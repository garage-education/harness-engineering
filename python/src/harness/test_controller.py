"""Exposes Assistant over HTTP for manual tests."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from harness.assistant import Assistant


class TestController:
    """Exposes ``Assistant`` over HTTP for manual tests.

    It plays the part of the Spring ``@RestController``. Each ``add_api_route`` line plays
    the part of one ``@GetMapping``.

    Example: ``GET http://localhost:8080/askAutoToolCall?input=how many error events?``
    """

    def __init__(self, assistant: Assistant) -> None:
        self.assistant = assistant
        self.router = APIRouter()
        self.router.add_api_route("/askAutoToolCall", self.ask_auto_tool_call, response_class=PlainTextResponse)

    def ask_auto_tool_call(self, input: str) -> str:
        """Sends the ``input`` query parameter to the model.

        Args:
            input: the question; the request fails without it

        Returns:
            the model's text reply
        """
        return self.assistant.ask_auto_tool_call(input)
