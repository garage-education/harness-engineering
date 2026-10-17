---
title: "Chapter 8: Graphs"
sidebar_label: "8. Graphs"
description: Turn the agent loop into named nodes and edges, so every move between steps has a unit test.
---

This chapter turns the agent loop into a graph: named steps, joined by named moves, with one unit test for each move.

**Objectives:**

- Draw the Chapter 7 loop as nodes and edges.
- Run the loop as a graph: a small graph runner in Java, and LangGraph's `StateGraph` in Python.
- Keep every value of a run in one state object.
- Test every edge with a scripted model, without LM Studio.

The Chapter 7 loop works, but its flow is hidden in one long method. To learn where a run goes after a model reply, you read a `for` loop with six `return` statements. To test the `STEP_LIMIT` rule, Chapter 6 changed a constant, restarted the app, and called Gemma. A test that needs a running model is slow, and its result changes from run to run.

A graph makes the flow explicit. Each step of work is a **node**. Each move from one node to the next is an **edge**. A **conditional edge** reads the run's data and picks the next node. Once each move is a named edge, you can draw it, log it, and test it on its own.

This chapter changes how the loop is written, not what it does. The same requests give the same results as in Chapter 7, with one exception that Step 4 explains. A graph database, which stores relationships between services, is a different tool. This chapter does not use one.

## Step 1: Draw the loop as a graph

Read `AgentLoop.run` from Chapter 7 and list the jobs it does. There are four:

1. **Check the question.** `Guardrails.checkQuestion` runs once, before the loop.
2. **Call the model.** Send the messages and add the reply. A reply without tool calls is the answer.
3. **Check the limits.** The Chapter 6 rules: the token budget, the timeout, and loop detection.
4. **Run the tools.** Check each call with `Guardrails.checkToolCall`, run it, and add the results.

Each job becomes a node. The `if` and `return` statements between the jobs become edges. Figure 8.1 shows the result.

<figure class="arch">
<script type="application/json">
{
  "title": "The agent loop as a graph of four nodes.",
  "nodes": [
    {"id": "start", "x": 0, "y": 130, "w": 110, "h": 60, "label": "Start", "tone": "muted"},
    {"id": "question", "x": 150, "y": 130, "w": 180, "h": 60, "label": "checkQuestion", "detail": "blocked words", "tone": "platform"},
    {"id": "model", "x": 390, "y": 130, "w": 180, "h": 60, "label": "callModel", "detail": "one model call", "tone": "ai"},
    {"id": "limits", "x": 630, "y": 130, "w": 180, "h": 60, "label": "checkLimits", "detail": "Chapter 6 stop rules", "tone": "platform"},
    {"id": "tools", "x": 630, "y": 280, "w": 180, "h": 60, "label": "runTools", "detail": "check, then run each call", "tone": "platform"},
    {"id": "endBlocked", "x": 150, "y": 280, "w": 180, "h": 60, "label": "End", "detail": "BLOCKED", "tone": "muted"},
    {"id": "endAnswer", "x": 390, "y": 0, "w": 180, "h": 60, "label": "End", "detail": "FINAL_ANSWER", "tone": "muted"},
    {"id": "endLimits", "x": 630, "y": 0, "w": 180, "h": 60, "label": "End", "detail": "a stop rule broke", "tone": "muted"}
  ],
  "edges": [
    {"from": "start", "to": "question"},
    {"from": "question", "to": "model", "label": "passed", "dashed": true},
    {"from": "question", "to": "endBlocked", "label": "blocked", "dashed": true},
    {"from": "model", "to": "limits", "label": "tool calls", "dashed": true},
    {"from": "model", "to": "endAnswer", "label": "no tool calls", "dashed": true},
    {"from": "limits", "to": "endLimits", "label": "broken", "dashed": true},
    {"from": "limits", "to": "tools", "label": "within limits", "dashed": true},
    {"from": "tools", "to": "model", "fromSide": "left", "toSide": "bottom"}
  ]
}
</script>
<figcaption>Figure 8.1. The agent loop as a graph. A solid arrow always goes to the same node. A dashed arrow is one choice of a conditional edge. The loop is the cycle <code>callModel</code>, <code>checkLimits</code>, <code>runTools</code>, and back to <code>callModel</code>. The Python names use snake case: <code>check_question</code>, <code>call_model</code>, <code>check_limits</code>, and <code>run_tools</code>.</figcaption>
</figure>

- **Every run starts at `checkQuestion`.** The edge from Start has no condition.
- **Three edges are conditional.** Each one either goes on to the next node or ends the run.
- **`runTools` always goes back to `callModel`.** The model must read the tool results, so this edge has no condition.
- **Every run ends at one End.** The stop reason says which one.

Table 8.1 shows where each part of the Chapter 7 method goes.

| Chapter 7 `AgentLoop.run` | Chapter 8 graph |
|---|---|
| Local variables: `messages`, `seenCalls`, `deadline`, `step`, `tokens` | Fields of one `RunState` object |
| The question check before the loop | Node `checkQuestion` |
| Steps 1 and 2: call the model, check for tool calls | Node `callModel` |
| The stop rules: tokens, timeout, repeats | Node `checkLimits` |
| Steps 3 and 4: check and run each tool | Node `runTools` |
| The `STEP_LIMIT` return after the `for` loop | Node `checkLimits`, before the tools run |
| The `for` loop and each `return` | Edges. A node sets a stop reason, and the edge after it ends the run. |

<p class="caption">Table 8.1. The Chapter 7 loop, split into a graph. No rule changes. Only its place in the code does.</p>

## Step 2: Write the graph runner

A graph runner needs three parts: a map of named nodes, a map of edges, and a loop that runs one node, follows its edge, and repeats until the edge says End.

::: tabs
::: tab Java
Spring AI has no graph runner. Its guide to agent patterns writes each workflow as plain Java: a `for` loop for a chain of model calls, and a `Map` of routes for a router. Figure 8.2 redraws its routing workflow. (Source: Spring AI reference, <a href="https://docs.spring.io/spring-ai/reference/api/effective-agents.html">Building Effective Agents</a>.)

The runner below is 50 lines of plain Java, plus comments. Its method names copy LangGraph's `StateGraph`, the graph library the Python track uses. Create `Graph.java`:

