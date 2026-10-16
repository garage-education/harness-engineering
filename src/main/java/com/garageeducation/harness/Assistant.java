package com.garageeducation.harness;

import java.util.List;

import org.springframework.ai.chat.client.AdvisorParams;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.stereotype.Service;

/**
 * Sends one question to the chat model, with the tools in {@link LogTools}.
 *
 * <p>The two methods send the same request. They differ in who runs the tool:
 * <ul>
 *   <li>{@link #askAutoToolCall} lets {@link ChatClient} run each tool call and returns the final text.</li>
 *   <li>{@link #askHaltToolCall} stops after the first reply and returns the tool calls, unrun.</li>
 * </ul>
 */
@Service
public class Assistant {

    private static final String SYSTEM = "You are a careful assistant. Answer in two sentences or fewer.";

    private final ChatClient chat;
    private final LogTools logTools;

    /**
     * Builds the client from the builder that Spring Boot provides.
     *
     * @param builder  the {@link ChatClient.Builder} from the OpenAI starter
     * @param logTools the tools the model can call
     */
    public Assistant(ChatClient.Builder builder, LogTools logTools) {
        this.chat = builder.build();
        this.logTools = logTools;
    }

    /**
     * Asks the model one question and lets {@link ChatClient} run the tools.
     *
     * <p>{@link ChatClient} registers a {@code ToolCallingAdvisor} by default. The advisor runs each
     * tool call, sends the result back to the model, and repeats until the reply has no tool calls.
     *
     * @param question the user's question, in plain text
     * @return the model's final text reply
     */
    public String askAutoToolCall(String question) {
        return chat.prompt()
                .system(SYSTEM)
                .user(question)
                .tools(logTools)
                .call()
                .content();
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
        AssistantMessage reply = chat.prompt()
                .system(SYSTEM)
                .user(question)
                .tools(logTools)
                .advisors(AdvisorParams.toolCallingAdvisorAutoRegister(false))
                .call()
                .chatResponse()
                .getResult()
                .getOutput();
        return reply.getToolCalls();
    }
}
