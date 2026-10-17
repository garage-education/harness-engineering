---
title: "Chapter 7: Guardrails"
sidebar_label: "7. Guardrails"
description: Check the question and every tool call in code, before the model or a tool sees them.
---

This chapter adds guardrails to the loop: checks in your code that run before the model or a tool sees any input.

**Objectives:**

- Explain why a tool description is not a guardrail.
- Block a question before the first model call.
- Check each tool call's name and arguments before the tool runs.
- Compare your guardrails with Spring AI's `SafeGuardAdvisor` and LangChain's middleware.

Chapter 6 stops a run that costs too much, takes too long, or repeats itself. Those rules watch the run as a whole. They never look inside one tool call. A tool call can still name a tool this agent must not use. It can carry an argument the tool cannot handle. A question can ask for data the agent must never return.

A guardrail is a check in your code that stops such input before it does harm. The model cannot argue with a guardrail, because the model never runs it. Your code does.

## Step 1: See why the description is not enough

The `countErrors` description says the window runs "from 1 to 1440" minutes. That text goes to the model inside the tool definition, as Figure 4.1 shows. It is a request to the model, not a rule. Ask the Chapter 4 endpoint about three days:

```bash
curl -G http://localhost:8080/askAutoToolCall --data-urlencode "input=how many error events in the checkout service in the last 3 days?"
```

::: tabs
::: tab Java
```text
23:10:17.140 DEBUG DispatcherServlet                        GET "/askAutoToolCall?input=how+many+error+events+in+the+checkout+service+in+the+last+3+days%3F", parameters={masked}
23:10:17.140 DEBUG Assistant                                [auto] Spring AI runs every tool call. Question: how many error events in the checkout service in the last 3 days?
23:10:21.094 INFO  ChatModelCompletionObservationHandler    Chat Model Completion:
[]
23:10:21.094 INFO  ChatModelPromptContentObservationHandler Chat Model Prompt Content:
["You are a careful assistant. Answer in two sentences or fewer.", "how many error events in the checkout service in the last 3 days?"]
23:10:21.094 DEBUG DefaultToolCallingManager                Executing tool call: countErrors
23:10:21.094 DEBUG LogTools                                 [tool] countErrors(service=checkout, minutes=4320) returned 412
23:10:21.418 INFO  ChatModelCompletionObservationHandler    Chat Model Completion:
["There were 412 error events in the checkout service over the last 3 days."]
23:10:21.418 INFO  ChatModelPromptContentObservationHandler Chat Model Prompt Content:
["You are a careful assistant. Answer in two sentences or fewer.", "how many error events in the checkout service in the last 3 days?", "", ""]
23:10:21.418 DEBUG Assistant                                [auto] Final answer: There were 412 error events in the checkout service over the last 3 days.
23:10:21.418 DEBUG DispatcherServlet                        Completed 200 OK
```

- **The model asked for `minutes=4320`.** That is 3 days, three times the limit in the description.
- **Spring AI ran the tool anyway.** `ToolCallingAdvisor` finds the tool by name and calls it. It does not check the argument values.
- **The answer sounds right.** Nothing in the reply tells the user that a limit was broken.
:::
::: tab Python
```text
23:07:11.760 DEBUG harness.assistant                        [auto] LangChain runs every tool call. Question: how many error events in the checkout service in the last 3 days?
23:07:11.762 INFO  ChatModelPromptContent                   Chat Model Prompt Content:
['You are a careful assistant. Answer in two sentences or fewer.', 'how many error events in the checkout service in the last 3 days?']
23:07:17.855 INFO  httpx2                                   HTTP Request: POST http://localhost:1234/v1/chat/completions "HTTP/1.1 200 OK"
23:07:17.856 INFO  ChatModelCompletion                      Chat Model Completion:
[]
23:07:17.857 DEBUG ToolCalling                              Executing tool call: count_errors
23:07:17.857 DEBUG harness.log_tools                        [tool] count_errors(service=checkout, minutes=4320) returned 412
23:07:17.858 INFO  ChatModelPromptContent                   Chat Model Prompt Content:
['You are a careful assistant. Answer in two sentences or fewer.', 'how many error events in the checkout service in the last 3 days?', '', '412']
23:07:18.198 INFO  httpx2                                   HTTP Request: POST http://localhost:1234/v1/chat/completions "HTTP/1.1 200 OK"
23:07:18.198 INFO  ChatModelCompletion                      Chat Model Completion:
['There were 412 error events in the checkout service over the last 3 days.']
23:07:18.199 DEBUG harness.assistant                        [auto] Final answer: There were 412 error events in the checkout service over the last 3 days.
23:07:18.199 INFO  uvicorn.access                           127.0.0.1:53474 - "GET /askAutoToolCall?input=how%20many%20error%20events%20in%20the%20checkout%20service%20in%20the%20last%203%20days%3F HTTP/1.1" 200
```

- **The model asked for `minutes=4320`.** That is 3 days, three times the limit in the description.
- **LangChain ran the tool anyway.** The agent's tools node checks that each argument has the right type. 4320 is a valid `int`, so it passes. The tools node never checks the range.
- **The answer sounds right.** Nothing in the reply tells the user that a limit was broken.
:::
:::

The fake `countErrors` ignores the window, so nothing breaks here. A real log store would scan three days of logs. That is slower and costs more than the tool promises. A tool that changes data, such as one that restarts a service, could do real damage with one bad argument.

Gemma does not do this every time. In 4 runs of this question, it asked for 4320 minutes 3 times and for 1440 minutes once. A rule that holds only most of the time is not a rule. A guardrail must hold on every run, so it must be code.

Table 7.1 lists the guardrails in `AgentLoop` after this chapter.

| Guardrail | When it runs | What it checks | On failure |
|---|---|---|---|
| Blocked words | Once, before the first model call | The question contains no word from `BLOCKED_WORDS` | The run stops with `BLOCKED`. The model is never called. |
| Tool allowlist | For each tool call, before the tool runs | The tool name is in `ALLOWED_TOOLS` | The tool does not run. The model gets a rejection text as the tool result. |
| Argument checks | For each tool call, after the allowlist | `service` is a name. `minutes` is a whole number from 1 to 1440. | The tool does not run. The model gets a rejection text as the tool result. |
| Loop detection | After each model reply, from Chapter 6 | The same call has not been requested 3 times | The run stops with `LOOP_DETECTED` |

<p class="caption">Table 7.1. The guardrails in <code>AgentLoop</code>. Each one is a few lines of code that the model cannot skip.</p>

The two kinds of failure get two different responses:

- **A bad question ends the run.** No tool call can fix the question, so the loop does not start.
- **A bad tool call goes back to the model.** The rejection text says what was wrong. The model can fix its call, or explain the limit to the user. The run goes on.

Figure 7.1 shows where each check sits in the loop.

