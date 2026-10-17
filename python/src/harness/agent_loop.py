"""The agent loop, written by hand."""

import logging
from typing import Final

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolCall, ToolMessage

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
    """

    MAX_STEPS: Final = 5
    """The most model calls one run can make."""

    SYSTEM: Final = "You are a careful assistant. Answer in two sentences or fewer."

    def __init__(self, chat: BaseChatModel, log_tools: LogTools) -> None:
        self.chat = chat
        self.log_tools = log_tools

    def run(self, question: str) -> RunResult:
        """Runs the loop for one question.

        Args:
            question: the user's question, in plain text

        Returns:
            the answer, the stop reason, the step count, and the tokens used
        """
        messages: list[BaseMessage] = [SystemMessage(self.SYSTEM), HumanMessage(question)]
        model = self.chat.bind_tools(tools_from(self.log_tools))

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

            # 3. Run each tool. 4. Add the results to the messages.
            for call in reply.tool_calls:
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
