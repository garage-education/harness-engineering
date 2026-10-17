package com.garageeducation.harness;

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.stereotype.Component;

import tools.jackson.databind.json.JsonMapper;

/**
 * The checks the agent loop runs before the model or a tool sees any input.
 *
 * <p>Each check is plain Java. The model cannot talk its way past it.
 * <ul>
 *   <li>{@link #checkQuestion} runs once, before the first model call.</li>
 *   <li>{@link #checkToolCall} runs for each tool call, before the tool runs.</li>
 * </ul>
 *
 * <p>Each method returns {@code null} when the input passes, or a rejection text when it fails.
 */
@Component
public class Guardrails {

    /** Words that block a question before any model call. The check ignores case. */
    static final List<String> BLOCKED_WORDS = List.of("password", "credit card");

    /** The only tools this agent may run, by name. */
    static final Set<String> ALLOWED_TOOLS = Set.of("countErrors");

    /** The shortest look-back window {@code countErrors} accepts, in minutes. */
    static final int MIN_MINUTES = 1;

    /** The longest look-back window {@code countErrors} accepts, in minutes: one day. */
    static final int MAX_MINUTES = 1440;

    /**
     * Checks the user's question against {@link #BLOCKED_WORDS}.
     *
     * @param question the user's question, in plain text
     * @return {@code null} when the question passes; otherwise the rejection text
     */
    public String checkQuestion(String question) {
        String text = question.toLowerCase(Locale.ROOT);
        for (String word : BLOCKED_WORDS) {
            if (text.contains(word)) {
                return "Blocked: the question contains \"" + word + "\".";
            }
        }
        return null;
    }

    /**
     * Checks one tool call: the name against {@link #ALLOWED_TOOLS}, then the arguments.
     *
     * <p>The rejection text goes back to the model as the tool result, so the model can fix its call.
     *
     * @param call one tool call from the model's reply
     * @return {@code null} when the call passes; otherwise the rejection text
     */
    public String checkToolCall(ToolCall call) {
        if (!ALLOWED_TOOLS.contains(call.name())) {
            return "Rejected: the tool " + call.name() + " is not allowed for this agent.";
        }
        Map<?, ?> args = JsonMapper.shared().readValue(call.arguments(), Map.class);
        if (!(args.get("service") instanceof String service) || service.isBlank()) {
            return "Rejected: service must be a service name, for example checkout.";
        }
        if (!(args.get("minutes") instanceof Integer minutes) || minutes < MIN_MINUTES || minutes > MAX_MINUTES) {
            return "Rejected: minutes must be a whole number from " + MIN_MINUTES + " to " + MAX_MINUTES
                    + ", got " + args.get("minutes") + ". Call the tool again with a valid value.";
        }
        return null;
    }
}