```java
package com.garageeducation.harness;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import java.util.function.Function;

import lombok.extern.slf4j.Slf4j;

/**
 * A small graph runner: named nodes, and edges that pick the next node.
 *
 * <p>A node is one step of work. It reads the state and changes it. An edge names the node that
 * runs next. A conditional edge reads the state to pick it. A run starts at the edge from
 * {@link #START} and stops when an edge returns {@link #END}.
 *
 * <p>It mirrors the API of LangGraph's {@code StateGraph}, in plain Java. Spring AI has no graph runner.
 *
 * @param <S> the state type that every node reads and changes
 */
@Slf4j
public class Graph<S> {

    /** The name of the start of the graph. An edge from it picks the first node. */
    public static final String START = "__start__";

    /** The name of the end of the graph. An edge to it stops the run. */
    public static final String END = "__end__";

    private final Map<String, Consumer<S>> nodes = new LinkedHashMap<>();
    private final Map<String, Edge<S>> edges = new LinkedHashMap<>();

    /**
     * One edge out of a node.
     *
     * @param route       picks the next node from the state
     * @param targets     every node the route can return; used to draw the graph
     * @param conditional {@code true} when the route reads the state
     */
    private record Edge<S>(Function<S, String> route, List<String> targets, boolean conditional) {
    }

    /**
     * Adds a node.
     *
     * @param name the node name, unique in this graph
     * @param node the work the node does; it changes the state in place
     * @return this graph
     */
    public Graph<S> addNode(String name, Consumer<S> node) {
        nodes.put(name, node);
        return this;
    }

    /**
     * Adds an edge that always goes from one node to another.
     *
     * @param from the node name, or {@link #START}
     * @param to   the next node name, or {@link #END}
     * @return this graph
     */
    public Graph<S> addEdge(String from, String to) {
        edges.put(from, new Edge<>(state -> to, List.of(to), false));
        return this;
    }

    /**
     * Adds an edge that reads the state to pick the next node.
     *
     * @param from    the node name
     * @param route   returns the next node name, or {@link #END}
     * @param targets every name {@code route} can return
     * @return this graph
     */
    public Graph<S> addConditionalEdges(String from, Function<S, String> route, List<String> targets) {
        edges.put(from, new Edge<>(route, targets, true));
        return this;
    }

    /**
     * Runs the graph from {@link #START} until an edge returns {@link #END}.
     *
     * @param state the state at the start of the run; the nodes change it in place
     * @return the same state, at the end of the run
     * @throws IllegalStateException if an edge returns a name that is not a node
     */
    public S run(S state) {
        String node = edges.get(START).route().apply(state);
        while (!END.equals(node)) {
            Consumer<S> work = nodes.get(node);
            if (work == null) {
                throw new IllegalStateException("No node named " + node);
            }
            log.debug("[graph] Node {}", node);
            work.accept(state);
            node = edges.get(node).route().apply(state);
        }
        return state;
    }

    /**
     * Draws the graph as Mermaid text. Paste it into a Mermaid editor to see the picture.
     *
     * <p>A solid arrow is a fixed edge. A dotted arrow is one choice of a conditional edge.
     *
     * @return the graph in Mermaid flowchart syntax
     */
    public String toMermaid() {
        StringBuilder text = new StringBuilder("graph TD;\n");
        edges.forEach((from, edge) -> {
            for (String to : edge.targets()) {
                text.append('\t').append(from).append(edge.conditional() ? " -.-> " : " --> ").append(to).append(";\n");
            }
        });
        return text.toString();
    }
}
```

- **`Graph<S>` works with any state type.** `S` is the object every node reads and changes. Step 3 writes it.
- **A node is a `Consumer<S>`.** It takes the state and changes it in place. It returns nothing.
- **An edge is a `Function<S, String>`.** It reads the state and returns the name of the next node. `addEdge` builds a function that always returns the same name.
- **`addConditionalEdges` also takes `targets`.** The route could return any string, so the graph cannot read the targets from it. The list is used only to draw the graph.
- **`run` is the whole engine.** It follows the edge from `START`, then runs nodes and follows edges until one returns `END`. It logs each node with the `[graph]` tag.
- **A typo in a route fails fast.** An edge that returns an unknown name throws `IllegalStateException`. It does not loop forever or skip a step.
- **`toMermaid` draws the graph as text.** Mermaid is a text format for diagrams. Paste the text into a Mermaid editor, such as mermaid.live, to see the picture.
:::
::: tab Python
LangGraph is the graph library behind LangChain's `create_agent`. Chapter 4 used it without naming it. This chapter uses its `StateGraph` class directly, so there is no runner to write. Add it to `pyproject.toml` as a direct dependency:

```toml
dependencies = [
    "fastapi==0.142.2",
    "langchain==1.4.3",
    "langchain-openai==1.6.7",
    "langgraph==1.2.12",
    "pyyaml==6.0.3",
    "uvicorn==0.54.0",
]
```

- **`langgraph==1.2.12` is already installed.** `langchain` depends on it. Code that imports a package should still list it, so an update to `langchain` cannot change it without notice.
- **`StateGraph` builds the graph.** `add_node`, `add_edge`, and `add_conditional_edges` add the parts. `compile()` checks the graph and returns a runnable object.
- **`START` and `END` are the start and the end.** Their values are `"__start__"` and `"__end__"`.
- **LangGraph caps each run at 10,007 steps.** Each node that runs counts as one step. The Chapter 6 stop rules end the run long before that.
- **LangGraph does more than this chapter needs.** It can stream each step, save the state after each node, and pause a run for a person. Chapters 9 and 23 come back to pausing and saving a run.

Spring AI has no graph runner. The Java track writes a 50-line one with the same method names. Spring AI's guide to agent patterns writes each workflow as plain Java. Figure 8.2 redraws its routing workflow. (Source: Spring AI reference, <a href="https://docs.spring.io/spring-ai/reference/api/effective-agents.html">Building Effective Agents</a>.)
:::
:::

<figure class="arch">
<script type="application/json">
{
  "title": "Spring AI's routing workflow, redrawn as a graph.",
  "nodes": [
    {"id": "in", "x": 0, "y": 110, "w": 150, "h": 60, "label": "Input", "detail": "a support request", "tone": "muted"},
    {"id": "router", "x": 200, "y": 110, "w": 180, "h": 60, "label": "Router", "detail": "a model call picks a route", "tone": "ai"},
    {"id": "billing", "x": 450, "y": 0, "w": 180, "h": 60, "label": "billing", "detail": "model call with its prompt", "tone": "ai"},
    {"id": "technical", "x": 450, "y": 110, "w": 180, "h": 60, "label": "technical", "detail": "model call with its prompt", "tone": "ai"},
    {"id": "general", "x": 450, "y": 220, "w": 180, "h": 60, "label": "general", "detail": "model call with its prompt", "tone": "ai"},
    {"id": "out", "x": 700, "y": 110, "w": 110, "h": 60, "label": "Output", "tone": "muted"}
  ],
  "edges": [
    {"from": "in", "to": "router"},
    {"from": "router", "to": "billing", "dashed": true},
    {"from": "router", "to": "technical", "dashed": true},
    {"from": "router", "to": "general", "dashed": true},
    {"from": "billing", "to": "out"},
    {"from": "technical", "to": "out"},
    {"from": "general", "to": "out"}
  ]
}
</script>
<figcaption>Figure 8.2. The routing workflow from Spring AI's Building Effective Agents page, redrawn with its three example routes. The router is a conditional edge whose choice comes from a model call. (Source: Spring AI reference, Building Effective Agents. The page credits Anthropic's article of the same name.)</figcaption>
</figure>

The routing workflow is a graph with one conditional edge. The difference from Figure 8.1 is who picks the route:

- **In the routing workflow, a model picks the route.** A model call reads the request and names `billing`, `technical`, or `general`.
- **In `AgentLoop`, code picks every route.** The model decides only whether to request tools. A node turns that reply into data, and the edge reads the data.
- **Both can be tested the same way.** Replace the model with a scripted one, and check which node runs next. Step 6 does this.