<figure class="flow">
<script type="application/json">
{
  "title": "The guardrails in AgentLoop, in order.",
  "steps": [
    {"label": "A question arrives"},
    {"label": "Is it free of blocked words?", "no": "Stop: BLOCKED"},
    {"label": "Send the messages to the model"},
    {"label": "Does the reply have tool calls?", "no": "Stop: FINAL_ANSWER"},
    {"label": "Within the Chapter 6 limits?", "no": "Stop: TOKEN_BUDGET, TIMEOUT, or LOOP_DETECTED"},
    {"label": "For each call: is the tool on the allowlist?", "no": "Return a rejection as the tool result"},
    {"label": "Are the arguments in range?", "no": "Return a rejection as the tool result"},
    {"label": "Run the tool", "tone": "platform"}
  ]
}
</script>
<figcaption>Figure 7.1. The guardrails in <code>AgentLoop.run</code>. A blocked question costs no model call. A rejected tool call never runs, and the model reads why.</figcaption>
</figure>

- **The question check runs first.** A blocked question never reaches the model, so it costs 0 tokens.
- **The Chapter 6 limits run next, unchanged.** A run over budget stops before any tool check.
- **The tool checks run last, once for each call.** A rejected call still counts for loop detection. A model that repeats the same rejected call 3 times stops with `LOOP_DETECTED`.

## Step 2: Write the guardrails

Put every check in one class. `AgentLoop` calls it. The class knows nothing about the loop. You can read, test, and change all the rules in one place.

::: tabs
::: tab Java
Create `Guardrails.java`:

```java
package com.garageeducation.harness;

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.stereotype.Component;

import tools.jackson.databind.json.JsonMapper;

/**
 * The checks the agent loop runs before the model or a tool sees any input.
 *
 * <p>Each check is plain Java. The model cannot talk its way past it.
 * <ul>
 *   <li>{@link #checkQuestion} runs once, before the first model call.</li>
 *   <li>{@link #checkToolCall} runs for each tool call, before the tool runs.</li>
 * </ul>
 *
 * <p>Each method returns {@code null} when the input passes, or a rejection text when it fails.
 */
@Component
public class Guardrails {

    /** Words that block a question before any model call. The check ignores case. */
    static final List<String> BLOCKED_WORDS = List.of("password", "credit card");

    /** The only tools this agent may run, by name. */
    static final Set<String> ALLOWED_TOOLS = Set.of("countErrors");

    /** The shortest look-back window {@code countErrors} accepts, in minutes. */
    static final int MIN_MINUTES = 1;

    /** The longest look-back window {@code countErrors} accepts, in minutes: one day. */
    static final int MAX_MINUTES = 1440;

    /**
     * Checks the user's question against {@link #BLOCKED_WORDS}.
     *
     * @param question the user's question, in plain text
     * @return {@code null} when the question passes; otherwise the rejection text
     */
    public String checkQuestion(String question) {
        String text = question.toLowerCase(Locale.ROOT);
        for (String word : BLOCKED_WORDS) {
            if (text.contains(word)) {
                return "Blocked: the question contains \"" + word + "\".";
            }
        }
        return null;
    }

    /**
     * Checks one tool call: the name against {@link #ALLOWED_TOOLS}, then the arguments.
     *
     * <p>The rejection text goes back to the model as the tool result, so the model can fix its call.
     *
     * @param call one tool call from the model's reply
     * @return {@code null} when the call passes; otherwise the rejection text
     */
    public String checkToolCall(ToolCall call) {
        if (!ALLOWED_TOOLS.contains(call.name())) {
            return "Rejected: the tool " + call.name() + " is not allowed for this agent.";
        }
        Map<?, ?> args = JsonMapper.shared().readValue(call.arguments(), Map.class);
        if (!(args.get("service") instanceof String service) || service.isBlank()) {
            return "Rejected: service must be a service name, for example checkout.";
        }
        if (!(args.get("minutes") instanceof Integer minutes) || minutes < MIN_MINUTES || minutes > MAX_MINUTES) {
            return "Rejected: minutes must be a whole number from " + MIN_MINUTES + " to " + MAX_MINUTES
                    + ", got " + args.get("minutes") + ". Call the tool again with a valid value.";
        }
        return null;
    }
}
```

Read the class in five parts:

- **`BLOCKED_WORDS`** lists the words that end a run. `checkQuestion` lowers the case of the question first, so `Password` and `PASSWORD` are blocked too. Spring AI's `SafeGuardAdvisor` runs the same check. Step 5 shows it.
- **`ALLOWED_TOOLS`** names the tools this agent may run. The model sees only the tools you send with `.tools(logTools)`. It can still write any name in a tool call, because a tool call is just text the model writes. The allowlist matters more from Chapter 16, where each sub-agent gets its own set of tools.
- **`readValue` parses the arguments.** `call.arguments()` is a JSON string, for example `{"minutes":4320,"service":"checkout"}`. `JsonMapper.shared()` is Jackson's shared JSON reader. Spring Boot already includes Jackson. `readValue` turns the string into a `Map`.
- **`instanceof Integer minutes`** checks the type and names the value in one step. A missing value, a text value such as `"15"`, or a decimal such as `15.5` fails the check. Only then does the range check run.
- **Each method returns `null` when the input passes, or a rejection text.** The text is written for the model. It names the rule, the bad value, and what to do next.

`@Component` makes `Guardrails` a Spring bean, like `LogTools`. Spring creates one instance and passes it to every class that asks for it.
:::
::: tab Python
Create `guardrails.py`:

```python
"""The checks the agent loop runs before the model or a tool sees any input."""

from typing import Final

from langchain_core.messages import ToolCall


class Guardrails:
    """The checks the agent loop runs before the model or a tool sees any input.

    Each check is plain Python. The model cannot talk its way past it.

    - ``check_question`` runs once, before the first model call.
    - ``check_tool_call`` runs for each tool call, before the tool runs.

    Each method returns ``None`` when the input passes, or a rejection text when it fails.
    """

    BLOCKED_WORDS: Final = ("password", "credit card")
    """Words that block a question before any model call. The check ignores case."""

    ALLOWED_TOOLS: Final = frozenset({"count_errors"})
    """The only tools this agent may run, by name."""

    MIN_MINUTES: Final = 1
    """The shortest look-back window ``count_errors`` accepts, in minutes."""

    MAX_MINUTES: Final = 1440
    """The longest look-back window ``count_errors`` accepts, in minutes: one day."""

    def check_question(self, question: str) -> str | None:
        """Checks the user's question against ``BLOCKED_WORDS``.

        Args:
            question: the user's question, in plain text

        Returns:
            ``None`` when the question passes; otherwise the rejection text
        """
        text = question.lower()
        for word in self.BLOCKED_WORDS:
            if word in text:
                return f'Blocked: the question contains "{word}".'
        return None

    def check_tool_call(self, call: ToolCall) -> str | None:
        """Checks one tool call: the name against ``ALLOWED_TOOLS``, then the arguments.

        The rejection text goes back to the model as the tool result, so the model can fix its call.

        Args:
            call: one tool call from the model's reply

        Returns:
            ``None`` when the call passes; otherwise the rejection text
        """
        if call["name"] not in self.ALLOWED_TOOLS:
            return f"Rejected: the tool {call['name']} is not allowed for this agent."
        args = call["args"]
        service = args.get("service")
        if not isinstance(service, str) or not service.strip():
            return "Rejected: service must be a service name, for example checkout."
        minutes = args.get("minutes")
        if not isinstance(minutes, int) or not self.MIN_MINUTES <= minutes <= self.MAX_MINUTES:
            return (
                f"Rejected: minutes must be a whole number from {self.MIN_MINUTES} to {self.MAX_MINUTES}, "
                f"got {minutes}. Call the tool again with a valid value."
            )
        return None
```

