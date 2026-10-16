package com.garageeducation.harness;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.springframework.ai.chat.client.AdvisorParams;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.ToolResponseMessage;
import org.springframework.ai.chat.messages.ToolResponseMessage.ToolResponse;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.support.ToolCallbacks;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.stereotype.Service;

import com.garageeducation.harness.RunResult.StopReason;

/**
 * The agent loop, written by hand.
 *
 * <p>Each step sends the full message list to the model. A reply without tool calls ends the run.
 * Otherwise, the loop runs each tool, adds the results to the messages, and repeats.
 *
 * <p>{@link ChatClient} runs tools by itself through its {@code ToolCallingAdvisor}.
 * This class turns that advisor off, so the model's tool calls come back to this code.
 */
@Service
public class AgentLoop {

    /** The most model calls one run can make. */
    static final int MAX_STEPS = 5;

    /** The most tokens one run can use, summed over all model calls. */
    static final int MAX_TOKENS = 8_000;

    /** The longest one run can take. The loop checks it after each model call. */
    static final Duration TIMEOUT = Duration.ofSeconds(60);

    /** How often the model can request the same tool call before the run stops. */
    static final int MAX_REPEATS = 3;

    private static final String SYSTEM = "You are a careful assistant. Answer in two sentences or fewer.";

    private final ChatClient chat;
    private final LogTools logTools;
    private final Map<String, ToolCallback> tools;

    /**
     * Builds the client and indexes the tools by name.
     *
     * @param builder  the {@link ChatClient.Builder} from the OpenAI starter
     * @param logTools the tools the model can call
     */
    public AgentLoop(ChatClient.Builder builder, LogTools logTools) {
        this.chat = builder.build();
        this.logTools = logTools;
        this.tools = Arrays.stream(ToolCallbacks.from(logTools))
                .collect(Collectors.toMap(tool -> tool.getToolDefinition().name(), Function.identity()));
    }

    /**
     * Runs the loop for one question.
     *
     * @param question the user's question, in plain text
     * @return the answer, the stop reason, the step count, and the tokens used
     */
    public RunResult run(String question) {
        List<Message> messages = new ArrayList<>(List.of(new SystemMessage(SYSTEM), new UserMessage(question)));
        Map<String, Integer> seenCalls = new HashMap<>();
        Instant deadline = Instant.now().plus(TIMEOUT);
        int tokens = 0;

        for (int step = 1; step <= MAX_STEPS; step++) {
            // 1. Send the messages to the model.
            ChatResponse response = chat.prompt()
                    .messages(messages)
                    .tools(logTools)
                    .advisors(AdvisorParams.toolCallingAdvisorAutoRegister(false))
                    .call()
                    .chatResponse();
            AssistantMessage reply = response.getResult().getOutput();
            messages.add(reply);
            tokens += totalTokens(response);

            // 2. A reply without tool calls is the answer.
            if (!reply.hasToolCalls()) {
                return new RunResult(reply.getText(), StopReason.FINAL_ANSWER, step, tokens);
            }

            // Stop rules, checked before any tool runs.
            if (tokens > MAX_TOKENS) {
                return new RunResult(null, StopReason.TOKEN_BUDGET, step, tokens);
            }
            if (Instant.now().isAfter(deadline)) {
                return new RunResult(null, StopReason.TIMEOUT, step, tokens);
            }
            for (ToolCall call : reply.getToolCalls()) {
                if (seenCalls.merge(call.name() + call.arguments(), 1, Integer::sum) >= MAX_REPEATS) {
                    return new RunResult(null, StopReason.LOOP_DETECTED, step, tokens);
                }
            }

            // 3. Run each tool. 4. Add the results to the messages.
            messages.add(runTools(reply.getToolCalls()));
        }
        return new RunResult(null, StopReason.STEP_LIMIT, MAX_STEPS, tokens);
    }

    /**
     * Runs each tool call and collects the results in one message.
     *
     * <p>An unknown tool name returns an error text to the model instead of failing the run.
     *
     * @param calls the tool calls from one model reply
     * @return one {@link ToolResponseMessage} with a response for each call
     */
    private ToolResponseMessage runTools(List<ToolCall> calls) {
        List<ToolResponse> responses = new ArrayList<>();
        for (ToolCall call : calls) {
            ToolCallback tool = tools.get(call.name());
            String result = tool == null ? "Unknown tool: " + call.name() : tool.call(call.arguments());
            responses.add(new ToolResponse(call.id(), call.name(), result));
        }
        return ToolResponseMessage.builder().responses(responses).build();
    }

    /**
     * Reads the token count from the response metadata.
     *
     * @param response one model response
     * @return the total tokens for this call, or 0 when the server does not report usage
     */
    private static int totalTokens(ChatResponse response) {
        Usage usage = response.getMetadata().getUsage();
        return usage.getTotalTokens();
    }
}
