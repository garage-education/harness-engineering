"""Sends one question to the chat model, with the tools in LogTools."""

import logging
from typing import Final

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from harness.log_tools import LogTools
from harness.observation_logging import ToolExecutionHandler
from harness.tool_support import tools_from

log: Final = logging.getLogger(__name__)


class Assistant:
    """Sends one question to the chat model, with the tools in ``LogTools``."""

    SYSTEM: Final = "You are a careful assistant. Answer in two sentences or fewer."

    def __init__(self, chat: BaseChatModel, log_tools: LogTools) -> None:
        self.chat = chat
        self.log_tools = log_tools
        self.agent = create_agent(chat, tools=tools_from(log_tools), system_prompt=self.SYSTEM).with_config(
            callbacks=[ToolExecutionHandler()]
        )

    def ask_auto_tool_call(self, question: str) -> str:
        """Asks the model one question and lets the agent run the tools.

        ``create_agent`` builds a loop. It runs each tool call, sends the result back to the
        model, and repeats until the reply has no tool calls.

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
