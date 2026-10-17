"""The outcome of one agent run."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class RunResult:
    """The outcome of one agent run.

    Every run returns one ``RunResult``. The ``StopReason`` says why the run ended.

    Attributes:
        answer: the model's final text; ``None`` when the run stopped before a final answer
        reason: the reason the run stopped
        steps: the number of model calls the run made
        tokens: the total tokens the run used, as reported by the model server
    """

    class StopReason(StrEnum):
        """Why a run stopped. Each run stops for exactly one reason."""

        FINAL_ANSWER = "FINAL_ANSWER"
        """The model replied without tool calls. Its text is the answer."""

        STEP_LIMIT = "STEP_LIMIT"
        """The run made ``MAX_STEPS`` model calls without a final answer."""

        TOKEN_BUDGET = "TOKEN_BUDGET"
        """The run used more than ``MAX_TOKENS`` tokens."""

        TIMEOUT = "TIMEOUT"
        """The run took longer than ``TIMEOUT``."""

        LOOP_DETECTED = "LOOP_DETECTED"
        """The model requested the same tool call ``MAX_REPEATS`` times."""

    answer: str | None
    reason: StopReason
    steps: int
    tokens: int