## Step 3: Put the run in one state

In Chapter 7, the data of one run lived in local variables of `run`. A node is a separate method, so it cannot see another method's local variables. Move them into one object that every node receives.

::: tabs
::: tab Java
Create `RunState.java`:

```java
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
```

- **The fields are the local variables from Chapter 7.** `messages`, `seenCalls`, `deadline`, `step`, and `tokens` keep their names.
- **`answer` and `reason` are new.** In Chapter 7, `run` returned them at once. In a graph, a node stores them, and the edge after the node reads `reason` to end the run.
- **The fields are package-private and not `final` where nodes change them.** Only `AgentLoop` and its test, in the same package, use this class. Getters and setters would add code without adding safety.
- **`reply()` returns the last message.** `callModel` adds the model's reply last. `checkLimits` and `runTools` read its tool calls.
:::
::: tab Python
Create `run_state.py`:

```python
"""The data one run carries through the graph."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from harness.run_result import RunResult


class RunState(TypedDict):
    """The data one run carries through the graph.

    Each node of ``AgentLoop`` reads this state and returns the keys it changes. LangGraph merges
    them into the state. Every value that the Chapter 6 loop kept in local variables lives here,
    so one object holds the whole run.

    ``add_messages`` is a reducer: a node returns only its new messages, and LangGraph appends them.
    Every other key is replaced by the value a node returns.
    """

    question: str
    """The user's question, in plain text."""

    messages: Annotated[list[AnyMessage], add_messages]
    """The messages so far: the system prompt, the question, then each reply and tool result."""

    seen_calls: dict[str, int]
    """How often the model has requested each tool call, by tool name and arguments."""

    deadline: float
    """The ``time.monotonic()`` value after which the run stops with ``TIMEOUT``."""

    step: int
    """The number of model calls so far."""

    tokens: int
    """The tokens used so far, summed over all model calls."""

    answer: str | None
    """The final answer; ``None`` until a node sets it."""

    reason: RunResult.StopReason | None
    """Why the run stopped; ``None`` while the run goes on."""
```

- **`RunState` is a `TypedDict`.** LangGraph reads its keys to learn the shape of the state. A `TypedDict` is a plain `dict` at run time, with key types that mypy checks.
- **The keys are the local variables from Chapter 7.** `messages`, `seen_calls`, `deadline`, `step`, and `tokens` keep their names.
- **`answer` and `reason` are new.** In Chapter 7, `run` returned them at once. In a graph, a node stores them, and the edge after the node reads `reason` to end the run.
- **A node returns only the keys it changes.** LangGraph merges them into the state. A node never changes the state it receives.
- **`add_messages` appends instead of replacing.** `Annotated[..., add_messages]` attaches a reducer to the key. A reducer is a function that merges a node's value into the current one. `call_model` returns one new message, and LangGraph adds it to the list.
:::
:::

## Step 4: Turn each step into a node

Rewrite `AgentLoop` as four node methods and one graph. Each node holds the code of its job from Chapter 7, almost line for line.

::: tabs
::: tab Java
```java
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
```

- **The `graph` field builds the graph once.** It runs when Spring creates the bean. `this::checkQuestion` passes a node method as a `Consumer<RunState>`.
- **`run` is now three lines.** It creates the state, runs the graph, and turns the final state into a `RunResult`. The flow lives in the graph, not in `run`.
- **`stopOr` builds every conditional edge.** "Stop if a node set a reason, otherwise go to `next`." The three conditional edges differ only in `next`.
- **Each node sets `reason` instead of returning.** For example, `checkQuestion` sets `BLOCKED`, and the edge after it ends the run.
- **The node methods are package-private.** The test in Step 6 calls `checkLimits` directly to test the timeout.
- **`mermaid` returns the graph as Mermaid text.** Step 5 adds an endpoint for it.
:::
::: tab Python
```python
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
```

- **`__init__` builds the graph once.** `graph.compile()` checks that every edge points to a known node, then returns the runnable graph.
- **`run` streams the graph.** `stream_mode=["tasks", "values"]` yields two kinds of events. A `tasks` event with an `input` key means a node is starting, so `run` logs it with the `[graph]` tag. A `values` event holds the full state after a step. The last one is the final state.
- **`cast` is only for mypy.** `stream` returns a different type for each stream mode, and mypy cannot tell which one from a list. `cast` tells mypy the type. It does nothing at run time.
- **`stop_or` builds every conditional edge.** "Stop if a node set a reason, otherwise go to `next_node`." The three conditional edges differ only in `next_node`.
- **Each node returns a `dict` of changed keys.** For example, `check_question` returns `{"answer": ..., "reason": BLOCKED}` for a blocked question, and `{}` for a good one.
- **`check_limits` copies `seen_calls` before changing it.** The state belongs to LangGraph. A node returns a new value instead of changing the old one.
- **`mermaid` asks LangGraph to draw the graph.** `get_graph().draw_mermaid()` is built into LangGraph. Step 5 adds an endpoint for it.
:::
:::

Two log lines move, and one rule changes:

- **`[loop] Start` comes first.** It now runs before the question check, so a blocked question logs it too.
- **Each node logs a `[graph]` line as it starts.** Chapter 2, Table 2.1 lists the tag.
- **`STEP_LIMIT` is checked before the tools run.** In Chapter 7, the last step ran its tools, and then the loop ended. No model call ever read those results. Now `checkLimits` stops the run on the last step, before `runTools`. The result is the same: `STEP_LIMIT`, with `MAX_STEPS` steps. The wasted tool calls are gone.

Drawing the graph exposed that wasted work. In Chapter 7, the step check sat after the loop, far from the other stop rules. In the graph, every stop rule sits in one node, so the gap is easy to see.

## Step 5: Run the graph

Add one endpoint that returns the graph as text.

::: tabs
::: tab Java
Add this method to `TestController`:

```java
    /**
     * Draws the agent loop's graph.
     *
     * @return the graph as Mermaid text, one edge per line
     */
    @GetMapping("/graph")
    public String graph() {
        return agentLoop.mermaid();
    }
```
:::
::: tab Python
Add this route to the `TestController` constructor, and the method below it:

```python
        self.router.add_api_route("/graph", self.graph, response_class=PlainTextResponse)
```

```python
    def graph(self) -> str:
        """Draws the agent loop's graph.

        Returns:
            the graph as Mermaid text, one edge per line
        """
        return self.agent_loop.mermaid()
```
:::
:::

Restart the app and ask for the graph:

```bash
curl http://localhost:8080/graph
```

::: tabs
::: tab Java
```text
graph TD;
	__start__ --> checkQuestion;
	checkQuestion -.-> callModel;
	checkQuestion -.-> __end__;
	callModel -.-> checkLimits;
	callModel -.-> __end__;
	checkLimits -.-> runTools;
	checkLimits -.-> __end__;
	runTools --> callModel;
```