Read the class in five parts:

- **`BLOCKED_WORDS`** lists the words that end a run. `check_question` lowers the case of the question first, so `Password` and `PASSWORD` are blocked too. Step 5 runs the same check as middleware.
- **`ALLOWED_TOOLS`** names the tools this agent may run. In Python, the tool name is the method name, `count_errors`. The model sees only the tools you pass to `bind_tools`. It can still write any name in a tool call, because a tool call is just text the model writes. The allowlist matters more from Chapter 16, where each sub-agent gets its own set of tools.
- **`call["args"]` is already a dictionary.** LangChain parses the model's JSON for you. Java has to parse it.
- **`isinstance(minutes, int)`** checks the type. A missing value, a text value such as `"15"`, or a decimal such as `15.5` fails the check. `self.MIN_MINUTES <= minutes <= self.MAX_MINUTES` then checks the range in one comparison.
- **Each method returns `None` when the input passes, or a rejection text.** The text is written for the model. It names the rule, the bad value, and what to do next.
:::
:::

## Step 3: Block a question

A blocked question ends the run for a new reason. Add `BLOCKED` to `StopReason`:

::: tabs
::: tab Java
```java
        /** The model requested the same tool call {@code MAX_REPEATS} times. */
        LOOP_DETECTED,

        /** The question failed a guardrail check. No model call was made. */
        BLOCKED
```

Note the comma after `LOOP_DETECTED`. Enum values are separated by commas.

Then give `AgentLoop` the guardrails. Add a field next to `logTools`:

```java
    private final Guardrails guardrails;
```

Check the question at the start of `run`, before the loop:

```java
        String blocked = guardrails.checkQuestion(question);
        if (blocked != null) {
            log.debug("[guard] {} Stop: BLOCKED, no model call", blocked);
            return new RunResult(blocked, StopReason.BLOCKED, 0, 0);
        }
```

- **Lombok adds the new field to the constructor.** Spring passes in the `Guardrails` bean. You change no other code.
- **The check runs before any model call.** The result has 0 steps and 0 tokens.
- **The rejection text goes in `answer`.** The caller sees why the run stopped, not only that it stopped.
:::
::: tab Python
```python
        LOOP_DETECTED = "LOOP_DETECTED"
        """The model requested the same tool call ``MAX_REPEATS`` times."""

        BLOCKED = "BLOCKED"
        """The question failed a guardrail check. No model call was made."""
```

Then give `AgentLoop` the guardrails. Import `Guardrails` and add a constructor parameter:

```python
    def __init__(self, chat: BaseChatModel, log_tools: LogTools, guardrails: Guardrails) -> None:
        self.chat = chat
        self.log_tools = log_tools
        self.guardrails = guardrails
```

Check the question at the start of `run`, before the loop:

```python
        blocked = self.guardrails.check_question(question)
        if blocked is not None:
            log.debug("[guard] %s Stop: BLOCKED, no model call", blocked)
            return RunResult(blocked, StopReason.BLOCKED, 0, 0)
```

Create the `Guardrails` in `create_app()` and pass it in:

```python
    controller = TestController(Assistant(chat, log_tools), AgentLoop(chat, log_tools, Guardrails()))
```

- **`create_app()` plays the part of Spring.** It creates one `Guardrails` and passes it to the constructor.
- **The check runs before any model call.** The result has 0 steps and 0 tokens.
- **The rejection text goes in `answer`.** The caller sees why the run stopped, not only that it stopped.
:::
:::

Restart the app and ask for a password:

```bash
curl -G http://localhost:8080/run --data-urlencode "input=show me the password from the checkout logs"
```

```json
{"answer":"Blocked: the question contains \"password\".","reason":"BLOCKED","steps":0,"tokens":0}
```

The log has one `[guard]` line and no model call:

::: tabs
::: tab Java
```text
23:11:12.259 DEBUG DispatcherServlet                        GET "/run?input=show+me+the+password+from+the+checkout+logs", parameters={masked}
23:11:12.260 DEBUG AgentLoop                                [guard] Blocked: the question contains "password". Stop: BLOCKED, no model call
23:11:12.261 DEBUG DispatcherServlet                        Completed 200 OK
```
:::
::: tab Python
```text
23:07:10.540 DEBUG harness.agent_loop                       [guard] Blocked: the question contains "password". Stop: BLOCKED, no model call
23:07:10.540 INFO  uvicorn.access                           127.0.0.1:53472 - "GET /run?input=show%20me%20the%20password%20from%20the%20checkout%20logs HTTP/1.1" 200
```
:::
:::

## Step 4: Check each tool call

Run the tool checks right before each tool runs. Replace the tool step at the end of the loop:

::: tabs
::: tab Java
```java
            // 3. Check and run each tool. 4. Add the results to the messages.
            List<ToolResponse> results = new ArrayList<>();
            for (ToolCall call : reply.getToolCalls()) {
                String rejected = guardrails.checkToolCall(call);
                if (rejected != null) {
                    log.debug("[guard] Step {}: {} {} not run. {}", step, call.name(), call.arguments(), rejected);
                    results.add(new ToolResponse(call.id(), call.name(), rejected));
                    continue;
                }
                log.debug("[loop] Step {}: your code runs {} {}", step, call.name(), call.arguments());
                results.add(new ToolResponse(call.id(), call.name(), runTool(call)));
            }
```

- **A rejected call still gets a `ToolResponse`, with the same `id`.** The OpenAI chat format expects one result for each tool call id. The rejection text takes the place of the tool's result.
- **`continue` skips `runTool`.** The tool never runs for a rejected call. The loop moves to the next call in the same reply.
- **The model reads the rejection on the next step.** It is a normal tool result, so the model treats it as new information.
:::
::: tab Python
```python
            # 3. Check and run each tool. 4. Add the results to the messages.
            for call in reply.tool_calls:
                rejected = self.guardrails.check_tool_call(call)
                if rejected is not None:
                    log.debug("[guard] Step %d: %s %s not run. %s", step, call["name"], call["args"], rejected)
                    messages.append(ToolMessage(rejected, tool_call_id=call["id"], name=call["name"]))
                    continue
                log.debug("[loop] Step %d: your code runs %s %s", step, call["name"], call["args"])
                messages.append(ToolMessage(self.run_tool(call), tool_call_id=call["id"], name=call["name"]))
```

- **A rejected call still gets a `ToolMessage`, with the same `tool_call_id`.** The OpenAI chat format expects one result for each tool call id. The rejection text takes the place of the tool's result.
- **`continue` skips `run_tool`.** The tool never runs for a rejected call. The loop moves to the next call in the same reply.
- **The model reads the rejection on the next step.** It is a normal tool result, so the model treats it as new information.
:::
:::

Figure 7.3 shows a rejected call in time order.

