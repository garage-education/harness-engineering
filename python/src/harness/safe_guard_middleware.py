"""Blocks a model call when the messages contain a sensitive word, like Spring AI's ``SafeGuardAdvisor``."""

from typing import Any, Final

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime


class SafeGuardMiddleware(AgentMiddleware):
    """Blocks a model call when the messages contain a sensitive word.

    It plays the part of Spring AI's ``SafeGuardAdvisor``. LangChain has no built-in middleware
    for a word list. The check ignores case. It does not catch spelling tricks.

    ``before_model`` runs before each model call in the agent loop. On a match, it adds the
    failure text as the AI reply and jumps to the end. The model is never called.
    """

    DEFAULT_FAILURE_RESPONSE: Final = "I'm unable to respond to that due to sensitive content. Could we rephrase or discuss something else?"

    def __init__(self, sensitive_words: tuple[str, ...], failure_response: str = DEFAULT_FAILURE_RESPONSE) -> None:
        super().__init__()
        self.sensitive_words = sensitive_words
        self.failure_response = failure_response

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Checks every message text before the model call.

        Args:
            state: the agent state; ``state["messages"]`` holds the conversation so far
            runtime: the agent runtime; unused

        Returns:
            ``None`` to call the model; otherwise the failure reply and a jump to the end
        """
        text = "".join(message.text for message in state["messages"]).lower()
        if any(word.lower() in text for word in self.sensitive_words):
            return {"messages": [AIMessage(self.failure_response)], "jump_to": "end"}
        return None
