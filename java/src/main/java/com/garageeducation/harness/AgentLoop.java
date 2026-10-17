package com.garageeducation.harness;

import java.util.ArrayList;
import java.util.List;

import org.springframework.ai.chat.client.AdvisorParams;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.ToolResponseMessage;
import org.springframework.ai.chat.messages.ToolResponseMessage.ToolResponse;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.support.ToolCallbacks;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.stereotype.Service;

import com.garageeducation.harness.RunResult.StopReason;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * The agent loop, written by hand.
 *
 * <p>Each step sends the full message list to the model. A reply without tool calls ends the run.
 * Otherwise, the loop runs each tool, adds the results to the messages, and repeats.
 *
 * <p>{@link ChatClient} runs tools by itself through its {@code ToolCallingAdvisor}.
 * This class turns that advisor off, so the model's tool calls come back to this code.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentLoop {

    /** The most model calls one run can make. */
    static final int MAX_STEPS = 5;


    private static final String SYSTEM = "You are a careful assistant. Answer in two sentences or fewer.";

    private final ChatClient chat;
    private final LogTools logTools;

    /**
     * Runs the loop for one question.
     *
     * @param question the user's question, in plain text
     * @return the answer, the stop reason, the step count, and the tokens used
     */
    public RunResult run(String question) {
        List<Message> messages = new ArrayList<>();
        messages.add(new SystemMessage(SYSTEM));
        messages.add(new UserMessage(question));

        int tokens = 0;
        log.debug("[loop] Start. Your code runs the tools. Question: {}", question);

        for (int step = 1; step <= MAX_STEPS; step++) {
            // 1. Send the messages to the model.
            log.debug("[loop] Step {}/{}: sending {} messages to the model", step, MAX_STEPS, messages.size());
            ChatResponse response = chat.prompt()
                    .messages(messages)
                    .tools(logTools)
                    .advisors(AdvisorParams.toolCallingAdvisorAutoRegister(false))
                    .call()
                    .chatResponse();
            AssistantMessage reply = response.getResult().getOutput();
            messages.add(reply);
            tokens += response.getMetadata().getUsage().getTotalTokens();

            // 2. A reply without tool calls is the answer.
            if (!reply.hasToolCalls()) {
                log.debug("[loop] Step {}: no tool calls. Stop: FINAL_ANSWER, {} tokens. Answer: {}", step, tokens, reply.getText());
                return new RunResult(reply.getText(), StopReason.FINAL_ANSWER, step, tokens);
            }
            log.debug("[loop] Step {}: model requested {} tool call(s), {} tokens so far", step, reply.getToolCalls().size(), tokens);

            // 3. Run each tool. 4. Add the results to the messages.
            List<ToolResponse> results = new ArrayList<>();
            for (ToolCall call : reply.getToolCalls()) {
                log.debug("[loop] Step {}: your code runs {} {}", step, call.name(), call.arguments());
                results.add(new ToolResponse(call.id(), call.name(), runTool(call)));
            }
            messages.add(ToolResponseMessage.builder().responses(results).build());
        }
        log.debug("[loop] Used all {} steps without a final answer. Stop: STEP_LIMIT", MAX_STEPS);
        return new RunResult(null, StopReason.STEP_LIMIT, MAX_STEPS, tokens);
    }

    /**
     * Runs one tool call and returns its result as text.
     *
     * <p>{@code ToolCallbacks.from} wraps each {@code @Tool} method in a {@link ToolCallback}.
     * The loop picks the callback whose name matches the call. An unknown name returns an
     * error text to the model instead of failing the run.
     *
     * @param call one tool call from the model's reply
     * @return the tool's result, or an error text for an unknown tool
     */
    private String runTool(ToolCall call) {
        for (ToolCallback tool : ToolCallbacks.from(logTools)) {
            if (tool.getToolDefinition().name().equals(call.name())) {
                return tool.call(call.arguments());
            }
        }
        log.warn("[loop] Model requested an unknown tool: {}", call.name());
        return "Unknown tool: " + call.name();
    }
}
