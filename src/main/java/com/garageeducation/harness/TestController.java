package com.garageeducation.harness;

import java.util.List;

import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes {@link Assistant} and {@link AgentLoop} over HTTP for manual tests.
 *
 * <p>Example: {@code GET http://localhost:8080/askAutoToolCall?input=how many error events in checkout service?}
 */
@RestController
public class TestController {

    private final Assistant assistant;
    private final AgentLoop agentLoop;

    /**
     * Creates the controller.
     *
     * @param assistant the assistant that answers with one request
     * @param agentLoop the hand-written agent loop
     */
    public TestController(Assistant assistant, AgentLoop agentLoop) {
        this.assistant = assistant;
        this.agentLoop = agentLoop;
    }

    /**
     * Sends the question to the model. {@code ChatClient} runs the tools.
     *
     * @param input the question; the request fails without it
     * @return the model's text reply
     */
    @GetMapping("/askAutoToolCall")
    public String askAutoToolCall(@RequestParam String input) {
        return assistant.askAutoToolCall(input);
    }

    /**
     * Sends the question to the model and returns its tool calls without running them.
     *
     * @param input the question; the request fails without it
     * @return the tool calls as JSON: id, type, name, and arguments
     */
    @GetMapping("/askHaltToolCall")
    public List<ToolCall> askHaltToolCall(@RequestParam String input) {
        return assistant.askHaltToolCall(input);
    }

    /**
     * Runs the hand-written agent loop for the question.
     *
     * @param input the question; the request fails without it
     * @return the run result as JSON: answer, reason, steps, and tokens
     */
    @GetMapping("/run")
    public RunResult run(@RequestParam String input) {
        return agentLoop.run(input);
    }
}
