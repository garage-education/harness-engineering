"""The agent loop, written by hand."""

import json
import logging
import time
from datetime import timedelta
from typing import Final

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolCall, ToolMessage

from harness.guardrails import Guardrails
from harness.log_tools import LogTools
from harness.run_result import RunResult
from harness.tool_support import tools_from

log: Final = logging.getLogger(__name__)

StopReason = RunResult.StopReason


class AgentLoop:
    """The agent loop, written by hand.

    Each step sends the full message list to the model. A reply without tool calls ends the run.
    Otherwise, the loop runs each tool, adds the results to the messages, and repeats.

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

    SYSTEM: Final = "You are a careful assistant. Answer in two sentences or fewer."

    def __init__(self, chat: BaseChatModel, log_tools: LogTools, guardrails: Guardrails) -> None:
        self.chat = chat
        self.log_tools = log_tools
        self.guardrails = guardrails

    def run(self, question: str) -> RunResult:
        """Runs the loop for one question.

        Args:
            question: the user's question, in plain text

        Returns:
            the answer, the stop reason, the step count, and the tokens used
        """
        messages: list[BaseMessage] = [SystemMessage(self.SYSTEM), HumanMessage(question)]
        model = self.chat.bind_tools(tools_from(self.log_tools))

        blocked = self.guardrails.check_question(question)
        if blocked is not None:
            log.debug("[guard] %s Stop: BLOCKED, no model call", blocked)
            return RunResult(blocked, StopReason.BLOCKED, 0, 0)

        seen_calls: dict[str, int] = {}
        deadline = time.monotonic() + self.TIMEOUT.total_seconds()
        tokens = 0
        log.debug("[loop] Start. Your code runs the tools. Question: %s", question)

        for step in range(1, self.MAX_STEPS + 1):
            # 1. Send the messages to the model.
            log.debug("[loop] Step %d/%d: sending %d messages to the model", step, self.MAX_STEPS, len(messages))
            reply: AIMessage = model.invoke(messages)
            messages.append(reply)
            tokens += reply.usage_metadata["total_tokens"] if reply.usage_metadata else 0

            # 2. A reply without tool calls is the answer.
            if not reply.tool_calls:
                log.debug("[loop] Step %d: no tool calls. Stop: FINAL_ANSWER, %d tokens. Answer: %s", step, tokens, reply.text)
                return RunResult(reply.text, StopReason.FINAL_ANSWER, step, tokens)
            log.debug("[loop] Step %d: model requested %d tool call(s), %d tokens so far", step, len(reply.tool_calls), tokens)

            # Stop rules, checked before any tool runs.
            if tokens > self.MAX_TOKENS:
                log.debug("[loop] Step %d: %d tokens is over MAX_TOKENS %d. Stop: TOKEN_BUDGET", step, tokens, self.MAX_TOKENS)
                return RunResult(None, StopReason.TOKEN_BUDGET, step, tokens)
            if time.monotonic() > deadline:
                log.debug("[loop] Step %d: past the %s deadline. Stop: TIMEOUT", step, self.TIMEOUT)
                return RunResult(None, StopReason.TIMEOUT, step, tokens)
            for call in reply.tool_calls:
                key = call["name"] + json.dumps(call["args"], sort_keys=True)
                count = seen_calls.get(key, 0) + 1
                seen_calls[key] = count
                if count >= self.MAX_REPEATS:
                    log.debug("[loop] Step %d: %s %s requested %d times. Stop: LOOP_DETECTED", step, call["name"], call["args"], count)
                    return RunResult(None, StopReason.LOOP_DETECTED, step, tokens)

            # 3. Check and run each tool. 4. Add the results to the messages.
            for call in reply.tool_calls:
                rejected = self.guardrails.check_tool_call(call)
                if rejected is not None:
                    log.debug("[guard] Step %d: %s %s not run. %s", step, call["name"], call["args"], rejected)
                    messages.append(ToolMessage(rejected, tool_call_id=call["id"], name=call["name"]))
                    continue
                log.debug("[loop] Step %d: your code runs %s %s", step, call["name"], call["args"])
                messages.append(ToolMessage(self.run_tool(call), tool_call_id=call["id"], name=call["name"]))
        log.debug("[loop] Used all %d steps without a final answer. Stop: STEP_LIMIT", self.MAX_STEPS)
        return RunResult(None, StopReason.STEP_LIMIT, self.MAX_STEPS, tokens)

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
