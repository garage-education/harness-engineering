package com.garageeducation.harness;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * Sends one question to the chat model and returns its text reply.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class Assistant {

    private static final String SYSTEM = "You are a careful assistant. Answer in two sentences or fewer.";

    private final ChatClient chat;

    /**
     * Asks the model one question.
     *
     * <p>The system message limits the reply to two sentences.
     *
     * @param question the user's question, in plain text
     * @return the model's final text reply
     */
    public String askAutoToolCall(String question) {
        log.debug("[auto] Spring AI runs every tool call. Question: {}", question);
        String answer = chat.prompt()
                .system(SYSTEM)
                .user(question)
                .call()
                .content();
        log.debug("[auto] Final answer: {}", answer);
        return answer;
    }
}
