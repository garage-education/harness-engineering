package com.garageeducation.harness;

import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;

import com.garageeducation.harness.RunResult.StopReason;

/**
 * The data one run carries through the graph.
 *
 * <p>Each node of {@link AgentLoop} reads this state and changes it. Every value that the
 * Chapter 6 loop kept in local variables lives here, so one object holds the whole run.
 */
class RunState {

    /** The user's question, in plain text. */
    final String question;

    /** The messages so far: the system prompt, the question, then each reply and tool result. */
    final List<Message> messages = new ArrayList<>();

    /** How often the model has requested each tool call, by tool name and arguments. */
    final Map<String, Integer> seenCalls = new HashMap<>();

    /** The time after which the run stops with {@link StopReason#TIMEOUT}. */
    final Instant deadline;

    /** The number of model calls so far. */
    int step;

    /** The tokens used so far, summed over all model calls. */
    int tokens;

    /** The final answer; {@code null} until a node sets it. */
    String answer;

    /** Why the run stopped; {@code null} while the run goes on. */
    StopReason reason;

    /**
     * Starts the state for one run.
     *
     * @param system   the system prompt
     * @param question the user's question
     * @param deadline the time after which the run stops
     */
    RunState(String system, String question, Instant deadline) {
        this.question = question;
        this.deadline = deadline;
        messages.add(new SystemMessage(system));
        messages.add(new UserMessage(question));
    }

    /**
     * Returns the model's latest reply.
     *
     * @return the last message, which {@code callModel} added
     */
    AssistantMessage reply() {
        return (AssistantMessage) messages.getLast();
    }
}
