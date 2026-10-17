"""The checks the agent loop runs before the model or a tool sees any input."""

from typing import Final

from langchain_core.messages import ToolCall


class Guardrails:
    """The checks the agent loop runs before the model or a tool sees any input.

    Each check is plain Python. The model cannot talk its way past it.

    - ``check_question`` runs once, before the first model call.
    - ``check_tool_call`` runs for each tool call, before the tool runs.

    Each method returns ``None`` when the input passes, or a rejection text when it fails.
    """

    BLOCKED_WORDS: Final = ("password", "credit card")
    """Words that block a question before any model call. The check ignores case."""

    ALLOWED_TOOLS: Final = frozenset({"count_errors"})
    """The only tools this agent may run, by name."""

    MIN_MINUTES: Final = 1
    """The shortest look-back window ``count_errors`` accepts, in minutes."""

    MAX_MINUTES: Final = 1440
    """The longest look-back window ``count_errors`` accepts, in minutes: one day."""

    def check_question(self, question: str) -> str | None:
        """Checks the user's question against ``BLOCKED_WORDS``.

        Args:
            question: the user's question, in plain text

        Returns:
            ``None`` when the question passes; otherwise the rejection text
        """
        text = question.lower()
        for word in self.BLOCKED_WORDS:
            if word in text:
                return f'Blocked: the question contains "{word}".'
        return None

    def check_tool_call(self, call: ToolCall) -> str | None:
        """Checks one tool call: the name against ``ALLOWED_TOOLS``, then the arguments.

        The rejection text goes back to the model as the tool result, so the model can fix its call.

        Args:
            call: one tool call from the model's reply

        Returns:
            ``None`` when the call passes; otherwise the rejection text
        """
        if call["name"] not in self.ALLOWED_TOOLS:
            return f"Rejected: the tool {call['name']} is not allowed for this agent."
        args = call["args"]
        service = args.get("service")
        if not isinstance(service, str) or not service.strip():
            return "Rejected: service must be a service name, for example checkout."
        minutes = args.get("minutes")
        if not isinstance(minutes, int) or not self.MIN_MINUTES <= minutes <= self.MAX_MINUTES:
            return (
                f"Rejected: minutes must be a whole number from {self.MIN_MINUTES} to {self.MAX_MINUTES}, "
                f"got {minutes}. Call the tool again with a valid value."
            )
        return None
