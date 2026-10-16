---
title: "Chapter 3: The model call"
sidebar_label: "3. The model call"
description: One ChatClient call, from a question to a text reply, behind one HTTP endpoint.
---

This chapter sends one question to Gemma and returns its text reply.

**Objectives:**

- Write the `Assistant` service.
- Expose it over HTTP with `TestController`.
- See what the model answers without tools.

## Step 1: The Assistant

```java
package com.garageeducation.harness;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

/**
 * Sends one question to the chat model and returns its text reply.
 */
@Service
public class Assistant {

    private final ChatClient chat;

    /**
     * Builds the client from the builder that Spring Boot provides.
     *
     * @param builder the {@link ChatClient.Builder} from the OpenAI starter
     */
    public Assistant(ChatClient.Builder builder) {
        this.chat = builder.build();
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
                .call()
                .content();
    }
}
```

- Spring Boot creates `ChatClient.Builder` from the OpenAI starter.
- `.system(…)` sets the rules. `.user(…)` sets the question.
- `.call()` sends the request. `.content()` returns the reply as a `String`.
- Your code never builds the HTTP request. Figure 3.1 shows the call.

## Step 2: The controller

```java
package com.garageeducation.harness;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes {@link Assistant} over HTTP for manual tests.
 *
 * <p>Example: {@code GET http://localhost:8080/ask?input=what is an agent harness?}
 */
@RestController
public class TestController {

    private final Assistant assistant;

    /**
     * Creates the controller.
     *
     * @param assistant the assistant that answers each request
     */
    public TestController(Assistant assistant) {
        this.assistant = assistant;
    }

    /**
     * Sends the {@code input} query parameter to the model.
     *
     * @param input the question; the request fails without it
     * @return the model's text reply
     */
    @GetMapping("/ask")
    public String ask(@RequestParam String input) {
        return assistant.ask(input);
    }
}
```

`GET /ask` reads the `input` parameter and returns the model's reply.

<figure class="seq">
<script type="application/json">
{
  "title": "GET /ask?input=…: one model call.",
  "lifelines": [
    {"id": "http", "label": "TestController", "tone": "platform"},
    {"id": "code", "label": "Assistant.ask", "tone": "platform"},
    {"id": "client", "label": "ChatClient", "tone": "platform"},
    {"id": "model", "label": "Gemma", "tone": "subscriber"}
  ],
  "messages": [
    {"from": "http", "to": "code", "label": "ask(input)"},
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

## Step 3: Run the first call

Restart the app. Send a question:

```bash
curl -G http://localhost:8080/ask --data-urlencode "input=how many error events?"
```

The model has no data. It asks for the logs:

```text
Please provide the logs or data you are referring to. Once you share them, I can count the error events for you.
```

A request without `input` fails. The model is never called.

Or run the Chapter 3 request in `requests/harness.http`. It works only until Chapter 4 renames the endpoint.

**Summary:** One question reaches Gemma and returns text. The model cannot read logs yet. Chapter 4 gives it a tool.
