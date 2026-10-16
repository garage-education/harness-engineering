package com.garageeducation.harness;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

/**
 * Sends one question to the chat model and returns its text reply.
 *
 * <p>The model can call the tools in {@link LogTools}.
 * {@link ChatClient} runs each tool call and sends the result back to the model.
 */
@Service
public class Assistant {

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
     * Asks the model one question.
     *
     * <p>The system message limits the reply to two sentences.
     *
     * @param question the user's question, in plain text
     * @return the model's final text reply
     */
    public String ask(String question) {
        return chat.prompt()
                .system("You are a careful assistant. Answer in two sentences or fewer.")
                .user(question)
                .tools(logTools)
                .call()
                .content();
    }
}
