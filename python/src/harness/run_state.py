"""The data one run carries through the graph."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from harness.run_result import RunResult


class RunState(TypedDict):
    """The data one run carries through the graph.

    Each node of ``AgentLoop`` reads this state and returns the keys it changes. LangGraph merges
    them into the state. Every value that the Chapter 6 loop kept in local variables lives here,
    so one object holds the whole run.

    ``add_messages`` is a reducer: a node returns only its new messages, and LangGraph appends them.
    Every other key is replaced by the value a node returns.
    """

    question: str
    """The user's question, in plain text."""

    messages: Annotated[list[AnyMessage], add_messages]
    """The messages so far: the system prompt, the question, then each reply and tool result."""

    seen_calls: dict[str, int]
    """How often the model has requested each tool call, by tool name and arguments."""

    deadline: float
    """The ``time.monotonic()`` value after which the run stops with ``TIMEOUT``."""

    step: int
    """The number of model calls so far."""

    tokens: int
    """The tokens used so far, summed over all model calls."""

    answer: str | None
    """The final answer; ``None`` until a node sets it."""

    reason: RunResult.StopReason | None
    """Why the run stopped; ``None`` while the run goes on."""
