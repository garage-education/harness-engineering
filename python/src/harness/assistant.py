"""Sends one question to the chat model and returns its text reply."""

import logging
from typing import Final

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

log: Final = logging.getLogger(__name__)


class Assistant:
    """Sends one question to the chat model and returns its text reply."""

    SYSTEM: Final = "You are a careful assistant. Answer in two sentences or fewer."

    def __init__(self, chat: BaseChatModel) -> None:
        self.chat = chat

    def ask_auto_tool_call(self, question: str) -> str:
        """Asks the model one question.

        The system message limits the reply to two sentences.

        Args:
            question: the user's question, in plain text

        Returns:
            the model's final text reply
        """
        log.debug("[auto] LangChain runs every tool call. Question: %s", question)
        answer = self.chat.invoke([SystemMessage(self.SYSTEM), HumanMessage(question)]).text
        log.debug("[auto] Final answer: %s", answer)
        return answer
