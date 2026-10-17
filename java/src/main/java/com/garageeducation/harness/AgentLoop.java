package com.garageeducation.harness;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

import org.springframework.ai.chat.client.AdvisorParams;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.ai.chat.messages.ToolResponseMessage;
import org.springframework.ai.chat.messages.ToolResponseMessage.ToolResponse;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.support.ToolCallbacks;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.stereotype.Service;

import com.garageeducation.harness.RunResult.StopReason;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * The agent loop, as a graph of four named nodes.
 *
 * <p>{@code checkQuestion} runs once. Then {@code callModel}, {@code checkLimits}, and {@code runTools}
 * repeat until a node sets a stop reason. Each node does one job and changes the {@link RunState}.
 * Each edge reads the state and picks the next node.
 *
 * <p>{@link ChatClient} runs tools by itself through its {@code ToolCallingAdvisor}.
 * This class turns that advisor off, so the model's tool calls come back to this code.
 *
 * <p>{@link Guardrails} checks the question before the first model call, and each tool call before it runs.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentLoop {

    /** The most model calls one run can make. */
    static final int MAX_STEPS = 5;

    /** The most tokens one run can use, summed over all model calls. */
    static final int MAX_TOKENS = 8_000;

    /** The longest one run can take. The loop checks it after each model call. */
    static final Duration TIMEOUT = Duration.ofSeconds(60);

    /** How often the model can request the same tool call before the run stops. */
    static final int MAX_REPEATS = 3;

    // The node names. Each one appears in the [graph] log lines.
    static final String CHECK_QUESTION = "checkQuestion";
    static final String CALL_MODEL = "callModel";
    static final String CHECK_LIMITS = "checkLimits";
    static final String RUN_TOOLS = "runTools";

    private static final String SYSTEM = "You are a careful assistant. Answer in two sentences or fewer.";

    private final ChatClient chat;
    private final LogTools logTools;
    private final Guardrails guardrails;

    private final Graph<RunState> graph = new Graph<RunState>()
            .addNode(CHECK_QUESTION, this::checkQuestion)
            .addNode(CALL_MODEL, this::callModel)
            .addNode(CHECK_LIMITS, this::checkLimits)
            .addNode(RUN_TOOLS, this::runTools)
            .addEdge(Graph.START, CHECK_QUESTION)
            .addConditionalEdges(CHECK_QUESTION, stopOr(CALL_MODEL), List.of(CALL_MODEL, Graph.END))
            .addConditionalEdges(CALL_MODEL, stopOr(CHECK_LIMITS), List.of(CHECK_LIMITS, Graph.END))
            .addConditionalEdges(CHECK_LIMITS, stopOr(RUN_TOOLS), List.of(RUN_TOOLS, Graph.END))
            .addEdge(RUN_TOOLS, CALL_MODEL);

    /**
     * Runs the graph for one question.
     *
     * @param question the user's question, in plain text
     * @return the answer, the stop reason, the step count, and the tokens used
     */
    public RunResult run(String question) {
        log.debug("[loop] Start. The graph runs the steps. Question: {}", question);
        RunState state = graph.run(new RunState(SYSTEM, question, Instant.now().plus(TIMEOUT)));
        return new RunResult(state.answer, state.reason, state.step, state.tokens);
    }

    /**
     * Draws the graph as Mermaid text.
     *
     * @return the graph in Mermaid flowchart syntax
     */
    public String mermaid() {
        return graph.toMermaid();
    }

    /**
     * Builds an edge that stops the run once a node has set a stop reason.
     *
     * @param next the node to run while no stop reason is set
     * @return the route: {@link Graph#END} when {@link RunState#reason} is set, otherwise {@code next}
     */
    static Function<RunState, String> stopOr(String next) {
        return state -> state.reason != null ? Graph.END : next;
    }

    /**
     * Node: checks the question against {@link Guardrails}. A blocked question stops the run.
     *
     * @param state the run state
     */
    void checkQuestion(RunState state) {
        String blocked = guardrails.checkQuestion(state.question);
        if (blocked != null) {
            log.debug("[guard] {} Stop: BLOCKED, no model call", blocked);
            state.answer = blocked;
            state.reason = StopReason.BLOCKED;
        }
    }

    /**
     * Node: sends the messages to the model and adds its reply. A reply without tool calls is the answer.
     *
     * @param state the run state
     */
    void callModel(RunState state) {
        state.step++;
        log.debug("[loop] Step {}/{}: sending {} messages to the model", state.step, MAX_STEPS, state.messages.size());
        ChatResponse response = chat.prompt()
                .messages(state.messages)
                .tools(logTools)
                .advisors(AdvisorParams.toolCallingAdvisorAutoRegister(false))
                .call()
                .chatResponse();
        AssistantMessage reply = response.getResult().getOutput();
        state.messages.add(reply);
        state.tokens += response.getMetadata().getUsage().getTotalTokens();

        if (!reply.hasToolCalls()) {
            log.debug("[loop] Step {}: no tool calls. Stop: FINAL_ANSWER, {} tokens. Answer: {}", state.step, state.tokens, reply.getText());
            state.answer = reply.getText();
            state.reason = StopReason.FINAL_ANSWER;
            return;
        }
        log.debug("[loop] Step {}: model requested {} tool call(s), {} tokens so far", state.step, reply.getToolCalls().size(), state.tokens);
    }

    /**
     * Node: checks the stop rules before any tool runs. A broken rule stops the run.
     *
     * @param state the run state
     */
    void checkLimits(RunState state) {
        int step = state.step;
        if (state.tokens > MAX_TOKENS) {
            log.debug("[loop] Step {}: {} tokens is over MAX_TOKENS {}. Stop: TOKEN_BUDGET", step, state.tokens, MAX_TOKENS);
            state.reason = StopReason.TOKEN_BUDGET;
            return;
        }
        if (Instant.now().isAfter(state.deadline)) {
            log.debug("[loop] Step {}: past the {} deadline. Stop: TIMEOUT", step, TIMEOUT);
            state.reason = StopReason.TIMEOUT;
            return;
        }
        for (ToolCall call : state.reply().getToolCalls()) {
            int count = state.seenCalls.merge(call.name() + call.arguments(), 1, Integer::sum);
            if (count >= MAX_REPEATS) {
                log.debug("[loop] Step {}: {} {} requested {} times. Stop: LOOP_DETECTED", step, call.name(), call.arguments(), count);
                state.reason = StopReason.LOOP_DETECTED;
                return;
            }
        }
        if (step >= MAX_STEPS) {
            log.debug("[loop] Step {}: used all {} steps without a final answer. Stop: STEP_LIMIT", step, MAX_STEPS);
            state.reason = StopReason.STEP_LIMIT;
        }
    }

    /**
     * Node: checks and runs each tool call, then adds the results to the messages.
     *
     * @param state the run state
     */
    void runTools(RunState state) {
        List<ToolResponse> results = new ArrayList<>();
        for (ToolCall call : state.reply().getToolCalls()) {
            String rejected = guardrails.checkToolCall(call);
            if (rejected != null) {
                log.debug("[guard] Step {}: {} {} not run. {}", state.step, call.name(), call.arguments(), rejected);
                results.add(new ToolResponse(call.id(), call.name(), rejected));
                continue;
            }
            log.debug("[loop] Step {}: your code runs {} {}", state.step, call.name(), call.arguments());
            results.add(new ToolResponse(call.id(), call.name(), runTool(call)));
        }
        state.messages.add(ToolResponseMessage.builder().responses(results).build());
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
