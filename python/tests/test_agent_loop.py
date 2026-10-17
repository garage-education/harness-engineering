"""One test for each edge of the AgentLoop graph.

A scripted model replaces LM Studio. Each test lists the replies the model gives, in order,
and checks where the run stops. The tests need no model server and run in milliseconds.
"""

import time
from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.graph import END

from harness.agent_loop import AgentLoop
from harness.guardrails import Guardrails
from harness.log_tools import LogTools
from harness.run_result import RunResult
from harness.run_state import RunState

StopReason = RunResult.StopReason


class ScriptedModel(BaseChatModel):
    """A model that returns scripted replies, in order, and records each prompt it receives."""

    replies: list[AIMessage] = []
    prompts: list[list[BaseMessage]] = []
    tokens_per_call: int = 100

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ScriptedModel:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.prompts.append(list(messages))
        reply = self.replies.pop(0)
        reply.usage_metadata = {"input_tokens": self.tokens_per_call, "output_tokens": 0, "total_tokens": self.tokens_per_call}
        return ChatResult(generations=[ChatGeneration(message=reply)])


def answer(text: str) -> AIMessage:
    return AIMessage(text)


def tool_call(**args: Any) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "count_errors", "args": args, "id": "call-1", "type": "tool_call"}])


@pytest.fixture
def model() -> ScriptedModel:
    return ScriptedModel(replies=[], prompts=[])


@pytest.fixture
def loop(model: ScriptedModel) -> AgentLoop:
    return AgentLoop(model, LogTools(), Guardrails())


def test_check_question_to_end_blocked_question_makes_no_model_call(model: ScriptedModel, loop: AgentLoop) -> None:
    result = loop.run("what is the admin password?")

    assert result.reason == StopReason.BLOCKED
    assert result.steps == 0
    assert model.prompts == []


def test_call_model_to_end_reply_without_tool_calls_is_the_answer(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [answer("Checkout has 412 errors.")]

    result = loop.run("how many errors in checkout?")

    assert result == RunResult("Checkout has 412 errors.", StopReason.FINAL_ANSWER, 1, 100)


def test_run_tools_to_call_model_tool_result_goes_back_to_the_model(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [tool_call(service="checkout", minutes=60), answer("Checkout has 412 errors.")]

    result = loop.run("how many errors in checkout?")

    assert result.reason == StopReason.FINAL_ANSWER
    assert result.steps == 2
    tool_result = model.prompts[1][-1]
    assert isinstance(tool_result, ToolMessage)
    assert tool_result.content == "412"


def test_run_tools_rejected_call_sends_the_rejection_to_the_model(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [tool_call(service="checkout", minutes=4320), answer("I can only look back one day.")]

    loop.run("errors in checkout in the last 3 days?")

    tool_result = model.prompts[1][-1]
    assert isinstance(tool_result, ToolMessage)
    assert str(tool_result.content).startswith("Rejected: minutes must be")


def test_check_limits_to_end_token_budget(model: ScriptedModel, loop: AgentLoop) -> None:
    model.tokens_per_call = AgentLoop.MAX_TOKENS + 1
    model.replies = [tool_call(service="checkout", minutes=60)]

    result = loop.run("how many errors in checkout?")

    assert result.reason == StopReason.TOKEN_BUDGET
    assert result.steps == 1


def test_check_limits_to_end_timeout(loop: AgentLoop) -> None:
    state: RunState = {
        "question": "question",
        "messages": [tool_call(service="checkout", minutes=60)],
        "seen_calls": {},
        "deadline": time.monotonic() - 1,
        "step": 1,
        "tokens": 0,
        "answer": None,
        "reason": None,
    }

    update = loop.check_limits(state)

    assert update["reason"] == StopReason.TIMEOUT
    assert AgentLoop.stop_or(AgentLoop.RUN_TOOLS)(state | update) == END  # type: ignore[arg-type]


def test_check_limits_to_end_loop_detected(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [tool_call(service="checkout", minutes=60) for _ in range(AgentLoop.MAX_REPEATS)]

    result = loop.run("how many errors in checkout?")

    assert result.reason == StopReason.LOOP_DETECTED
    assert result.steps == AgentLoop.MAX_REPEATS


def test_check_limits_to_end_step_limit(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [tool_call(service="checkout", minutes=minutes) for minutes in range(1, AgentLoop.MAX_STEPS + 1)]

    result = loop.run("how many errors in checkout?")

    assert result.reason == StopReason.STEP_LIMIT
    assert result.steps == AgentLoop.MAX_STEPS


def test_graph_lists_every_edge(loop: AgentLoop) -> None:
    edges = [line.strip() for line in loop.mermaid().splitlines() if "->" in line]

    assert edges == [
        "__start__ --> check_question;",
        "call_model -.-> __end__;",
        "call_model -.-> check_limits;",
        "check_limits -.-> __end__;",
        "check_limits -.-> run_tools;",
        "check_question -.-> __end__;",
        "check_question -.-> call_model;",
        "run_tools --> call_model;",
    ]