- **Each line is one edge.** `-->` is a fixed edge. `-.->` is one choice of a conditional edge.
- **The 8 lines match Figure 8.1.** Paste them into mermaid.live to draw the same graph.
:::
::: tab Python
```text
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	check_question(check_question)
	call_model(call_model)
	check_limits(check_limits)
	run_tools(run_tools)
	__end__([<p>__end__</p>]):::last
	__start__ --> check_question;
	call_model -.-> __end__;
	call_model -.-> check_limits;
	check_limits -.-> __end__;
	check_limits -.-> run_tools;
	check_question -.-> __end__;
	check_question -.-> call_model;
	run_tools --> call_model;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

- **LangGraph adds layout and colors.** The lines from `__start__ --> check_question;` to `run_tools --> call_model;` are the edges. The rest sets shapes and colors.
- **`-->` is a fixed edge. `-.->` is one choice of a conditional edge.** The 8 edges match Figure 8.1.
- **LangGraph sorts the conditional edges by name.** The Java runner keeps the order you added them in.
:::
:::

Now send the Chapter 5 question again:

```bash
curl -G http://localhost:8080/run --data-urlencode "input=how many error events in checkout service?"
```

::: tabs
::: tab Java
```text
01:49:49.107 DEBUG DispatcherServlet                        GET "/run?input=how+many+error+events+in+checkout+service%3F", parameters={masked}
01:49:49.112 DEBUG AgentLoop                                [loop] Start. The graph runs the steps. Question: how many error events in checkout service?
01:49:49.113 DEBUG Graph                                    [graph] Node checkQuestion
01:49:49.113 DEBUG Graph                                    [graph] Node callModel
01:49:49.113 DEBUG AgentLoop                                [loop] Step 1/5: sending 2 messages to the model
01:49:53.640 INFO  ChatModelCompletionObservationHandler    Chat Model Completion:
[]
01:49:53.640 INFO  ChatModelPromptContentObservationHandler Chat Model Prompt Content:
["You are a careful assistant. Answer in two sentences or fewer.", "how many error events in checkout service?"]
01:49:53.641 DEBUG AgentLoop                                [loop] Step 1: model requested 1 tool call(s), 543 tokens so far
01:49:53.641 DEBUG Graph                                    [graph] Node checkLimits
01:49:53.641 DEBUG Graph                                    [graph] Node runTools
01:49:53.643 DEBUG AgentLoop                                [loop] Step 1: your code runs countErrors {"minutes":10,"service":"checkout"}
01:49:53.647 DEBUG LogTools                                 [tool] countErrors(service=checkout, minutes=10) returned 412
01:49:53.648 DEBUG Graph                                    [graph] Node callModel
01:49:53.648 DEBUG AgentLoop                                [loop] Step 2/5: sending 4 messages to the model
01:49:53.991 INFO  ChatModelCompletionObservationHandler    Chat Model Completion:
["There were 412 error events in the checkout service in the last 10 minutes."]
01:49:53.991 INFO  ChatModelPromptContentObservationHandler Chat Model Prompt Content:
["You are a careful assistant. Answer in two sentences or fewer.", "how many error events in checkout service?", "", ""]
01:49:53.992 DEBUG AgentLoop                                [loop] Step 2: no tool calls. Stop: FINAL_ANSWER, 741 tokens. Answer: There were 412 error events in the checkout service in the last 10 minutes.
01:49:54.001 DEBUG DispatcherServlet                        Completed 200 OK
```

- **The `[graph]` lines trace the path through Figure 8.1.** `checkQuestion`, `callModel`, `checkLimits`, `runTools`, then `callModel` again.
- **The `[loop]` and `[tool]` lines are the same as in Chapter 7.** The nodes hold the same code.
- **The logger name shows who writes each line.** `Graph` writes the `[graph]` lines. `AgentLoop` writes the lines from the nodes.
- **The reply is the same shape as before.** `{"answer":"There were 412 error events in the checkout service in the last 10 minutes.","reason":"FINAL_ANSWER","steps":2,"tokens":741}`. Gemma chose a 10-minute window on its own, since the question gives none.
:::
::: tab Python
```text
01:51:19.542 DEBUG harness.agent_loop                       [loop] Start. The graph runs the steps. Question: how many error events in checkout service?
01:51:19.544 DEBUG harness.agent_loop                       [graph] Node check_question
01:51:19.544 DEBUG harness.agent_loop                       [graph] Node call_model
01:51:19.544 DEBUG harness.agent_loop                       [loop] Step 1/5: sending 2 messages to the model
01:51:19.544 INFO  ChatModelPromptContent                   Chat Model Prompt Content:
['You are a careful assistant. Answer in two sentences or fewer.', 'how many error events in checkout service?']
01:51:24.379 INFO  httpx2                                   HTTP Request: POST http://localhost:1234/v1/chat/completions "HTTP/1.1 200 OK"
01:51:24.384 INFO  ChatModelCompletion                      Chat Model Completion:
[]
01:51:24.384 DEBUG harness.agent_loop                       [loop] Step 1: model requested 1 tool call(s), 399 tokens so far
01:51:24.385 DEBUG harness.agent_loop                       [graph] Node check_limits
01:51:24.385 DEBUG harness.agent_loop                       [graph] Node run_tools
01:51:24.385 DEBUG harness.agent_loop                       [loop] Step 1: your code runs count_errors {'minutes': 10, 'service': 'checkout'}
01:51:24.387 DEBUG harness.log_tools                        [tool] count_errors(service=checkout, minutes=10) returned 412
01:51:24.387 DEBUG harness.agent_loop                       [graph] Node call_model
01:51:24.387 DEBUG harness.agent_loop                       [loop] Step 2/5: sending 4 messages to the model
01:51:24.387 INFO  ChatModelPromptContent                   Chat Model Prompt Content:
['You are a careful assistant. Answer in two sentences or fewer.', 'how many error events in checkout service?', '', '412']
01:51:24.737 INFO  httpx2                                   HTTP Request: POST http://localhost:1234/v1/chat/completions "HTTP/1.1 200 OK"
01:51:24.737 INFO  ChatModelCompletion                      Chat Model Completion:
['There were 412 error events in the checkout service in the last 10 minutes.']
01:51:24.737 DEBUG harness.agent_loop                       [loop] Step 2: no tool calls. Stop: FINAL_ANSWER, 600 tokens. Answer: There were 412 error events in the checkout service in the last 10 minutes.
01:51:24.738 INFO  uvicorn.access                           127.0.0.1:62693 - "GET /run?input=how%20many%20error%20events%20in%20checkout%20service%3F HTTP/1.1" 200
```

- **The `[graph]` lines trace the path through Figure 8.1.** `check_question`, `call_model`, `check_limits`, `run_tools`, then `call_model` again.
- **The `[loop]` and `[tool]` lines are the same as in Chapter 7.** The nodes hold the same code.
- **`run` writes the `[graph]` lines.** They come from the `tasks` events of `stream`, so the logger is `harness.agent_loop`.
- **The reply is the same shape as before.** `{"answer":"There were 412 error events in the checkout service in the last 10 minutes.","reason":"FINAL_ANSWER","steps":2,"tokens":600}`. Gemma chose a 10-minute window on its own, since the question gives none.
:::
:::

All requests from Chapters 5 to 7 in `requests/harness.http` still work. The guardrail requests give the same results: a blocked question stops after the `checkQuestion` node, and a rejected tool call goes back to the model.

To see the new place of the step rule, set `MAX_STEPS` to 1, restart, and send a question that needs a tool:

```bash
curl -G http://localhost:8080/run --data-urlencode "input=how many error events in the checkout service in the last 15 minutes?"
```

::: tabs
::: tab Java
```text
01:50:36.578 DEBUG DispatcherServlet                        GET "/run?input=how+many+error+events+in+the+checkout+service+in+the+last+15+minutes%3F", parameters={masked}
01:50:36.579 DEBUG AgentLoop                                [loop] Start. The graph runs the steps. Question: how many error events in the checkout service in the last 15 minutes?
01:50:36.579 DEBUG Graph                                    [graph] Node checkQuestion
01:50:36.580 DEBUG Graph                                    [graph] Node callModel
01:50:36.580 DEBUG AgentLoop                                [loop] Step 1/1: sending 2 messages to the model
01:50:37.907 INFO  ChatModelCompletionObservationHandler    Chat Model Completion:
[]
01:50:37.907 INFO  ChatModelPromptContentObservationHandler Chat Model Prompt Content:
["You are a careful assistant. Answer in two sentences or fewer.", "how many error events in the checkout service in the last 15 minutes?"]
01:50:37.908 DEBUG AgentLoop                                [loop] Step 1: model requested 1 tool call(s), 267 tokens so far
01:50:37.908 DEBUG Graph                                    [graph] Node checkLimits
01:50:37.908 DEBUG AgentLoop                                [loop] Step 1: used all 1 steps without a final answer. Stop: STEP_LIMIT
01:50:37.910 DEBUG DispatcherServlet                        Completed 200 OK
```

- **The run stops in `checkLimits`.** There is no `[graph] Node runTools` line and no `[tool]` line. In Chapter 7, this run ran the tool first.
- **The reply is unchanged.** `{"answer":null,"reason":"STEP_LIMIT","steps":1,"tokens":267}`.
- **Set `MAX_STEPS` back to 5** before you go on.
:::
::: tab Python
```text
01:51:45.234 DEBUG harness.agent_loop                       [loop] Start. The graph runs the steps. Question: how many error events in the checkout service in the last 15 minutes?
01:51:45.236 DEBUG harness.agent_loop                       [graph] Node check_question
01:51:45.237 DEBUG harness.agent_loop                       [graph] Node call_model
01:51:45.237 DEBUG harness.agent_loop                       [loop] Step 1/1: sending 2 messages to the model
01:51:45.238 INFO  ChatModelPromptContent                   Chat Model Prompt Content:
['You are a careful assistant. Answer in two sentences or fewer.', 'how many error events in the checkout service in the last 15 minutes?']
01:51:48.765 INFO  httpx2                                   HTTP Request: POST http://localhost:1234/v1/chat/completions "HTTP/1.1 200 OK"
01:51:48.770 INFO  ChatModelCompletion                      Chat Model Completion:
[]
01:51:48.770 DEBUG harness.agent_loop                       [loop] Step 1: model requested 1 tool call(s), 277 tokens so far
01:51:48.771 DEBUG harness.agent_loop                       [graph] Node check_limits
01:51:48.771 DEBUG harness.agent_loop                       [loop] Step 1: used all 1 steps without a final answer. Stop: STEP_LIMIT
01:51:48.772 INFO  uvicorn.access                           127.0.0.1:49443 - "GET /run?input=how%20many%20error%20events%20in%20the%20checkout%20service%20in%20the%20last%2015%20minutes%3F HTTP/1.1" 200
```

- **The run stops in `check_limits`.** There is no `[graph] Node run_tools` line and no `[tool]` line. In Chapter 7, this run ran the tool first.
- **The reply is unchanged.** `{"answer":null,"reason":"STEP_LIMIT","steps":1,"tokens":277}`.
- **Set `MAX_STEPS` back to 5** before you go on.
:::
:::

## Step 6: Test every edge

A test of an edge checks that a run takes that edge under its condition. The model is the only part that needs LM Studio, so the tests replace it with a scripted model. A scripted model returns replies from a list, in order, and records each prompt it receives. Each test lists the replies and checks where the run stops.

::: tabs
::: tab Java
Create `src/test/java/com/garageeducation/harness/AgentLoopTest.java`:

```java
package com.garageeducation.harness;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.ai.chat.messages.ToolResponseMessage;
import org.springframework.ai.chat.metadata.ChatResponseMetadata;
import org.springframework.ai.chat.metadata.DefaultUsage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.chat.prompt.Prompt;

