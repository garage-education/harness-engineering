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
