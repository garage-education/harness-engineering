---
title: "Chapter 3: The model call"
sidebar_label: "3. The model call"
description: One ChatClient call, from a question to a text reply, behind one HTTP endpoint.
---

This chapter sends one question to Gemma and returns its text reply.

**Objectives:**

- Create one shared `ChatClient`.
- Write the `Assistant` service.
- Expose it over HTTP with `TestController`.
- See what the model answers without tools.

## Step 1: The chat client

The OpenAI starter provides a `ChatClient.Builder`, already pointed at LM Studio. Build one client and share it. Create `AiConfig.java`:

```java
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
```

- `@Configuration` marks a class that creates objects for Spring.
- `@Bean` registers the returned `ChatClient`. Spring calls this method once at startup.
- Any class that asks for a `ChatClient` now receives this one.

## Step 2: The Assistant

```java
package com.garageeducation.harness;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

import lombok.RequiredArgsConstructor;

/**
 * Sends one question to the chat model and returns its text reply.
 */
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
        return chat.prompt()
                .system(SYSTEM)
                .user(question)
                .call()
                .content();
    }
}
```

- `@Service` tells Spring to create one `Assistant` at startup.
- `@RequiredArgsConstructor` comes from Lombok. It writes a constructor with one argument per `final` field. Spring calls it and passes the `ChatClient` from Step 1.
- `.system(…)` sets the rules. `.user(…)` sets the question.
- `.call()` sends the request. `.content()` returns the reply as a `String`.
- Your code never builds the HTTP request. Figure 3.1 shows the call.
- The name `askAutoToolCall` looks ahead. Chapter 4 adds tools, and `ChatClient` runs them for you.

## Step 3: The controller

```java
package com.garageeducation.harness;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import lombok.RequiredArgsConstructor;

/**
 * Exposes {@link Assistant} over HTTP for manual tests.
 *
 * <p>Example: {@code GET http://localhost:8080/askAutoToolCall?input=how many error events?}
 */
@RestController
@RequiredArgsConstructor
public class TestController {

    private final Assistant assistant;

    /**
     * Sends the {@code input} query parameter to the model.
     *
     * @param input the question; the request fails without it
     * @return the model's text reply
     */
    @GetMapping("/askAutoToolCall")
    public String askAutoToolCall(@RequestParam String input) {
        return assistant.askAutoToolCall(input);
    }
}
```

- `@RestController` turns each method's return value into the HTTP response.
- `@GetMapping("/askAutoToolCall")` maps `GET /askAutoToolCall` to the method.
- `@RequestParam` reads `input` from the query string.

<figure class="seq">
<script type="application/json">
{
  "title": "GET /askAutoToolCall?input=…: one model call.",
  "lifelines": [
    {"id": "http", "label": "TestController", "tone": "platform"},
    {"id": "code", "label": "Assistant.askAutoToolCall", "tone": "platform"},
    {"id": "client", "label": "ChatClient", "tone": "platform"},
    {"id": "model", "label": "Gemma", "tone": "subscriber"}
  ],
  "messages": [
    {"from": "http", "to": "code", "label": "askAutoToolCall(input)"},
    {"from": "code", "to": "client", "label": "prompt().system(…).user(question)"},
    {"from": "client", "to": "model", "label": ".call(): request in the provider format"},
    {"from": "model", "to": "client", "label": "reply text", "kind": "response"},
    {"from": "client", "to": "code", "label": ".content(): a String", "kind": "response"},
    {"from": "code", "to": "http", "label": "reply text", "kind": "response"}
  ]
}
</script>
<figcaption>Figure 3.1. One model call. No tools are attached, so the model answers from its own text.</figcaption>
</figure>

## Step 4: Run the first call

Restart the app. Send a question:

```bash
curl -G http://localhost:8080/askAutoToolCall --data-urlencode "input=how many error events?"
```

The model has no data. It asks for the logs:

```text
Please provide the logs or data you are referring to. Once you share them, I can count the error events for you.
```

A request without `input` fails. The model is never called.

Or run the Chapter 3 request in `requests/harness.http`.

**Summary:** One question reaches Gemma and returns text. The model cannot read logs yet. Chapter 4 gives it a tool.