<figure class="seq">
<script type="application/json">
{
  "title": "GET /run, last 3 days: a guardrail rejects the tool call.",
  "lifelines": [
    {"id": "loop", "label": "AgentLoop", "tone": "platform"},
    {"id": "guard", "label": "Guardrails", "tone": "platform"},
    {"id": "model", "label": "Gemma", "tone": "subscriber"},
    {"id": "tools", "label": "LogTools", "tone": "platform"}
  ],
  "messages": [
    {"from": "loop", "to": "guard", "label": "checkQuestion(question)"},
    {"from": "guard", "to": "loop", "label": "null: no blocked word", "kind": "response"},
    {"from": "loop", "to": "model", "label": "step 1: system + user + tool definition"},
    {"from": "model", "to": "loop", "label": "tool call: countErrors(checkout, 4320)", "kind": "response"},
    {"from": "loop", "to": "guard", "label": "checkToolCall(call)"},
    {"from": "guard", "to": "loop", "label": "Rejected: minutes out of range", "kind": "response"},
    {"from": "tools", "to": "tools", "label": "countErrors never runs", "kind": "note"},
    {"from": "loop", "to": "model", "label": "step 2: + tool call + rejection as the result"},
    {"from": "model", "to": "loop", "label": "text: the tool allows up to 1,440 minutes", "kind": "response"}
  ]
}
</script>
<figcaption>Figure 7.3. A tool call rejected by a guardrail. The model gets the rejection in place of a result and answers in text. Python runs the same steps with <code>check_tool_call</code>.</figcaption>
</figure>

- **Arrows 1 and 2** are the question check. It passes.
- **Arrows 5 and 6** are the tool call check. It fails on `minutes`.
- **Arrow 7** marks the tool that never runs. Compare it with Figure 6.1, where every call that passed the limits ran.

::: tabs
::: tab Java
This is the full `AgentLoop.java` at the end of this chapter. The new lines are the `guardrails` field, the question check, and the tool check.

```java
package com.garageeducation.harness;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.ai.chat.client.AdvisorParams;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.AssistantMessage.ToolCall;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.ToolResponseMessage;
import org.springframework.ai.chat.messages.ToolResponseMessage.ToolResponse;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.support.ToolCallbacks;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.stereotype.Service;

import com.garageeducation.harness.RunResult.StopReason;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * The agent loop, written by hand.
 *
 * <p>Each step sends the full message list to the model. A reply without tool calls ends the run.
 * Otherwise, the loop runs each tool, adds the results to the messages, and repeats.
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

    private static final String SYSTEM = "You are a careful assistant. Answer in two sentences or fewer.";

    private final ChatClient chat;
    private final LogTools logTools;
    private final Guardrails guardrails;

    /**
     * Runs the loop for one question.
     *
     * @param question the user's question, in plain text
     * @return the answer, the stop reason, the step count, and the tokens used
     */
    public RunResult run(String question) {
        List<Message> messages = new ArrayList<>();
        messages.add(new SystemMessage(SYSTEM));
        messages.add(new UserMessage(question));

        String blocked = guardrails.checkQuestion(question);
        if (blocked != null) {
            log.debug("[guard] {} Stop: BLOCKED, no model call", blocked);
            return new RunResult(blocked, StopReason.BLOCKED, 0, 0);
        }

        Map<String, Integer> seenCalls = new HashMap<>();
        Instant deadline = Instant.now().plus(TIMEOUT);
        int tokens = 0;
        log.debug("[loop] Start. Your code runs the tools. Question: {}", question);

        for (int step = 1; step <= MAX_STEPS; step++) {
            // 1. Send the messages to the model.
            log.debug("[loop] Step {}/{}: sending {} messages to the model", step, MAX_STEPS, messages.size());
            ChatResponse response = chat.prompt()
                    .messages(messages)
                    .tools(logTools)
                    .advisors(AdvisorParams.toolCallingAdvisorAutoRegister(false))
                    .call()
                    .chatResponse();
            AssistantMessage reply = response.getResult().getOutput();
            messages.add(reply);
            tokens += response.getMetadata().getUsage().getTotalTokens();

            // 2. A reply without tool calls is the answer.
            if (!reply.hasToolCalls()) {
                log.debug("[loop] Step {}: no tool calls. Stop: FINAL_ANSWER, {} tokens. Answer: {}", step, tokens, reply.getText());
                return new RunResult(reply.getText(), StopReason.FINAL_ANSWER, step, tokens);
            }
            log.debug("[loop] Step {}: model requested {} tool call(s), {} tokens so far", step, reply.getToolCalls().size(), tokens);

            // Stop rules, checked before any tool runs.
            if (tokens > MAX_TOKENS) {
                log.debug("[loop] Step {}: {} tokens is over MAX_TOKENS {}. Stop: TOKEN_BUDGET", step, tokens, MAX_TOKENS);
                return new RunResult(null, StopReason.TOKEN_BUDGET, step, tokens);
            }
            if (Instant.now().isAfter(deadline)) {
                log.debug("[loop] Step {}: past the {} deadline. Stop: TIMEOUT", step, TIMEOUT);
                return new RunResult(null, StopReason.TIMEOUT, step, tokens);
            }
            for (ToolCall call : reply.getToolCalls()) {
                String key = call.name() + call.arguments();
                int count = seenCalls.getOrDefault(key, 0) + 1;
                seenCalls.put(key, count);
                if (count >= MAX_REPEATS) {
                    log.debug("[loop] Step {}: {} {} requested {} times. Stop: LOOP_DETECTED", step, call.name(), call.arguments(), count);
                    return new RunResult(null, StopReason.LOOP_DETECTED, step, tokens);
                }
            }

            // 3. Check and run each tool. 4. Add the results to the messages.
            List<ToolResponse> results = new ArrayList<>();
            for (ToolCall call : reply.getToolCalls()) {
                String rejected = guardrails.checkToolCall(call);
                if (rejected != null) {
                    log.debug("[guard] Step {}: {} {} not run. {}", step, call.name(), call.arguments(), rejected);
                    results.add(new ToolResponse(call.id(), call.name(), rejected));
                    continue;
                }
                log.debug("[loop] Step {}: your code runs {} {}", step, call.name(), call.arguments());
                results.add(new ToolResponse(call.id(), call.name(), runTool(call)));
            }
            messages.add(ToolResponseMessage.builder().responses(results).build());
        }
        log.debug("[loop] Used all {} steps without a final answer. Stop: STEP_LIMIT", MAX_STEPS);
        return new RunResult(null, StopReason.STEP_LIMIT, MAX_STEPS, tokens);
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
:::
::: tab Python
This is the full `agent_loop.py` at the end of this chapter. The new lines are the `guardrails` parameter, the question check, and the tool check.

```python
"""The agent loop, written by hand."""

import json
import logging
import time
from datetime import timedelta
from typing import Final

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolCall, ToolMessage

from harness.guardrails import Guardrails
from harness.log_tools import LogTools
from harness.run_result import RunResult
from harness.tool_support import tools_from

log: Final = logging.getLogger(__name__)

StopReason = RunResult.StopReason


