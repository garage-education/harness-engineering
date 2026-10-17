"""Sends one question to the chat model, with the tools in LogTools."""

import logging
from typing import Final

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolCall

from harness.guardrails import Guardrails
from harness.log_tools import LogTools
from harness.observation_logging import ToolExecutionHandler
from harness.safe_guard_middleware import SafeGuardMiddleware
from harness.tool_support import tools_from

log: Final = logging.getLogger(__name__)


class Assistant:
    """Sends one question to the chat model, with the tools in ``LogTools``.

    The two methods send the same request. They differ in who runs the tool:

    - ``ask_auto_tool_call`` lets a LangChain agent run each tool call and returns the final text.
    - ``ask_halt_tool_call`` stops after the first reply and returns the tool calls, unrun.

    The constructor receives the chat model and the tools, like Spring's constructor injection.
    """

    SYSTEM: Final = "You are a careful assistant. Answer in two sentences or fewer."

    def __init__(self, chat: BaseChatModel, log_tools: LogTools) -> None:
        self.chat = chat
        self.log_tools = log_tools
        self.agent = create_agent(
            chat,
            tools=tools_from(log_tools),
            system_prompt=self.SYSTEM,
            middleware=[SafeGuardMiddleware(Guardrails.BLOCKED_WORDS)],
        ).with_config(callbacks=[ToolExecutionHandler()])

    def ask_auto_tool_call(self, question: str) -> str:
        """Asks the model one question and lets the agent run the tools.

        ``create_agent`` builds a loop. It runs each tool call, sends the result back to the
        model, and repeats until the reply has no tool calls.

        ``SafeGuardMiddleware`` blocks a question that contains a word from ``Guardrails.BLOCKED_WORDS``.
        It returns a fixed text without calling the model.

        Args:
            question: the user's question, in plain text

        Returns:
            the model's final text reply
        """
        log.debug("[auto] LangChain runs every tool call. Question: %s", question)
        state = self.agent.invoke({"messages": [HumanMessage(question)]})
        answer: str = state["messages"][-1].text
        log.debug("[auto] Final answer: %s", answer)
        return answer

    def ask_halt_tool_call(self, question: str) -> list[ToolCall]:
        """Asks the model one question and stops before any tool runs.

        ``bind_tools`` sends the tool definitions with the request. No agent runs them.
        The model's tool calls come back to this code as data.

        Args:
            question: the user's question, in plain text

        Returns:
            the tool calls the model requested; empty when it answered in text
        """
        log.debug("[halt] No agent. No tool will run. Question: %s", question)
        reply = self.chat.bind_tools(tools_from(self.log_tools)).invoke([SystemMessage(self.SYSTEM), HumanMessage(question)])
        if reply.tool_calls:
            for call in reply.tool_calls:
                log.debug("[halt] Model requested %s %s. Not run.", call["name"], call["args"])
        else:
            log.debug("[halt] Model answered in text, with no tool call: %s", reply.text)
        return reply.tool_calls