import com.garageeducation.harness.RunResult.StopReason;

/**
 * One test for each edge of the {@link AgentLoop} graph.
 *
 * <p>A scripted model replaces LM Studio. Each test lists the replies the model gives, in order,
 * and checks where the run stops. The tests need no model server and run in milliseconds.
 */
class AgentLoopTest {

    /** A model that returns scripted replies, in order, and records each prompt it receives. */
    static class ScriptedModel implements ChatModel {

        final Deque<AssistantMessage> replies = new ArrayDeque<>();
        final List<Prompt> prompts = new ArrayList<>();
        int tokensPerCall = 100;

        ScriptedModel reply(AssistantMessage message) {
            replies.add(message);
            return this;
        }

        @Override
        public ChatResponse call(Prompt prompt) {
            prompts.add(prompt);
            ChatResponseMetadata metadata = ChatResponseMetadata.builder()
                    .usage(new DefaultUsage(tokensPerCall, 0, tokensPerCall))
                    .build();
            return new ChatResponse(List.of(new Generation(replies.removeFirst())), metadata);
        }
    }

    static AssistantMessage answer(String text) {
        return new AssistantMessage(text);
    }

    static AssistantMessage toolCall(String arguments) {
        return AssistantMessage.builder()
                .toolCalls(List.of(new ToolCall("call-1", "function", "countErrors", arguments)))
                .build();
    }

    final ScriptedModel model = new ScriptedModel();
    final AgentLoop loop = new AgentLoop(ChatClient.create(model), new LogTools(), new Guardrails());

    @Test
    void checkQuestionToEnd_blockedQuestionMakesNoModelCall() {
        RunResult result = loop.run("what is the admin password?");

        assertThat(result.reason()).isEqualTo(StopReason.BLOCKED);
        assertThat(result.steps()).isZero();
        assertThat(model.prompts).isEmpty();
    }

    @Test
    void callModelToEnd_replyWithoutToolCallsIsTheAnswer() {
        model.reply(answer("Checkout has 412 errors."));

        RunResult result = loop.run("how many errors in checkout?");

        assertThat(result).isEqualTo(new RunResult("Checkout has 412 errors.", StopReason.FINAL_ANSWER, 1, 100));
    }

    @Test
    void runToolsToCallModel_toolResultGoesBackToTheModel() {
        model.reply(toolCall("{\"service\":\"checkout\",\"minutes\":60}"))
             .reply(answer("Checkout has 412 errors."));

        RunResult result = loop.run("how many errors in checkout?");

        assertThat(result.reason()).isEqualTo(StopReason.FINAL_ANSWER);
        assertThat(result.steps()).isEqualTo(2);
        ToolResponseMessage toolResult = (ToolResponseMessage) model.prompts.get(1).getInstructions().getLast();
        assertThat(toolResult.getResponses().getFirst().responseData()).isEqualTo("412");
    }