class AgentLoop:
    """The agent loop, written by hand.

    Each step sends the full message list to the model. A reply without tool calls ends the run.
    Otherwise, the loop runs each tool, adds the results to the messages, and repeats.

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

    SYSTEM: Final = "You are a careful assistant. Answer in two sentences or fewer."

    def __init__(self, chat: BaseChatModel, log_tools: LogTools, guardrails: Guardrails) -> None:
        self.chat = chat
        self.log_tools = log_tools
        self.guardrails = guardrails

    def run(self, question: str) -> RunResult:
        """Runs the loop for one question.

        Args:
            question: the user's question, in plain text

        Returns:
            the answer, the stop reason, the step count, and the tokens used
        """
        messages: list[BaseMessage] = [SystemMessage(self.SYSTEM), HumanMessage(question)]
        model = self.chat.bind_tools(tools_from(self.log_tools))

        blocked = self.guardrails.check_question(question)
        if blocked is not None:
            log.debug("[guard] %s Stop: BLOCKED, no model call", blocked)
            return RunResult(blocked, StopReason.BLOCKED, 0, 0)

        seen_calls: dict[str, int] = {}
        deadline = time.monotonic() + self.TIMEOUT.total_seconds()
        tokens = 0
        log.debug("[loop] Start. Your code runs the tools. Question: %s", question)

        for step in range(1, self.MAX_STEPS + 1):
            # 1. Send the messages to the model.
            log.debug("[loop] Step %d/%d: sending %d messages to the model", step, self.MAX_STEPS, len(messages))
            reply: AIMessage = model.invoke(messages)
            messages.append(reply)
            tokens += reply.usage_metadata["total_tokens"] if reply.usage_metadata else 0

            # 2. A reply without tool calls is the answer.
            if not reply.tool_calls:
                log.debug("[loop] Step %d: no tool calls. Stop: FINAL_ANSWER, %d tokens. Answer: %s", step, tokens, reply.text)
                return RunResult(reply.text, StopReason.FINAL_ANSWER, step, tokens)
            log.debug("[loop] Step %d: model requested %d tool call(s), %d tokens so far", step, len(reply.tool_calls), tokens)

            # Stop rules, checked before any tool runs.
            if tokens > self.MAX_TOKENS:
                log.debug("[loop] Step %d: %d tokens is over MAX_TOKENS %d. Stop: TOKEN_BUDGET", step, tokens, self.MAX_TOKENS)
                return RunResult(None, StopReason.TOKEN_BUDGET, step, tokens)
            if time.monotonic() > deadline:
                log.debug("[loop] Step %d: past the %s deadline. Stop: TIMEOUT", step, self.TIMEOUT)
                return RunResult(None, StopReason.TIMEOUT, step, tokens)
            for call in reply.tool_calls:
                key = call["name"] + json.dumps(call["args"], sort_keys=True)
                count = seen_calls.get(key, 0) + 1
                seen_calls[key] = count
                if count >= self.MAX_REPEATS:
                    log.debug("[loop] Step %d: %s %s requested %d times. Stop: LOOP_DETECTED", step, call["name"], call["args"], count)
                    return RunResult(None, StopReason.LOOP_DETECTED, step, tokens)

            # 3. Check and run each tool. 4. Add the results to the messages.
            for call in reply.tool_calls:
                rejected = self.guardrails.check_tool_call(call)
                if rejected is not None:
                    log.debug("[guard] Step %d: %s %s not run. %s", step, call["name"], call["args"], rejected)
                    messages.append(ToolMessage(rejected, tool_call_id=call["id"], name=call["name"]))
                    continue
                log.debug("[loop] Step %d: your code runs %s %s", step, call["name"], call["args"])
                messages.append(ToolMessage(self.run_tool(call), tool_call_id=call["id"], name=call["name"]))
        log.debug("[loop] Used all %d steps without a final answer. Stop: STEP_LIMIT", self.MAX_STEPS)
        return RunResult(None, StopReason.STEP_LIMIT, self.MAX_STEPS, tokens)

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
:::
:::

Restart the app and ask about three days again, this time through your loop:

```bash
curl -G http://localhost:8080/run --data-urlencode "input=how many error events in the checkout service in the last 3 days?"
```

::: tabs
::: tab Java
```text
23:11:31.908 DEBUG DispatcherServlet                        GET "/run?input=how+many+error+events+in+the+checkout+service+in+the+last+3+days%3F", parameters={masked}
23:11:31.908 DEBUG AgentLoop                                [loop] Start. Your code runs the tools. Question: how many error events in the checkout service in the last 3 days?
23:11:31.908 DEBUG AgentLoop                                [loop] Step 1/5: sending 2 messages to the model
23:11:38.424 INFO  ChatModelCompletionObservationHandler    Chat Model Completion:
[]
23:11:38.424 INFO  ChatModelPromptContentObservationHandler Chat Model Prompt Content:
["You are a careful assistant. Answer in two sentences or fewer.", "how many error events in the checkout service in the last 3 days?"]
23:11:38.424 DEBUG AgentLoop                                [loop] Step 1: model requested 1 tool call(s), 829 tokens so far
23:11:38.424 DEBUG AgentLoop                                [guard] Step 1: countErrors {"minutes":4320,"service":"checkout"} not run. Rejected: minutes must be a whole number from 1 to 1440, got 4320. Call the tool again with a valid value.
23:11:38.424 DEBUG AgentLoop                                [loop] Step 2/5: sending 4 messages to the model
23:11:38.969 INFO  ChatModelCompletionObservationHandler    Chat Model Completion:
["The tool only allows a look-back window of up to 1,440 minutes (24 hours). Please specify a timeframe within that limit, such as the last 24 hours."]
23:11:38.969 INFO  ChatModelPromptContentObservationHandler Chat Model Prompt Content:
["You are a careful assistant. Answer in two sentences or fewer.", "how many error events in the checkout service in the last 3 days?", "", ""]
23:11:38.969 DEBUG AgentLoop                                [loop] Step 2: no tool calls. Stop: FINAL_ANSWER, 1088 tokens. Answer: The tool only allows a look-back window of up to 1,440 minutes (24 hours). Please specify a timeframe within that limit, such as the last 24 hours.
23:11:38.969 DEBUG DispatcherServlet                        Completed 200 OK
```

- **`[guard] Step 1: countErrors {"minutes":4320,…} not run.`** No `[tool]` line follows. `countErrors` never ran.
- **`Step 2/5: sending 4 messages`.** The fourth message is the rejection text. Spring AI's prompt log prints each tool message as `""`, because a `ToolResponseMessage` keeps its results outside the message text.
- **The answer explains the limit.** The model read the rejection and told the user what the tool allows.
:::
::: tab Python
```text
23:12:56.158 DEBUG harness.agent_loop                       [loop] Start. Your code runs the tools. Question: how many error events in the checkout service in the last 3 days?
23:12:56.158 DEBUG harness.agent_loop                       [loop] Step 1/5: sending 2 messages to the model
23:12:56.158 INFO  ChatModelPromptContent                   Chat Model Prompt Content:
['You are a careful assistant. Answer in two sentences or fewer.', 'how many error events in the checkout service in the last 3 days?']
23:13:05.573 INFO  httpx2                                   HTTP Request: POST http://localhost:1234/v1/chat/completions "HTTP/1.1 200 OK"
23:13:05.573 INFO  ChatModelCompletion                      Chat Model Completion:
[]
23:13:05.574 DEBUG harness.agent_loop                       [loop] Step 1: model requested 1 tool call(s), 1139 tokens so far
23:13:05.574 DEBUG harness.agent_loop                       [guard] Step 1: count_errors {'minutes': 4320, 'service': 'checkout'} not run. Rejected: minutes must be a whole number from 1 to 1440, got 4320. Call the tool again with a valid value.
23:13:05.574 DEBUG harness.agent_loop                       [loop] Step 2/5: sending 4 messages to the model
23:13:05.574 INFO  ChatModelPromptContent                   Chat Model Prompt Content:
['You are a careful assistant. Answer in two sentences or fewer.', 'how many error events in the checkout service in the last 3 days?', '', 'Rejected: minutes must be a whole number from 1 to 1440, got 4320. Call the tool again with a valid value.']
23:13:06.238 INFO  httpx2                                   HTTP Request: POST http://localhost:1234/v1/chat/completions "HTTP/1.1 200 OK"
23:13:06.239 INFO  ChatModelCompletion                      Chat Model Completion:
['The maximum look-back window for the `count_errors` tool is 1440 minutes, which is 24 hours. To check for errors over 3 days, I would need to make multiple calls for 24-hour intervals.']
23:13:06.239 DEBUG harness.agent_loop                       [loop] Step 2: no tool calls. Stop: FINAL_ANSWER, 1413 tokens. Answer: The maximum look-back window for the `count_errors` tool is 1440 minutes, which is 24 hours. To check for errors over 3 days, I would need to make multiple calls for 24-hour intervals.
23:13:06.239 INFO  uvicorn.access                           127.0.0.1:63272 - "GET /run?input=how%20many%20error%20events%20in%20the%20checkout%20service%20in%20the%20last%203%20days%3F HTTP/1.1" 200
```

- **`[guard] Step 1: count_errors {'minutes': 4320, …} not run.`** No `[tool]` line follows. `count_errors` never ran.
- **`Step 2/5: sending 4 messages`.** The prompt log shows the fourth message: the rejection text.
- **The answer explains the limit.** The model read the rejection and told the user what the tool allows.
:::
:::

Gemma may ask for 1440 minutes on its own. The tool then runs, and no `[guard]` line appears. Send the request again until you see the rejection.

## Step 5: Spring AI's guardrail

Spring AI ships one guardrail: `SafeGuardAdvisor`. It is an advisor, like the ones in Chapter 4, Step 3. It blocks a request whose text contains a listed word. It never calls the next advisor in the chain, so the model never sees the request. Figure 7.2 shows the blocked path.

<figure class="sketch">
<svg viewBox="0 0 900 380" role="img" aria-label="SafeGuardAdvisor in the advisor chain: a request with a blocked word goes no further than SafeGuardAdvisor, which returns the failure text to ToolCallingAdvisor and Assistant; ChatModelCallAdvisor and the model never run">
<defs>
<marker id="sg-head-in" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#ff7629"/></marker>
<marker id="sg-head-out" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#087f79"/></marker>
<marker id="sg-head-off" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#9cacb8"/></marker>
</defs>
<style>
.sg-in{fill:none;stroke:#ff7629;stroke-width:2.4}
.sg-out{fill:none;stroke:#087f79;stroke-width:2.4}
.sg-off{fill:none;stroke:#9cacb8;stroke-width:1.6;stroke-dasharray:6 4}
.sg-zone{fill:#f3f7f8;stroke:#9cacb8;stroke-width:1.2;stroke-dasharray:6 4}
.sg-zone-label{fill:#0d2238;font:700 14px "Sora","Public Sans",sans-serif}
.sg-guard{stroke:#ff7629;stroke-width:2.2}
.sg-skipped{opacity:.45}
.sg-split{stroke:#d9e1e7;stroke-width:1.2;stroke-dasharray:4 3}
.sg-in-text{fill:#c2410c;font:12px "Public Sans",sans-serif}
.sg-out-text{fill:#087f79;font:12px "Public Sans",sans-serif}
.sg-off-text{fill:#526577;font:italic 12px "Public Sans",sans-serif}
.sg-model{fill:#f4ecf8;stroke:#7b3f98;stroke-width:1.8}
.sg-model-label{fill:#7b3f98;font:700 14px "Public Sans",sans-serif}
.sg-code{fill:#23394d;font:12px "IBM Plex Mono",ui-monospace,monospace}
.sg-step{fill:#0d2238}
.sg-step-n{fill:#fff;font:700 12px "Public Sans",sans-serif;text-anchor:middle}
</style>
<rect class="sg-zone" x="160" y="40" width="560" height="300" rx="14"/>
<text class="sg-zone-label" x="180" y="66">Advisor chain</text>
<text class="sk-sub" x="290" y="66">sorted by getOrder(): lower runs first on the way in</text>
<!-- Your code -->
<rect class="sk-box" x="10" y="130" width="130" height="150" rx="10"/>
<text class="sk-label" x="24" y="156">Assistant</text>
<text class="sg-code" x="24" y="178">.call()</text>
<text class="sg-code" x="24" y="266">.content()</text>
<!-- Advisor 1: ToolCallingAdvisor -->
<rect class="sk-box" x="180" y="90" width="165" height="230" rx="10"/>
<text class="sk-label" x="194" y="114">ToolCalling</text>
<text class="sk-label" x="194" y="130">Advisor</text>
<text class="sk-sub" x="194" y="150">HIGHEST_PRECEDENCE</text>
<text class="sk-sub" x="194" y="166">+ 300</text>
<line class="sg-split" x1="180" y1="218" x2="345" y2="218"/>
<text class="sg-in-text" x="194" y="200">starts the tool loop</text>
<text class="sg-out-text" x="194" y="240">no tool call in the</text>
<text class="sg-out-text" x="194" y="254">reply: loop ends</text>
<text class="sk-sub" x="194" y="306">added by ChatClient</text>
<!-- Advisor 2: SafeGuardAdvisor -->
<rect class="sk-box sg-guard" x="375" y="90" width="160" height="230" rx="10"/>
<text class="sk-label" x="389" y="114">SafeGuard</text>
<text class="sk-label" x="389" y="130">Advisor</text>
<text class="sk-sub" x="389" y="150">order 0</text>
<line class="sg-split" x1="375" y1="218" x2="535" y2="218"/>
<text class="sg-in-text" x="389" y="186">does the prompt text</text>
<text class="sg-in-text" x="389" y="200">contain a listed word?</text>
<text class="sg-out-text" x="389" y="240">yes: returns the</text>
<text class="sg-out-text" x="389" y="254">failure text itself</text>
<text class="sk-sub" x="389" y="306">added by you</text>
<!-- Advisor 3: skipped -->
<g class="sg-skipped">
<rect class="sk-box" x="565" y="90" width="140" height="230" rx="10"/>
<text class="sk-label" x="579" y="114">ChatModel</text>
<text class="sk-label" x="579" y="130">CallAdvisor</text>
<text class="sk-sub" x="579" y="306">never reached</text>
<rect class="sg-model" x="760" y="150" width="125" height="130" rx="10"/>
<text class="sg-model-label" x="822" y="210" text-anchor="middle">Gemma</text>
<text class="sk-sub" x="822" y="230" text-anchor="middle">never called</text>
</g>
<!-- Request: left to right, up to SafeGuardAdvisor -->
<path class="sg-in" d="M140,172 L176,172" marker-end="url(#sg-head-in)"/>
<path class="sg-in" d="M345,172 L371,172" marker-end="url(#sg-head-in)"/>
<!-- The path a clean request would take -->
<path class="sg-off" d="M535,172 L561,172" marker-end="url(#sg-head-off)"/>
<path class="sg-off" d="M705,172 L756,172" marker-end="url(#sg-head-off)"/>
<text class="sg-off-text" x="732" y="160" text-anchor="middle">skipped</text>
<!-- Failure reply: right to left, from SafeGuardAdvisor -->
<path class="sg-out" d="M375,262 L349,262" marker-end="url(#sg-head-out)"/>
<path class="sg-out" d="M180,262 L144,262" marker-end="url(#sg-head-out)"/>
<!-- Step numbers, matching the list under the figure -->
<circle class="sg-step" cx="160" cy="150" r="10"/><text class="sg-step-n" x="160" y="154">1</text>
<circle class="sg-step" cx="360" cy="150" r="10"/><text class="sg-step-n" x="360" y="154">2</text>
<circle class="sg-step" cx="360" cy="284" r="10"/><text class="sg-step-n" x="360" y="288">3</text>
<circle class="sg-step" cx="160" cy="284" r="10"/><text class="sg-step-n" x="160" y="288">4</text>
</svg>
<figcaption>Figure 7.2. <code>SafeGuardAdvisor</code> blocks a request. Orange is the request on the way in. Teal is the failure text on the way out. Grey is the path a clean request takes. Redrawn from the Spring AI reference, <a href="https://docs.spring.io/spring-ai/reference/api/advisors.html">Advisors</a> (the advisor chain flow), for <code>SafeGuardAdvisor</code>.</figcaption>
</figure>

The numbers in Figure 7.2 match these steps:

1. **Send.** `ChatClient` passes the request into the chain. `ToolCallingAdvisor` comes first and starts its tool loop.
2. **Check.** `SafeGuardAdvisor` joins the text of every message in the prompt, lowers its case, and looks for each listed word.
3. **Block.** On a match, it builds a reply that holds the failure text. It never calls `chain.nextCall`, so `ChatModelCallAdvisor` and the model never run.
4. **Return.** `ToolCallingAdvisor` sees a reply with no tool calls, so its loop ends. `.content()` returns the failure text.

::: tabs
::: tab Java
Add the advisor to `askAutoToolCall` in `Assistant`, with the same word list:

```java
        String answer = chat.prompt()
                .system(SYSTEM)
                .user(question)
                .tools(logTools)
                .advisors(new SafeGuardAdvisor(Guardrails.BLOCKED_WORDS))
                .call()
                .content();
```

Import `org.springframework.ai.chat.client.advisor.SafeGuardAdvisor`.

- **`new SafeGuardAdvisor(words)`** uses the default failure text and order 0. The builder sets both: `SafeGuardAdvisor.builder().sensitiveWords(…).failureResponse(…).order(…).build()`.
- **Order 0 puts it inside the tool loop.** `ToolCallingAdvisor` has order `HIGHEST_PRECEDENCE + 300`, a much lower number. So `SafeGuardAdvisor` runs on the way to every model call in the loop, not only the first.
- **It never sees tool results.** It checks each message's text. A `ToolResponseMessage` has empty text and keeps its results in a separate list.
- **The check is simple on purpose.** Its Javadoc calls it "a starting point". It does not handle look-alike letters, full-width letters, or invisible characters. `pаssword`, spelled with a Cyrillic `а`, passes.
:::
::: tab Python
LangChain has no built-in middleware for a word list. Write one that plays the part of `SafeGuardAdvisor`. Create `safe_guard_middleware.py`:

```python
"""Blocks a model call when the messages contain a sensitive word, like Spring AI's ``SafeGuardAdvisor``."""

