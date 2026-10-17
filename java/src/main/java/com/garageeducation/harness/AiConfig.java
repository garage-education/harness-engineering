package com.garageeducation.harness;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Creates the beans that talk to the model.
 */
@Configuration
public class AiConfig {

    /**
     * Builds one {@link ChatClient} for the whole app.
     *
     * <p>The OpenAI starter provides the builder, already pointed at LM Studio.
     * Every class that needs the model receives this client.
     *
     * @param builder the {@link ChatClient.Builder} from the OpenAI starter
     * @return the shared chat client
     */
    @Bean
    ChatClient chatClient(ChatClient.Builder builder) {
        return builder.build();
    }
}