    @Test
    void runTools_rejectedCallSendsTheRejectionToTheModel() {
        model.reply(toolCall("{\"service\":\"checkout\",\"minutes\":4320}"))
             .reply(answer("I can only look back one day."));

        loop.run("errors in checkout in the last 3 days?");

        ToolResponseMessage toolResult = (ToolResponseMessage) model.prompts.get(1).getInstructions().getLast();
        assertThat(toolResult.getResponses().getFirst().responseData()).startsWith("Rejected: minutes must be");
    }

    @Test
    void checkLimitsToEnd_tokenBudget() {
        model.tokensPerCall = AgentLoop.MAX_TOKENS + 1;
        model.reply(toolCall("{\"service\":\"checkout\",\"minutes\":60}"));

        RunResult result = loop.run("how many errors in checkout?");

        assertThat(result.reason()).isEqualTo(StopReason.TOKEN_BUDGET);
        assertThat(result.steps()).isEqualTo(1);
    }

    @Test
    void checkLimitsToEnd_timeout() {
        RunState state = new RunState("system", "question", Instant.now().minusSeconds(1));
        state.messages.add(toolCall("{\"service\":\"checkout\",\"minutes\":60}"));

        loop.checkLimits(state);

        assertThat(state.reason).isEqualTo(StopReason.TIMEOUT);
        assertThat(AgentLoop.stopOr(AgentLoop.RUN_TOOLS).apply(state)).isEqualTo(Graph.END);
    }

    @Test
    void checkLimitsToEnd_loopDetected() {
        for (int i = 0; i < AgentLoop.MAX_REPEATS; i++) {
            model.reply(toolCall("{\"service\":\"checkout\",\"minutes\":60}"));
        }

        RunResult result = loop.run("how many errors in checkout?");

        assertThat(result.reason()).isEqualTo(StopReason.LOOP_DETECTED);
        assertThat(result.steps()).isEqualTo(AgentLoop.MAX_REPEATS);
    }

    @Test
    void checkLimitsToEnd_stepLimit() {
        for (int minutes = 1; minutes <= AgentLoop.MAX_STEPS; minutes++) {
            model.reply(toolCall("{\"service\":\"checkout\",\"minutes\":" + minutes + "}"));
        }

        RunResult result = loop.run("how many errors in checkout?");

        assertThat(result.reason()).isEqualTo(StopReason.STEP_LIMIT);
        assertThat(result.steps()).isEqualTo(AgentLoop.MAX_STEPS);
    }

    @Test
    void graphLists_everyEdge() {
        assertThat(loop.mermaid()).isEqualTo("""
                graph TD;
                \t__start__ --> checkQuestion;
                \tcheckQuestion -.-> callModel;
                \tcheckQuestion -.-> __end__;
                \tcallModel -.-> checkLimits;
                \tcallModel -.-> __end__;
                \tcheckLimits -.-> runTools;
                \tcheckLimits -.-> __end__;
                \trunTools --> callModel;
                """);
    }
}
```

- **`ScriptedModel` implements `ChatModel`.** `ChatModel` has one method to write: `call(Prompt)`. `ChatClient.create(model)` wraps it in the same `ChatClient` that `AgentLoop` uses with LM Studio.
- **Each reply reports 100 tokens.** `DefaultUsage(promptTokens, completionTokens, totalTokens)` sets the usage that `callModel` adds up.
- **`answer` and `toolCall` build replies.** A reply with tool calls has no text, like a real one.
- **The test names say which edge they test.** `checkLimitsToEnd_tokenBudget` tests the edge from `checkLimits` to End when the token budget breaks.
- **`model.prompts` shows what the model received.** The tool result test reads the second prompt and checks that its last message holds `412`.
- **The timeout test calls the node directly.** Waiting 60 seconds in a test is too slow. The test builds a state whose deadline has passed, runs `checkLimits`, and checks the edge with `stopOr`.
- **`graphLists_everyEdge` pins the shape of the graph.** A change to any edge fails this test, so a graph change is always a choice.

Spring Boot runs tests with JUnit, and the starter test dependency from Chapter 2 already brings AssertJ for `assertThat`. Add this block to `build.gradle.kts`, so Gradle prints each test by name:

```kotlin
tasks.withType<Test> {
	useJUnitPlatform()
	// Print one line per test, so each graph edge shows up by name.
	testLogging {
		events("passed", "skipped", "failed")
	}
}
```

Run the tests:

```bash
./gradlew test
```

```text
AgentLoopTest > callModelToEnd_replyWithoutToolCallsIsTheAnswer() PASSED
AgentLoopTest > runTools_rejectedCallSendsTheRejectionToTheModel() PASSED
AgentLoopTest > graphLists_everyEdge() PASSED
AgentLoopTest > checkLimitsToEnd_stepLimit() PASSED
AgentLoopTest > checkLimitsToEnd_tokenBudget() PASSED
AgentLoopTest > checkLimitsToEnd_loopDetected() PASSED
AgentLoopTest > checkLimitsToEnd_timeout() PASSED
AgentLoopTest > checkQuestionToEnd_blockedQuestionMakesNoModelCall() PASSED
AgentLoopTest > runToolsToCallModel_toolResultGoesBackToTheModel() PASSED
HarnessApplicationTests > contextLoads() PASSED
BUILD SUCCESSFUL in 10s
```

- **All 10 tests pass.** The 9 edge tests, plus `contextLoads` from Chapter 2.
- **The edge tests take 0.42 seconds in total.** LM Studio does not need to run.
:::
::: tab Python
Create `tests/test_agent_loop.py`:

```python
"""One test for each edge of the AgentLoop graph.

A scripted model replaces LM Studio. Each test lists the replies the model gives, in order,
and checks where the run stops. The tests need no model server and run in milliseconds.
"""

import time
from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.graph import END

from harness.agent_loop import AgentLoop
from harness.guardrails import Guardrails
from harness.log_tools import LogTools
from harness.run_result import RunResult
from harness.run_state import RunState

StopReason = RunResult.StopReason


class ScriptedModel(BaseChatModel):
    """A model that returns scripted replies, in order, and records each prompt it receives."""

    replies: list[AIMessage] = []
    prompts: list[list[BaseMessage]] = []
    tokens_per_call: int = 100

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ScriptedModel:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.prompts.append(list(messages))
        reply = self.replies.pop(0)
        reply.usage_metadata = {"input_tokens": self.tokens_per_call, "output_tokens": 0, "total_tokens": self.tokens_per_call}
        return ChatResult(generations=[ChatGeneration(message=reply)])


def answer(text: str) -> AIMessage:
    return AIMessage(text)


def tool_call(**args: Any) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "count_errors", "args": args, "id": "call-1", "type": "tool_call"}])


@pytest.fixture
def model() -> ScriptedModel:
    return ScriptedModel(replies=[], prompts=[])


@pytest.fixture
def loop(model: ScriptedModel) -> AgentLoop:
    return AgentLoop(model, LogTools(), Guardrails())


