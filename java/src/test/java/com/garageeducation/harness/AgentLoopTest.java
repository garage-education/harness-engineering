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
