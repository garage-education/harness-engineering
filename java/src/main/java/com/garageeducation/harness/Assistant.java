package com.garageeducation.harness;

import java.util.List;

import org.springframework.ai.chat.client.AdvisorParams;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.SafeGuardAdvisor;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.stereotype.Service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Sends one question to the chat model, with the tools in {@link LogTools}.
 *
 * <p>The two methods send the same request. They differ in who runs the tool:
 * <ul>
 *   <li>{@link #askAutoToolCall} lets {@link ChatClient} run each tool call and returns the final text.</li>
 *   <li>{@link #askHaltToolCall} stops after the first reply and returns the tool calls, unrun.</li>
 * </ul>
 *
 * <p>{@code @RequiredArgsConstructor} generates a constructor for the {@code final} fields.
 * Spring calls it and passes in the {@link ChatClient} and the {@link LogTools}.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class Assistant {

    private static final String SYSTEM = "You are a careful assistant. Answer in two sentences or fewer.";

    private final ChatClient chat;
    private final LogTools logTools;

    /**
     * Asks the model one question and lets {@link ChatClient} run the tools.
     *
     * <p>{@link ChatClient} registers a {@code ToolCallingAdvisor} by default. The advisor runs each
     * tool call, sends the result back to the model, and repeats until the reply has no tool calls.
     *
     * <p>{@link SafeGuardAdvisor} blocks a question that contains a word from {@link Guardrails#BLOCKED_WORDS}.
     * It returns a fixed text without calling the model.
     *
     * @param question the user's question, in plain text
     * @return the model's final text reply
     */
    public String askAutoToolCall(String question) {
        log.debug("[auto] Spring AI runs every tool call. Question: {}", question);
        String answer = chat.prompt()
                .system(SYSTEM)
                .user(question)
                .tools(logTools)
                .advisors(new SafeGuardAdvisor(Guardrails.BLOCKED_WORDS))
                .call()
                .content();
        log.debug("[auto] Final answer: {}", answer);
        return answer;
    }

    /**
     * Asks the model one question and stops before any tool runs.
     *
     * <p>{@code toolCallingAdvisorAutoRegister(false)} removes the {@code ToolCallingAdvisor}.
     * The model still sees the tools. Its tool calls come back to this code as data.
     *
     * @param question the user's question, in plain text
     * @return the tool calls the model requested; empty when it answered in text
     */
    public List<ToolCall> askHaltToolCall(String question) {
        log.debug("[halt] ToolCallingAdvisor is off. No tool will run. Question: {}", question);
        AssistantMessage reply = chat.prompt()
                .system(SYSTEM)
                .user(question)
                .tools(logTools)
                .advisors(AdvisorParams.toolCallingAdvisorAutoRegister(false))
                .call()
                .chatResponse()
                .getResult()
                .getOutput();
        if (reply.hasToolCalls()) {
            for (ToolCall call : reply.getToolCalls()) {
                log.debug("[halt] Model requested {} {}. Not run.", call.name(), call.arguments());
            }
        } else {
            log.debug("[halt] Model answered in text, with no tool call: {}", reply.getText());
        }
        return reply.getToolCalls();
    }
}
