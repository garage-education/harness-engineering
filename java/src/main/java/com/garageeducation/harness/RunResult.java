package com.garageeducation.harness;

/**
 * The outcome of one agent run.
 *
 * <p>Every run returns one {@code RunResult}. The {@link StopReason} says why the run ended.
 *
 * @param answer the model's final text; {@code null} when the run stopped before a final answer
 * @param reason the reason the run stopped
 * @param steps  the number of model calls the run made
 * @param tokens the total tokens the run used, as reported by the model server
 */
public record RunResult(String answer, StopReason reason, int steps, int tokens) {

    /**
     * Why a run stopped. Each run stops for exactly one reason.
     */
    public enum StopReason {

        /** The model replied without tool calls. Its text is the answer. */
        FINAL_ANSWER,

        /** The run made {@code MAX_STEPS} model calls without a final answer. */
        STEP_LIMIT,

        /** The run used more than {@code MAX_TOKENS} tokens. */
        TOKEN_BUDGET,

        /** The run took longer than {@code TIMEOUT}. */
        TIMEOUT,

        /** The model requested the same tool call {@code MAX_REPEATS} times. */
        LOOP_DETECTED
    }
}
