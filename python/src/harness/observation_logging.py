"""Logs each prompt, each reply, and each tool run, like Spring AI's observation logs."""

import logging
from typing import Any, Final
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

prompt_log: Final = logging.getLogger("ChatModelPromptContent")
completion_log: Final = logging.getLogger("ChatModelCompletion")
tool_log: Final = logging.getLogger("ToolCalling")


class ChatModelObservationHandler(BaseCallbackHandler):
    """Logs the messages sent to the model and the text it returns.

    Spring AI writes these lines when ``log-prompt`` and ``log-completion`` are on.
    LangChain has no such switch, so this handler writes the same two lines.
    """

    def __init__(self, log_prompt: bool, log_completion: bool) -> None:
        self.log_prompt = log_prompt
        self.log_completion = log_completion

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[BaseMessage]], *, run_id: UUID, **kwargs: Any) -> None:
        """Logs the text of every message in the prompt."""
        if self.log_prompt:
            prompt_log.info("Chat Model Prompt Content:\n%s", [message.text for message in messages[0]])

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        """Logs the reply text. ``[]`` means a tool call with no text."""
        if self.log_completion:
            texts = [generation.text for generation in response.generations[0] if generation.text]
            completion_log.info("Chat Model Completion:\n%s", texts)


class ToolExecutionHandler(BaseCallbackHandler):
    """Logs each tool run that LangChain starts for you.

    Spring AI's ``DefaultToolCallingManager`` writes the same line at DEBUG.
    """

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, *, run_id: UUID, **kwargs: Any) -> None:
        """Logs the name of the tool about to run."""
        tool_log.debug("Executing tool call: %s", serialized.get("name"))