def test_check_question_to_end_blocked_question_makes_no_model_call(model: ScriptedModel, loop: AgentLoop) -> None:
    result = loop.run("what is the admin password?")

    assert result.reason == StopReason.BLOCKED
    assert result.steps == 0
    assert model.prompts == []


def test_call_model_to_end_reply_without_tool_calls_is_the_answer(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [answer("Checkout has 412 errors.")]

    result = loop.run("how many errors in checkout?")

    assert result == RunResult("Checkout has 412 errors.", StopReason.FINAL_ANSWER, 1, 100)


def test_run_tools_to_call_model_tool_result_goes_back_to_the_model(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [tool_call(service="checkout", minutes=60), answer("Checkout has 412 errors.")]

    result = loop.run("how many errors in checkout?")

    assert result.reason == StopReason.FINAL_ANSWER
    assert result.steps == 2
    tool_result = model.prompts[1][-1]
    assert isinstance(tool_result, ToolMessage)
    assert tool_result.content == "412"


def test_run_tools_rejected_call_sends_the_rejection_to_the_model(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [tool_call(service="checkout", minutes=4320), answer("I can only look back one day.")]

    loop.run("errors in checkout in the last 3 days?")

    tool_result = model.prompts[1][-1]
    assert isinstance(tool_result, ToolMessage)
    assert str(tool_result.content).startswith("Rejected: minutes must be")


def test_check_limits_to_end_token_budget(model: ScriptedModel, loop: AgentLoop) -> None:
    model.tokens_per_call = AgentLoop.MAX_TOKENS + 1
    model.replies = [tool_call(service="checkout", minutes=60)]

    result = loop.run("how many errors in checkout?")

    assert result.reason == StopReason.TOKEN_BUDGET
    assert result.steps == 1


def test_check_limits_to_end_timeout(loop: AgentLoop) -> None:
    state: RunState = {
        "question": "question",
        "messages": [tool_call(service="checkout", minutes=60)],
        "seen_calls": {},
        "deadline": time.monotonic() - 1,
        "step": 1,
        "tokens": 0,
        "answer": None,
        "reason": None,
    }

    update = loop.check_limits(state)

    assert update["reason"] == StopReason.TIMEOUT
    assert AgentLoop.stop_or(AgentLoop.RUN_TOOLS)(state | update) == END  # type: ignore[arg-type]


def test_check_limits_to_end_loop_detected(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [tool_call(service="checkout", minutes=60) for _ in range(AgentLoop.MAX_REPEATS)]

    result = loop.run("how many errors in checkout?")

    assert result.reason == StopReason.LOOP_DETECTED
    assert result.steps == AgentLoop.MAX_REPEATS


def test_check_limits_to_end_step_limit(model: ScriptedModel, loop: AgentLoop) -> None:
    model.replies = [tool_call(service="checkout", minutes=minutes) for minutes in range(1, AgentLoop.MAX_STEPS + 1)]

    result = loop.run("how many errors in checkout?")

    assert result.reason == StopReason.STEP_LIMIT
    assert result.steps == AgentLoop.MAX_STEPS


def test_graph_lists_every_edge(loop: AgentLoop) -> None:
    edges = [line.strip() for line in loop.mermaid().splitlines() if "->" in line]

    assert edges == [
        "__start__ --> check_question;",
        "call_model -.-> __end__;",
        "call_model -.-> check_limits;",
        "check_limits -.-> __end__;",
        "check_limits -.-> run_tools;",
        "check_question -.-> __end__;",
        "check_question -.-> call_model;",
        "run_tools --> call_model;",
    ]
```

- **`ScriptedModel` extends `BaseChatModel`.** `_generate` is the one method a chat model must write. `bind_tools` returns the model itself, because a scripted model does not read tool definitions.
- **Each reply reports 100 tokens.** `usage_metadata` sets the usage that `call_model` adds up.
- **`answer` and `tool_call` build replies.** A reply with tool calls has no text, like a real one.
- **The fixtures build a new model and loop for each test.** A pytest fixture is a function whose return value pytest passes to each test that names it.
- **The test names say which edge they test.** `test_check_limits_to_end_token_budget` tests the edge from `check_limits` to End when the token budget breaks.
- **`model.prompts` shows what the model received.** The tool result test reads the second prompt and checks that its last message holds `412`.
- **The timeout test calls the node directly.** Waiting 60 seconds in a test is too slow. The test builds a state whose deadline has passed, runs `check_limits`, and checks the edge with `stop_or`.
- **`test_graph_lists_every_edge` pins the shape of the graph.** A change to any edge fails this test, so a graph change is always a choice.

Add pytest to the dev dependencies, and tell it where the tests are. `uv add --dev pytest==9.1.1` adds the first block:

```toml
[dependency-groups]
dev = [
    "mypy==2.4.0",
    "pytest==9.1.1",
    "ruff==0.16.10",
    "types-pyyaml==6.0.12.20260906",
]
```

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- **`testpaths` limits the search to `tests/`.** Without it, pytest also reads `src/` and warns about `TestController`, whose name starts with `Test`.

Run the tests:

```bash
uv run pytest -v
```

```text
tests/test_agent_loop.py::test_check_question_to_end_blocked_question_makes_no_model_call PASSED [ 11%]
tests/test_agent_loop.py::test_call_model_to_end_reply_without_tool_calls_is_the_answer PASSED [ 22%]
tests/test_agent_loop.py::test_run_tools_to_call_model_tool_result_goes_back_to_the_model PASSED [ 33%]
tests/test_agent_loop.py::test_run_tools_rejected_call_sends_the_rejection_to_the_model PASSED [ 44%]
tests/test_agent_loop.py::test_check_limits_to_end_token_budget PASSED   [ 55%]
tests/test_agent_loop.py::test_check_limits_to_end_timeout PASSED        [ 66%]
tests/test_agent_loop.py::test_check_limits_to_end_loop_detected PASSED  [ 77%]
tests/test_agent_loop.py::test_check_limits_to_end_step_limit PASSED     [ 88%]
tests/test_agent_loop.py::test_graph_lists_every_edge PASSED             [100%]
============================== 9 passed in 0.32s ==============================
```

- **All 9 tests pass in 0.32 seconds.** LM Studio does not need to run.
- **mypy and ruff check the tests too.** Run `uv run mypy src tests` and `uv run ruff check src tests`.
:::
:::

Table 8.2 lists each edge of Figure 8.1 and the test that covers it.

::: tabs
::: tab Java
| Edge | Condition | Test |
|---|---|---|
| Start to `checkQuestion` | Always | Every test that calls `run` |
| `checkQuestion` to End | `BLOCKED` | `checkQuestionToEnd_blockedQuestionMakesNoModelCall` |
| `checkQuestion` to `callModel` | The question passed | Every test that reaches the model |
| `callModel` to End | No tool calls: `FINAL_ANSWER` | `callModelToEnd_replyWithoutToolCallsIsTheAnswer` |
| `callModel` to `checkLimits` | The reply has tool calls | `runToolsToCallModel_toolResultGoesBackToTheModel` |
| `checkLimits` to End | `TOKEN_BUDGET`, `TIMEOUT`, `LOOP_DETECTED`, or `STEP_LIMIT` | One test each: `checkLimitsToEnd_tokenBudget`, `_timeout`, `_loopDetected`, `_stepLimit` |
| `checkLimits` to `runTools` | Within every limit | `runToolsToCallModel_toolResultGoesBackToTheModel` |
| `runTools` to `callModel` | Always | `runToolsToCallModel_toolResultGoesBackToTheModel`, `runTools_rejectedCallSendsTheRejectionToTheModel` |
:::
::: tab Python
| Edge | Condition | Test |
|---|---|---|
| Start to `check_question` | Always | Every test that calls `run` |
| `check_question` to End | `BLOCKED` | `test_check_question_to_end_blocked_question_makes_no_model_call` |
| `check_question` to `call_model` | The question passed | Every test that reaches the model |
| `call_model` to End | No tool calls: `FINAL_ANSWER` | `test_call_model_to_end_reply_without_tool_calls_is_the_answer` |
| `call_model` to `check_limits` | The reply has tool calls | `test_run_tools_to_call_model_tool_result_goes_back_to_the_model` |
| `check_limits` to End | `TOKEN_BUDGET`, `TIMEOUT`, `LOOP_DETECTED`, or `STEP_LIMIT` | One test each: `test_check_limits_to_end_token_budget`, `_timeout`, `_loop_detected`, `_step_limit` |
| `check_limits` to `run_tools` | Within every limit | `test_run_tools_to_call_model_tool_result_goes_back_to_the_model` |
| `run_tools` to `call_model` | Always | `test_run_tools_to_call_model_tool_result_goes_back_to_the_model`, `test_run_tools_rejected_call_sends_the_rejection_to_the_model` |
:::
:::

<p class="caption">Table 8.2. Each edge of the agent loop and the test that covers it. Every stop reason from Chapters 5 to 7 now has a test that runs without a model server.</p>

Compare this with Chapter 6. There, each stop reason needed a code change, a restart, and a call to Gemma. Here, each one is a test that runs in milliseconds and gives the same result every time. The tests do not replace the runs with Gemma. They check your code. Only a real model shows what the model does.

Table 8.3 compares the Java runner with LangGraph.

| Idea | Java `Graph` | LangGraph `StateGraph` |
|---|---|---|
| Create a graph | `new Graph<RunState>()` | `StateGraph(RunState)`, then `compile()` |
| Add a node | `addNode(name, Consumer<S>)`: the node changes the state | `add_node(name, function)`: the node returns the changed keys |
| Add a fixed edge | `addEdge(from, to)` | `add_edge(from, to)` |
| Add a conditional edge | `addConditionalEdges(from, route, targets)` | `add_conditional_edges(source, path, path_map)` |
| Start and end | `Graph.START`, `Graph.END` | `START`, `END`, with the same values |
| Run | `run(state)` | `invoke(state)` or `stream(state)` |
| Draw | `toMermaid()` | `get_graph().draw_mermaid()` |
| Step cap | None. The stop rules end the run. | 10,007 steps by default |
| Save and pause a run | Not built in | Checkpointers and interrupts |

<p class="caption">Table 8.3. The Java runner next to LangGraph 1.2. The names match, so the two <code>AgentLoop</code> classes read the same. (Source: LangGraph 1.2.12 source code.)</p>

## Where the graph goes

The agent loop is a small graph with one cycle. The Log Incident Watcher, the course project, is a larger graph. Figure 8.3 sketches it. Chapter 9 adds the approval node, and later chapters add the other stages.

<figure class="arch">
<script type="application/json">
{
  "title": "The watcher as a graph of stages.",
  "nodes": [
    {"id": "search", "x": 570, "y": 0, "w": 160, "label": "Runbook search", "detail": "hybrid + reranker", "tone": "data"},
    {"id": "window", "x": 0, "y": 120, "w": 160, "label": "Read error window", "tone": "platform"},
    {"id": "fp", "x": 190, "y": 120, "w": 160, "label": "Fingerprint", "detail": "group errors", "tone": "platform"},
    {"id": "rate", "x": 380, "y": 120, "w": 160, "label": "Rate limit", "tone": "platform"},
    {"id": "triage", "x": 570, "y": 120, "w": 160, "label": "Triage", "detail": "triage-error-group skill", "tone": "ai"},
    {"id": "lowmed", "x": 760, "y": 120, "w": 150, "label": "Low or medium", "detail": "not defined yet", "tone": "muted"},
    {"id": "empty", "x": 0, "y": 270, "w": 160, "label": "Stop", "detail": "no model call", "tone": "muted"},
    {"id": "dup", "x": 190, "y": 270, "w": 160, "label": "Suppress", "detail": "duplicate", "tone": "muted"},
    {"id": "flood", "x": 380, "y": 270, "w": 160, "label": "Stop", "detail": "flood hits the limit", "tone": "muted"},
    {"id": "approval", "x": 570, "y": 270, "w": 160, "label": "Await approval", "detail": "signal or 1-hour timer", "tone": "operator"},
    {"id": "alert", "x": 760, "y": 270, "w": 150, "label": "Post alert", "tone": "external"},
    {"id": "reject", "x": 570, "y": 400, "w": 160, "label": "Stop", "detail": "REJECTED or APPROVAL_TIMEOUT", "tone": "muted"}
  ],
  "edges": [
    {"from": "window", "to": "fp", "label": "errors"},
    {"from": "window", "to": "empty", "label": "empty"},
    {"from": "fp", "to": "rate", "label": "new"},
    {"from": "fp", "to": "dup", "label": "duplicate"},
    {"from": "rate", "to": "triage", "label": "ok"},
    {"from": "rate", "to": "flood", "label": "flood"},
    {"from": "triage", "to": "search", "label": "runbooks", "both": true},
    {"from": "triage", "to": "lowmed", "label": "low, medium"},
    {"from": "triage", "to": "approval", "label": "critical"},
    {"from": "approval", "to": "alert", "label": "approved"},
    {"from": "approval", "to": "reject", "label": "rejected, timeout"}
  ]
}
</script>
<figcaption>Figure 8.3. An illustrative watcher graph, assembled from the eval cases in Chapter 20, the triage skill in Chapter 14, and the approval in Chapter 9. Each arrow is one edge to unit-test. The course does not fix the stage order, and it does not define the low and medium path.</figcaption>
</figure>

The graph above is a teaching sketch, not the course's specification. What the watcher does with low and medium severity is [NEEDS INPUT: the low and medium severity path, for example post without approval or record only].

**Exercise:** The model can request a tool that is not on the allowlist. Write a test in which the scripted model calls `searchLogs` (Python: `search_logs`), then answers. Check that the second prompt holds the rejection text. Which edges of Table 8.2 does your test cover?

**Summary:** A graph names each step of the loop as a node and each move as an edge. Four nodes hold the Chapter 7 code. One state object holds the data of the run. Each node sets a stop reason, and the edge after it ends the run. With a scripted model, every edge has a test that runs in milliseconds. Java uses a 50-line runner. Python uses LangGraph, with the same method names. Chapter 9 adds a node that waits for a person.