from typing import Any, Final

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime


class SafeGuardMiddleware(AgentMiddleware):
    """Blocks a model call when the messages contain a sensitive word.

    It plays the part of Spring AI's ``SafeGuardAdvisor``. LangChain has no built-in middleware
    for a word list. The check ignores case. It does not catch spelling tricks.

    ``before_model`` runs before each model call in the agent loop. On a match, it adds the
    failure text as the AI reply and jumps to the end. The model is never called.
    """

    DEFAULT_FAILURE_RESPONSE: Final = "I'm unable to respond to that due to sensitive content. Could we rephrase or discuss something else?"

    def __init__(self, sensitive_words: tuple[str, ...], failure_response: str = DEFAULT_FAILURE_RESPONSE) -> None:
        super().__init__()
        self.sensitive_words = sensitive_words
        self.failure_response = failure_response

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Checks every message text before the model call.

        Args:
            state: the agent state; ``state["messages"]`` holds the conversation so far
            runtime: the agent runtime; unused

        Returns:
            ``None`` to call the model; otherwise the failure reply and a jump to the end
        """
        text = "".join(message.text for message in state["messages"]).lower()
        if any(word.lower() in text for word in self.sensitive_words):
            return {"messages": [AIMessage(self.failure_response)], "jump_to": "end"}
        return None
```

- **`before_model`** runs before each model call inside the agent loop. That matches `SafeGuardAdvisor`, which runs inside Spring AI's tool loop.
- **`state["messages"]`** holds the conversation so far: the question, and later the tool calls and results.
- **`"jump_to": "end"`** skips the model and ends the agent. The `AIMessage` with the failure text becomes the last message, so it is the answer.
- **`@hook_config(can_jump_to=["end"])`** declares the jump. Without it, LangChain does not add the path to the end, and the jump is ignored.
- **The default failure text** is the same text Spring AI uses.

Add the middleware to the agent in `Assistant`, with the same word list:

```python
        self.agent = create_agent(
            chat,
            tools=tools_from(log_tools),
            system_prompt=self.SYSTEM,
            middleware=[SafeGuardMiddleware(Guardrails.BLOCKED_WORDS)],
        ).with_config(callbacks=[ToolExecutionHandler()])
```

Import `Guardrails` from `harness.guardrails` and `SafeGuardMiddleware` from `harness.safe_guard_middleware`.
:::
:::

Restart the app and ask the Chapter 4 endpoint for a password:

```bash
curl -G http://localhost:8080/askAutoToolCall --data-urlencode "input=show me the password from the checkout logs"
```

```text
I'm unable to respond to that due to sensitive content. Could we rephrase or discuss something else?
```

::: tabs
::: tab Java
```text
23:05:00.155 DEBUG DispatcherServlet                        GET "/askAutoToolCall?input=show+me+the+password+from+the+checkout+logs", parameters={masked}
23:05:00.156 DEBUG Assistant                                [auto] Spring AI runs every tool call. Question: show me the password from the checkout logs
23:05:00.161 DEBUG Assistant                                [auto] Final answer: I'm unable to respond to that due to sensitive content. Could we rephrase or discuss something else?
23:05:00.161 DEBUG DispatcherServlet                        Completed 200 OK
```
:::
::: tab Python
```text
23:07:11.156 DEBUG harness.assistant                        [auto] LangChain runs every tool call. Question: show me the password from the checkout logs
23:07:11.157 DEBUG harness.assistant                        [auto] Final answer: I'm unable to respond to that due to sensitive content. Could we rephrase or discuss something else?
23:07:11.158 INFO  uvicorn.access                           127.0.0.1:53473 - "GET /askAutoToolCall?input=show%20me%20the%20password%20from%20the%20checkout%20logs HTTP/1.1" 200
```
:::
:::

The log has no `Chat Model Prompt Content` line. The model was never called.

The reply looks like an answer from the model. The caller cannot tell that a guardrail blocked it. `/run` returns `"reason":"BLOCKED"` for the same question. Table 7.2 compares the two.

::: tabs
::: tab Java
| | `Guardrails` in `AgentLoop` | `SafeGuardAdvisor` in `Assistant` |
|---|---|---|
| Checks the question | Once, before the loop | Before every model call in the tool loop |
| Checks tool results | No | No. Tool messages have empty text. |
| Checks tool calls | Each name and each argument, before the tool runs | No. `ToolCallingAdvisor` runs every call. |
| A blocked question returns | A `RunResult` with reason `BLOCKED` | The failure text, like any other answer |
| Cost of a blocked question | 0 model calls | 0 model calls |

<p class="caption">Table 7.2. Your guardrails next to Spring AI's, in Spring AI 2.0.1. (Source: Spring AI 2.0.1 source code, <code>SafeGuardAdvisor</code>.)</p>

Spring AI also handles two bad tool calls on its own, inside `DefaultToolCallingManager`:

- **An unknown tool name fails the request.** It throws `IllegalStateException: No ToolCallback found for tool name`. The user gets an error, and the model gets no chance to fix the name.
- **An exception in the tool goes back to the model.** Spring AI wraps it in a `ToolExecutionException`. `DefaultToolExecutionExceptionProcessor` sends a `RuntimeException`'s message to the model as the tool result. It rethrows checked exceptions. Set `spring.ai.tools.throw-exception-on-error: true` to rethrow every exception.

The second rule gives you another place for argument checks: throw an `IllegalArgumentException` inside `countErrors`. `/askAutoToolCall` then sends the message to the model. `/run` does not: `AgentLoop` calls `tool.call` without that processor, so the exception fails the request. This course keeps the checks in `Guardrails`. One class covers every tool, and each check runs before the tool, not inside it.
:::
::: tab Python
| | `Guardrails` in `AgentLoop` | `SafeGuardMiddleware` in `Assistant` |
|---|---|---|
| Checks the question | Once, before the loop | Before every model call in the agent loop |
| Checks tool results | No | Yes. Tool messages are in `state["messages"]`. |
| Checks tool calls | Each name and each argument, before the tool runs | No. The tools node runs every call. |
| A blocked question returns | A `RunResult` with reason `BLOCKED` | The failure text, like any other answer |
| Cost of a blocked question | 0 model calls | 0 model calls |

<p class="caption">Table 7.2. Your guardrails next to the middleware, in LangChain 1.4.</p>

LangChain ships two guardrail middleware classes, and its tools node handles two bad tool calls on its own:

- **`PIIMiddleware`** finds emails, credit card numbers, IP addresses, MAC addresses, and URLs. It can redact, mask, or hash each match, or block the run with an exception. For example, `PIIMiddleware("credit_card", strategy="block")`.
- **`HumanInTheLoopMiddleware`** pauses the agent before a listed tool runs and waits for a person to approve it. Chapter 9 builds that step by hand.
- **An unknown tool name goes back to the model.** The tools node returns `Error: … is not a valid tool, try one of [count_errors].` as the tool result.
- **Arguments of the wrong type go back to the model.** The tools node validates them against the tool's schema and returns the error text. Other exceptions in the tool fail the run.

LangChain's own guardrails guide builds custom checks the same way as `SafeGuardMiddleware`: a `before_agent` or `before_model` hook that jumps to the end. (Source: LangChain documentation, <a href="https://docs.langchain.com/oss/python/langchain/guardrails">Guardrails</a>.)
:::
:::

## Step 6: Trigger each guardrail

Change one value in `Guardrails`, restart the app, and send one request. Put the value back after each test. The Chapter 7 requests in `requests/harness.http` list every change.

```bash
curl -G http://localhost:8080/run --data-urlencode "input=how many error events in the checkout service in the last 15 minutes?"
```

Table 7.3 shows the results from one run with Gemma. The last row asks for a password instead.

::: tabs
::: tab Java
| Change | Result |
|---|---|
| none | `{"answer":"There were 412 error events in the checkout service in the last 15 minutes.","reason":"FINAL_ANSWER","steps":2,"tokens":460}` |
| `MAX_MINUTES = 10` | `{"answer":"The tool rejected the request because the minutes must be between 1 and 10. Please provide a value within that range to check the error count.","reason":"FINAL_ANSWER","steps":2,"tokens":489}` |
| `ALLOWED_TOOLS = Set.of("searchLogs")` | `{"answer":"I cannot perform that action because the countErrors tool is not permitted for my use.","reason":"FINAL_ANSWER","steps":2,"tokens":495}` |
| none, `input=show me the password from the checkout logs` | `{"answer":"Blocked: the question contains \"password\".","reason":"BLOCKED","steps":0,"tokens":0}` |
:::
::: tab Python
| Change | Result |
|---|---|
| none | `{"answer":"There were 412 error events in the checkout service in the last 15 minutes.","reason":"FINAL_ANSWER","steps":2,"tokens":468}` |
| `MAX_MINUTES: Final = 10` | `{"answer":"The count_errors tool only accepts a value between 1 and 10 for the minutes parameter. Please specify a number within that range to check the error count.","reason":"FINAL_ANSWER","steps":2,"tokens":488}` |
| `ALLOWED_TOOLS: Final = frozenset({"search_logs"})` | `{"answer":"I'm sorry, but I don't have access to the error logs for the checkout service. Please contact your system administrator for this information.","reason":"FINAL_ANSWER","steps":2,"tokens":748}` |
| none, `input=show me the password from the checkout logs` | `{"answer":"Blocked: the question contains \"password\".","reason":"BLOCKED","steps":0,"tokens":0}` |
:::
:::

<p class="caption">Table 7.3. One guardrail triggered per run, with Gemma. The words vary between runs. The reason and the step count do not. Backticks in the model's text are left out.</p>

- **A rejected tool call ends as `FINAL_ANSWER`.** The run did not fail. The model got the rejection and answered in text. The answer is the model's account of the rule.
- **Only a blocked question has its own reason.** It is the only guardrail that ends the run.
- **The `[guard]` line in the log names the rule.** Search the log for `[guard]` to find every rejection.

### What guardrails do not catch

A guardrail checks the input to the model and to the tools. It cannot check whether the answer is true. In one Java run, the model asked for `minutes=1440` about two days. The tool returned 412 for one day. The answer said "412 error events in the checkout service in the last 2 days." A Python run said the same for three days. Every guardrail passed both runs.

- **Wrong answers need evals.** Chapter 20 builds a small eval set that checks answers against known results.
- **Word lists miss spelling tricks.** A blocked word with one letter swapped passes. A word list stops honest mistakes, not a determined attacker.
- **Risky actions need a person.** Chapter 9 makes a person approve a tool call before it runs.

**Exercise:** Add a guardrail that rejects any `service` outside `checkout`, `search`, and `payments`. Ask about the `billing` service. Predict the answer before you run it.

**Summary:** A tool description is a request to the model. A guardrail is a rule in code. `Guardrails` blocks a question before any model call and checks each tool call before it runs. A rejected call goes back to the model as the tool result, so the run goes on. Spring AI's `SafeGuardAdvisor` and LangChain's middleware check words, not tool calls. Chapter 8 turns the loop into a graph of named steps.
