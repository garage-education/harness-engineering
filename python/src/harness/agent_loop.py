"""The agent loop, as a graph of four named nodes."""

import json
import logging
import time
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any, Final, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolCall, ToolMessage
from langgraph.graph import END, START, StateGraph

from harness.guardrails import Guardrails
from harness.log_tools import LogTools
from harness.run_result import RunResult
from harness.run_state import RunState
from harness.tool_support import tools_from

log: Final = logging.getLogger(__name__)

StopReason = RunResult.StopReason


class AgentLoop:
    """The agent loop, as a graph of four named nodes.

    ``check_question`` runs once. Then ``call_model``, ``check_limits``, and ``run_tools`` repeat
    until a node sets a stop reason. Each node does one job and returns the state keys it changes.
    Each edge reads the state and picks the next node. LangGraph's ``StateGraph`` runs the graph.

    ``bind_tools`` only sends the tool definitions. No agent runs the tools, so the model's
    tool calls come back to this code.

    ``Guardrails`` checks the question before the first model call, and each tool call before it runs.
    """

    MAX_STEPS: Final = 5
    """The most model calls one run can make."""

    MAX_TOKENS: Final = 8_000
    """The most tokens one run can use, summed over all model calls."""

    TIMEOUT: Final = timedelta(seconds=60)
    """The longest one run can take. The loop checks it after each model call."""

    MAX_REPEATS: Final = 3
    """How often the model can request the same tool call before the run stops."""

    # The node names. Each one appears in the [graph] log lines.
    CHECK_QUESTION: Final = "check_question"
    CALL_MODEL: Final = "call_model"
    CHECK_LIMITS: Final = "check_limits"
    RUN_TOOLS: Final = "run_tools"

    SYSTEM: Final = "You are a careful assistant. Answer in two sentences or fewer."

    def __init__(self, chat: BaseChatModel, log_tools: LogTools, guardrails: Guardrails) -> None:
        self.chat = chat
        self.log_tools = log_tools
        self.guardrails = guardrails
        self.model = chat.bind_tools(tools_from(log_tools))

        graph = StateGraph(RunState)
        graph.add_node(self.CHECK_QUESTION, self.check_question)
        graph.add_node(self.CALL_MODEL, self.call_model)
        graph.add_node(self.CHECK_LIMITS, self.check_limits)
        graph.add_node(self.RUN_TOOLS, self.run_tools)
        graph.add_edge(START, self.CHECK_QUESTION)
        graph.add_conditional_edges(self.CHECK_QUESTION, self.stop_or(self.CALL_MODEL), [self.CALL_MODEL, END])
        graph.add_conditional_edges(self.CALL_MODEL, self.stop_or(self.CHECK_LIMITS), [self.CHECK_LIMITS, END])
        graph.add_conditional_edges(self.CHECK_LIMITS, self.stop_or(self.RUN_TOOLS), [self.RUN_TOOLS, END])
        graph.add_edge(self.RUN_TOOLS, self.CALL_MODEL)
        self.graph = graph.compile()

    def run(self, question: str) -> RunResult:
        """Runs the graph for one question.

        ``stream_mode="tasks"`` reports each node as it starts, for the ``[graph]`` log line.
        ``"values"`` reports the full state after each step. The last one is the final state.

        Args:
            question: the user's question, in plain text

        Returns:
            the answer, the stop reason, the step count, and the tokens used
        """
        log.debug("[loop] Start. The graph runs the steps. Question: %s", question)
        start: RunState = {
            "question": question,
            "messages": [SystemMessage(self.SYSTEM), HumanMessage(question)],
            "seen_calls": {},
            "deadline": time.monotonic() + self.TIMEOUT.total_seconds(),
            "step": 0,
            "tokens": 0,
            "answer": None,
            "reason": None,
        }
        state: dict[str, Any] = dict(start)
        # With a list of modes, stream yields (mode, chunk) pairs. The cast tells mypy their types.
        events = cast(Iterator[tuple[str, dict[str, Any]]], self.graph.stream(start, stream_mode=["tasks", "values"]))
        for mode, chunk in events:
            if mode == "tasks" and "input" in chunk:
                log.debug("[graph] Node %s", chunk["name"])
            elif mode == "values":
                state = chunk
        return RunResult(state["answer"], state["reason"], state["step"], state["tokens"])

    def mermaid(self) -> str:
        """Draws the graph as Mermaid text.

        Returns:
            the graph in Mermaid flowchart syntax
        """
        return self.graph.get_graph().draw_mermaid()

    @staticmethod
    def stop_or(next_node: str) -> Callable[[RunState], str]:
        """Builds an edge that stops the run once a node has set a stop reason.

        Args:
            next_node: the node to run while no stop reason is set

        Returns:
            the route: ``END`` when ``state["reason"]`` is set, otherwise ``next_node``
        """
        return lambda state: END if state["reason"] is not None else next_node

    def check_question(self, state: RunState) -> dict[str, Any]:
        """Node: checks the question against ``Guardrails``. A blocked question stops the run.

        Args:
            state: the run state

        Returns:
            the changed keys: ``answer`` and ``reason`` when the question is blocked
        """
        blocked = self.guardrails.check_question(state["question"])
        if blocked is not None:
            log.debug("[guard] %s Stop: BLOCKED, no model call", blocked)
            return {"answer": blocked, "reason": StopReason.BLOCKED}
        return {}

    def call_model(self, state: RunState) -> dict[str, Any]:
        """Node: sends the messages to the model and adds its reply. A reply without tool calls is the answer.

        Args:
            state: the run state

        Returns:
            the changed keys: the reply, ``step``, ``tokens``, and, for a final answer, ``answer`` and ``reason``
        """
        step = state["step"] + 1
        log.debug("[loop] Step %d/%d: sending %d messages to the model", step, self.MAX_STEPS, len(state["messages"]))
        reply: AIMessage = self.model.invoke(state["messages"])
        tokens = state["tokens"] + (reply.usage_metadata["total_tokens"] if reply.usage_metadata else 0)
        update: dict[str, Any] = {"messages": [reply], "step": step, "tokens": tokens}

        if not reply.tool_calls:
            log.debug("[loop] Step %d: no tool calls. Stop: FINAL_ANSWER, %d tokens. Answer: %s", step, tokens, reply.text)
            return update | {"answer": reply.text, "reason": StopReason.FINAL_ANSWER}
        log.debug("[loop] Step %d: model requested %d tool call(s), %d tokens so far", step, len(reply.tool_calls), tokens)
        return update

    def check_limits(self, state: RunState) -> dict[str, Any]:
        """Node: checks the stop rules before any tool runs. A broken rule stops the run.

        Args:
            state: the run state

        Returns:
            the changed keys: ``seen_calls``, and ``reason`` when a rule is broken
        """
        step = state["step"]
        if state["tokens"] > self.MAX_TOKENS:
            log.debug("[loop] Step %d: %d tokens is over MAX_TOKENS %d. Stop: TOKEN_BUDGET", step, state["tokens"], self.MAX_TOKENS)
            return {"reason": StopReason.TOKEN_BUDGET}
        if time.monotonic() > state["deadline"]:
            log.debug("[loop] Step %d: past the %s deadline. Stop: TIMEOUT", step, self.TIMEOUT)
            return {"reason": StopReason.TIMEOUT}
        seen_calls = dict(state["seen_calls"])
        for call in self.reply(state).tool_calls:
            key = call["name"] + json.dumps(call["args"], sort_keys=True)
            count = seen_calls[key] = seen_calls.get(key, 0) + 1
            if count >= self.MAX_REPEATS:
                log.debug("[loop] Step %d: %s %s requested %d times. Stop: LOOP_DETECTED", step, call["name"], call["args"], count)
                return {"seen_calls": seen_calls, "reason": StopReason.LOOP_DETECTED}
        if step >= self.MAX_STEPS:
            log.debug("[loop] Step %d: used all %d steps without a final answer. Stop: STEP_LIMIT", step, self.MAX_STEPS)
            return {"seen_calls": seen_calls, "reason": StopReason.STEP_LIMIT}
        return {"seen_calls": seen_calls}

    def run_tools(self, state: RunState) -> dict[str, Any]:
        """Node: checks and runs each tool call, then adds the results to the messages.

        Args:
            state: the run state

        Returns:
            the changed keys: one ``ToolMessage`` per tool call
        """
        results: list[ToolMessage] = []
        for call in self.reply(state).tool_calls:
            rejected = self.guardrails.check_tool_call(call)
            if rejected is not None:
                log.debug("[guard] Step %d: %s %s not run. %s", state["step"], call["name"], call["args"], rejected)
                results.append(ToolMessage(rejected, tool_call_id=call["id"], name=call["name"]))
                continue
            log.debug("[loop] Step %d: your code runs %s %s", state["step"], call["name"], call["args"])
            results.append(ToolMessage(self.run_tool(call), tool_call_id=call["id"], name=call["name"]))
        return {"messages": results}

    @staticmethod
    def reply(state: RunState) -> AIMessage:
        """Returns the model's latest reply.

        Args:
            state: the run state

        Returns:
            the last message, which ``call_model`` added
        """
        reply = state["messages"][-1]
        assert isinstance(reply, AIMessage)
        return reply

    def run_tool(self, call: ToolCall) -> str:
        """Runs one tool call and returns its result as text.

        ``tools_from`` wraps each ``@tool`` method in a LangChain tool. The loop picks the tool
        whose name matches the call. An unknown name returns an error text to the model instead
        of failing the run.

        Args:
            call: one tool call from the model's reply

        Returns:
            the tool's result, or an error text for an unknown tool
        """
        for tool in tools_from(self.log_tools):
            if tool.name == call["name"]:
                return str(tool.invoke(call["args"]))
        log.warning("[loop] Model requested an unknown tool: %s", call["name"])
        return "Unknown tool: " + call["name"]
