# Building an Agent Harness with Spring AI

Oct 10, 2026 · @Ahmed Hassanien

## Read the course locally

This repository holds the course source and the code it teaches. You need Python 3.8 or later. The build uses only the standard library.

```bash
python course/tools/build_site.py --serve
```

Open http://localhost:8000. Edit any file under `course/`, then refresh the browser. The site rebuilds within 1 second.

| Command | Result |
|---|---|
| `python course/tools/build_site.py` | Builds the site into `site/` |
| `python course/tools/build_site.py --serve --port 9000` | Serves on port 9000 |
| `python course/tools/sync_to_hugo.py` | Copies the course into the Garage Education website |

`site/` is build output. Git ignores it. Edit the sources instead:

| Path | Holds |
|---|---|
| `course/pages/course/<part>/*.md` | One chapter per file |
| `course/pages/course/<part>/_group.json` | The part's label, description, and color |
| `course/index.html` | The landing page |
| `course/site.json` | The site title, colors, footer, and print settings |
| `course/assets/` | The site CSS and the diagram script |
| `src/` | The Spring Boot code the chapters walk through |

### Publish

The course is published on the Garage Education website. Clone `garage-education/website`, then run:

```bash
python course/tools/sync_to_hugo.py PATH/TO/website
```

Commit the change in the website repository. Its pipeline deploys the site.

## Front matter

This book teaches Java engineers to build an agent harness with Spring AI. The running example is the Log Incident Watcher. Read the chapters in order. Each chapter adds one idea. Run the code in each chapter before you read the next one. All examples use fake data and run offline.

**Versions:** Spring Boot 4.1.1, Spring AI 2.0.1, Spring AI Session 0.6.0, Temporal 1.35.0. Use released versions only.

**Local services:** PostgreSQL 17 with VectorChord, BM25, and AGE. LM Studio with Gemma for chat and BGE-M3 for embeddings. A reranker container for bge-reranker-v2-m3. A Temporal dev server.

### Glossary

- **Model.** A large language model. It takes text in and returns text out.
- **Harness.** The code around a model. It sends requests, runs tools, keeps state, and decides when to stop.
- **Agent.** A model plus a harness plus a goal.
- **Tool.** A Java method the model can ask the harness to run.
- **Tool call.** The model's request to run a tool. It names the tool and gives arguments.
- **Loop.** The cycle of model call, tool execution, and result. It ends when the run stops.
- **Termination.** The rule that ends a run.
- **Context window.** The text the model can read in one call. It is measured in tokens.
- **Token.** A small piece of text. Providers bill by token.
- **Skill.** A file of instructions for one task. The harness loads it only when needed.
- **Sub-agent.** An agent that a parent agent calls as a tool.
- **Memory.** Information kept across model calls. Short-term memory is the recent conversation. Long-term memory is stored outside it.
- **Embedding.** A list of numbers that represents the meaning of a text.
- **Vector store.** A database that finds texts with similar embeddings.
- **BM25.** A keyword scoring method. It rewards rare words that appear often in a document.
- **Hybrid search.** Keyword search and vector search, merged into one result list.
- **RRF (Reciprocal Rank Fusion).** A way to merge ranked lists by rank position, not by score.
- **Reranker.** A model that scores a query and each candidate together, then reorders the candidates.
- **RAG (retrieval-augmented generation).** The harness fetches relevant documents before the model answers.
- **HITL (human-in-the-loop).** A run that pauses until a person approves an action.
- **Graph.** A flow of nodes and edges. A knowledge graph stores relationships between things.
- **Durable execution.** A run that survives crashes and restarts because its state is stored.
- **Workflow (Temporal).** The durable definition of one run.
- **Activity (Temporal).** A unit of work with side effects, such as a model call. Temporal retries it.
- **Signal (Temporal).** A message sent to a running workflow, such as an approval.
- **Eval.** A fixed set of test inputs with expected properties. Run it before each change.
- **Prompt caching.** The provider reuses work for a stable part of the prompt. It lowers cost.

## Part 1: Foundations

### Chapter 1: Why a harness?

A model reads text and writes text. It cannot run code, read files, or remember past calls. The harness adds those abilities. It does five jobs. It sends the prompt. It reads the reply. It runs the tools the model asks for. It returns the tool results. It decides when the run stops.

**Example.** Asked alone, a model can only guess whether checkout is slow. With a harness, the model calls a `countErrors` tool, reads the real count, and answers from that data.

**Objectives:** describe a model call, name the five harness jobs, and explain what the course builds.

### Chapter 2: Project setup

This chapter builds a Spring Boot 4.1.1 project that talks to LM Studio.

**Objectives:**

- Build the project with Gradle.
- Point Spring AI at the Gemma and BGE-M3 models in LM Studio.
- Confirm Gemma returns tool calls.

#### Step 1: The build file

The project uses Gradle with the Kotlin DSL.

```kotlin
plugins {
	java
	id("org.springframework.boot") version "4.1.1"
	id("io.spring.dependency-management") version "1.1.7"
}

group = "com.garageeducation"
version = "0.0.1-SNAPSHOT"

java {
	toolchain {
		languageVersion = JavaLanguageVersion.of(27)
	}
}

repositories {
	mavenCentral()
}

extra["springAiVersion"] = "2.0.1"

dependencies {
	implementation("org.springframework.boot:spring-boot-starter-webmvc")
	implementation("org.springframework.ai:spring-ai-starter-model-openai")
	testImplementation("org.springframework.boot:spring-boot-starter-test")
	testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

dependencyManagement {
	imports {
		mavenBom("org.springframework.ai:spring-ai-bom:${property("springAiVersion")}")
	}
}

tasks.withType<Test> {
	useJUnitPlatform()
}
```

- `spring-ai-bom` pins every Spring AI module to 2.0.1.
- `spring-boot-starter-webmvc` serves HTTP on port 8080.
- `spring-ai-starter-model-openai` creates the `ChatClient.Builder`.
- The toolchain is Java 27. Spring Boot 4.1.1 needs Java 17 or later.

`settings.gradle.kts` holds one line:

```kotlin
rootProject.name = "harness"
```

#### Step 2: The model settings

LM Studio exposes an OpenAI-compatible API (application programming interface). The OpenAI starter calls it. Put the settings in `src/main/resources/application.yaml`.

```yaml
spring:
  application:
    name: harness
  ai:
    openai:
      base-url: http://localhost:1234/v1
      api-key: lm-studio
      chat:
        model: google/gemma-4-12b-qat
      embedding:
        model: text-embedding-bge-m3
```

- `base-url` ends in `/v1`.
- LM Studio ignores the API key. The starter still needs a value.
- Each model name must match an identifier in LM Studio.

List the identifiers with this request:

```bash
curl http://localhost:1234/v1/models
```

#### Step 3: The main class

```java
package com.garageeducation.harness;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Starts the harness.
 *
 * <p>Spring Boot scans this package and creates every bean in it.
 * The OpenAI starter adds a {@code ChatClient.Builder} for LM Studio.
 *
 * <p>The {@code main} method is package-private and {@code static}.
 * Java 25 and later accept this form.
 */
@SpringBootApplication
public class HarnessApplication {

	/**
	 * Runs the Spring Boot application on port 8080.
	 *
	 * @param args command-line arguments, passed to Spring Boot
	 */
	static void main(String[] args) {
		SpringApplication.run(HarnessApplication.class, args);
	}

}
```

Start the app:

```bash
./gradlew bootRun
```

On Windows, run `gradlew.bat bootRun`.

#### Step 4: The pre-flight check

Send one request with a tool definition to Gemma. Confirm the response contains a tool call.

**Summary:** The app starts on port 8080 and reaches LM Studio. Chapter 3 sends the first question.

### Chapter 3: The model call

This chapter sends one question to Gemma and returns its text reply.

**Objectives:**

- Write the `Assistant` service.
- Expose it over HTTP with `TestController`.
- See what the model answers without tools.

#### Step 1: The Assistant

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
- Your code never builds the HTTP request.

#### Step 2: The controller

```java
package com.garageeducation.harness;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes {@link Assistant} over HTTP for manual tests.
 *
 * <p>Example: {@code GET http://localhost:8080/?input=how many error events in checkout service?}
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
    @GetMapping("/")
    public String test(@RequestParam String input) {
        return assistant.ask(input);
    }
}
```

`GET /` reads the `input` parameter and returns the model's reply.

#### Step 3: Run the first call

Restart the app. Send a question:

```bash
curl -G http://localhost:8080/ --data-urlencode "input=how many error events?"
```

The model has no data. It asks for the logs:

```text
Please provide the logs or data you are referring to. Once you share them, I can count the error events for you.
```

A request without `input` fails. The model is never called.

**Summary:** One question reaches Gemma and returns text. The model cannot read logs yet. Chapter 4 gives it a tool.

### Chapter 4: Tools

This chapter gives the model one tool to count error events.

**Objectives:**

- Write `countErrors` as a Spring AI tool.
- Attach it to the `Assistant`.
- Compare replies with and without the tool.

A tool is a Java method. The model chooses tools from their names and descriptions alone. A vague description causes wrong choices.

#### Step 1: The tool

```java
package com.garageeducation.harness;

import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

/**
 * Log tools the model can call.
 *
 * <p>The model sees only the tool name, the {@link Tool} description, and each
 * {@link ToolParam} description. It never sees the method body.
 */
@Component
public class LogTools {

    /**
     * Counts error log events for one service.
     *
     * <p>The data is fake. The {@code checkout} service returns 412. Every other service returns 3.
     *
     * @param service the service name, for example {@code checkout}
     * @param minutes the look-back window in minutes, from 1 to 1440; the fake data ignores it
     * @return the number of error events
     */
    @Tool(description = "Count error log events for one service in the last N minutes. Use this to check for a current error spike.")
    public int countErrors(@ToolParam(description = "Service name, for example checkout") String service,
                           @ToolParam(description = "Look-back window in minutes, from 1 to 1440") int minutes) {
        return "checkout".equals(service) ? 412 : 3; // fake data
    }
}
```

- `@Tool` names the method as a tool. Its description tells the model when to use it.
- `@ToolParam` describes each argument. The model fills them in.
- `@Component` makes `LogTools` a bean, so Spring can inject it.



#### Step 2: Attach the tool

Inject `LogTools` into the `Assistant`. Pass it to `.tools(logTools)` on the prompt. This is the full file in the repository:

```java
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
```

`ChatClient` runs the tool for you. It sends the result back to the model and returns the final text. Chapter 5 writes this loop by hand.

#### Step 3: Run it with the tool

Restart the app. Table 4.1 lists three questions and the replies from one run.

| Question | Reply |
|---|---|
| `how many error events?` | Please specify which service you would like to check and the time window (in minutes) for the error count. |
| `how many error events in search service?` | There were 3 error events in the search service in the last 10 minutes. |
| `how many error events in checkout service?` | There are currently 412 error events in the checkout service over the last 15 minutes. |

<p class="caption">Table 4.1. Replies from Gemma with the tool attached. Your wording will differ.</p>

- Without a service name, the model asks for one. It does not guess.
- The counts match the fake data: 412 for `checkout`, 3 for the rest.
- The model chose `minutes` itself: 10 and 15. The question gave no window.

Send the last question:

```bash
curl -G http://localhost:8080/ --data-urlencode "input=how many error events in checkout service?"
```

**Exercise:** Rename the tool, then remove its description. Compare the model's choices each time.

**Summary:** One `@Tool` method lets the model answer from data. The description decides when the model calls it.

## Part 2: The Loop

### Chapter 5: Writing the agent loop by hand

The loop has four steps. Send the messages to the model. If the reply has no tool calls, return its text. Otherwise run each tool, add the results to the messages, and repeat.

Call the `ChatModel` directly, not `ChatClient`. In Spring AI 2.0, `ChatClient` runs tools through a `ToolCallingAdvisor`. `ChatModel.call` only sends the tool definitions and returns the tool calls, so the code runs each tool itself.

```java
ToolCallingChatOptions options = ToolCallingChatOptions.builder()
        .toolCallbacks(ToolCallbacks.from(logTools))
        .build();

for (int step = 1; step <= MAX_STEPS; step++) {
    ChatResponse response = model.call(new Prompt(messages, options));
    AssistantMessage reply = response.getResult().getOutput();
    messages.add(reply);
    if (!reply.hasToolCalls()) {
        return new RunResult(reply.getText(), StopReason.FINAL_ANSWER, step);
    }
    // run each tool call, add ToolResponseMessage to messages
}
```

> **Verify:** Confirm the class names and builder methods for your Spring AI version. They change between releases.

### Chapter 6: Termination

A run ends in one of these ways: a final answer, a step limit, a token budget, a timeout, or loop detection. Every run returns a `RunResult` with the reason, so failures are easy to read.

```java
public record RunResult(String answer, StopReason reason, int steps) {
    public enum StopReason { FINAL_ANSWER, STEP_LIMIT, TOKEN_BUDGET, TIMEOUT, LOOP_DETECTED, APPROVAL_TIMEOUT, REJECTED }
}
```

### Chapter 7: Guardrails

Put guardrails in code, not in the prompt.

- **Argument checks.** Reject a `minutes` value outside 1 to 1440 before the tool runs. Return the error text to the model.
- **Allowlist.** Each agent has a fixed set of tool names. Reject any other name.
- **Loop detection.** Count each tool name plus arguments. Stop when one key repeats three times.

### Chapter 8: Graphs

A graph makes the flow explicit. Each stage is a node. Each move between stages is an edge. Keep the control flow in plain Java, so every edge has a unit test. A graph database is a different tool, used for relationships between services. Chapter 8b covers it.

### Chapter 9: Human-in-the-loop

A critical alert waits for a person. The workflow sets its state to awaiting approval and waits for an approval signal or a one-hour timer. Temporal stores the wait, so a restart does not lose it. Chapter 24 shows the code. Keep an audit row in PostgreSQL for each decision.

## Part 3: Memory and Retrieval

### Chapter 10: Short-term memory with Spring AI Session

Spring AI Session stores every message and tool call in PostgreSQL. Spring AI's JDBC chat memory drops tool call messages, so this course does not use it. The workflow id is the session id.

```java
sessions.appendMessage(sessionId, new UserMessage(question));
List<Message> history = sessions.getMessages(sessionId);
```

The full history stays in the database. The window sent to the model is a separate choice. Verify the bean name and the `create` signature in the Session README.

### Chapter 11: Embeddings and hybrid storage in PostgreSQL

Use one PostgreSQL database with VectorChord for vectors, and its BM25 extension for keywords. The table holds the text, the metadata, the embedding, and the keyword vector.

```sql
CREATE TABLE IF NOT EXISTS corpus (
    id       TEXT PRIMARY KEY,
    service  TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    source   TEXT NOT NULL,
    text     TEXT NOT NULL,
    emb      vector(1024),
    bm25     bm25vector
);
```

BGE-M3 runs in LM Studio and produces 1024-dimension vectors. Split documents into chunks of about 1200 characters with 150 overlapping. Embed each chunk, then insert it. A startup check confirms the vector size matches the table.

> **Verify:** Create the BM25 index with the statement in the VectorChord-BM25 repository. The reference article does not show it.

### Chapter 12: Hybrid retrieval inside the loop

Run two searches and merge them. The vector search returns the 20 closest chunks. The keyword search returns the 20 best BM25 matches. Reciprocal Rank Fusion merges the two lists by rank. Each chunk scores the sum of 1 divided by 60 plus its rank in each list.

Expose the merged search as a tool. Require a citation for each claim. If the answer has no citation and does not say no match, send one correction. Stop if it still has none.

### Chapter 13: Retrieval quality

Use metadata filters for service and document type. Return `NO_MATCH` when the best vector distance is above a threshold you set from the eval set. Then rerank the fused top 20 with the cross-encoder `bge-reranker-v2-m3`, served over REST, and keep the top 4.

The reference article reports that the cross-encoder was best on all four datasets it tested (Source: VectorChord blog, 2025). Test the gain on your own eval set. The reranker adds latency, so log its duration.

PostgreSQL cannot run a neural reranker. A ColBERT rerank can run in SQL, but it needs a separate token encoder service, so this course does not use it.

## Part 4: Skills and Agents

### Chapter 14: Skills as files

A skill is a folder with a `SKILL.md` file. The file has a name and a one-line description in front matter, then the full instructions. The harness loads only names and descriptions at the start. A `useSkill` tool loads the full text when the model asks for it.

```markdown
---
name: triage-error-group
description: Judge the severity of one error group from its rate, the services it affects, and whether a runbook exists.
---

# Steps
1. Read the error rate for the last 15 minutes.
2. List the affected services.
3. Search runbooks for the error fingerprint.
4. Return one severity: low, medium, or critical.
```

### Chapter 15: Skill selection

Skills are indexed by their description embedding in PostgreSQL. For each task, the harness takes the five nearest skills. Only those five appear in the prompt, and `useSkill` accepts only those names. Measure recall at five on 20 labeled tasks. Include pre-filtering only when the catalog grows past about ten skills.

### Chapter 16: Sub-agents

A sub-agent has its own system prompt, its own tool allowlist, and its own step limit. The parent calls it through a tool that returns a short summary. A focused agent does one job well.

### Chapter 17: Agent selection

Three patterns exist. A direct agent handles the task itself. A router labels the task and sends it to one agent. A supervisor plans several subtasks and combines the results. Start with direct handling. Add a router only when the cost of a wrong route is clear. Test each pattern with the eval set.

### Chapter 18: Context isolation

A sub-agent keeps its full detail in the log. It returns a capped summary with a fixed shape: a finding, a confidence, and a detail id. Set the cap in code, not in the prompt. The parent's context stays small.

## Part 5: Observability, Evaluation, and Cost

### Chapter 19: Step logging

Write one JSON line per model call and per tool call. Each line holds the run id, step number, kind, tool name, arguments, token counts, duration, and stop reason. A failure is easy to find when you search by run id.

### Chapter 20: A small eval set

An eval case has fixed input and expected properties. Check the stop reason, whether an alert posted, and required phrases. Do not check exact text, because model output varies.

Write these cases first: a duplicate that should be suppressed, a critical error that needs approval, a flood that hits the rate limit, a novel error with no runbook, and an empty window that ends with no model call.

```java
@ParameterizedTest
@ValueSource(strings = {"duplicate-suppressed", "critical-needs-approval", "flood-hits-rate-limit"})
void evalCase(String caseName) throws Exception {
    // read the case JSON, run the watcher, assert the expected properties
}
```

Run the eval before every change. Use plain JUnit 5.

### Chapter 21: Failure drills

Break one part on purpose and watch the result. Remove a skill description. Return a large tool output. Remove the step cap. Loosen the fingerprint. Remove the citation check. Record the eval score before and after each drill, then revert.

### Chapter 22: Cost optimization

Measure tokens per run first. Then add a cache with Spring Cache and Caffeine, keyed by error fingerprint, with a ten-minute expiry. Clear it when a runbook changes. Redis can replace Caffeine later with no code change.

```java
@Cacheable(cacheNames = "triage", key = "#fingerprint", unless = "#result == null")
public TriageDecision triage(String fingerprint, String stackTrace) { ... }
```

Provider prompt caching does not apply to LM Studio, so skip that step. Each step must lower the token count in the eval run. Remove any step that does not.

## Part 6: Durable Execution with Temporal

Every watcher run is a Temporal workflow. Temporal stores each step, the approval wait, and the result. A worker crash resumes the run where it stopped.

### Chapter 23: Run state and messages

Temporal workflow history holds the run state. It holds the step count, the state, the approval, and the result. Spring AI Session holds the messages and tool calls. Use the workflow id as the session id. Do not store run state in a separate table. Two stores for one run drift apart.

**Exercise.** Start a run. Kill the worker after step 2. Restart it. Confirm the run completes without repeating step 1.

### Chapter 24: Temporal basics for the watcher

| Concept | Use in the watcher |
| --- | --- |
| Workflow | One watcher run |
| Activity | One model call, one tool call, one alert post |
| Signal | Human approval |
| Timer | Approval deadline |
| Retry policy | Retry a failed model or tool call |
| Query | Read the current state |

**Determinism rule.** Workflow code must give the same result on replay. Model calls, tool calls, database writes, and REST calls go in activities. Use `Workflow.await`, `Workflow.sleep`, and `Workflow.currentTimeMillis()` in the workflow. Do not use `Thread.sleep` or `Instant.now()` there.

```java
@WorkflowInterface
public interface WatcherWorkflow {
    @WorkflowMethod RunResult run(WatchRequest request);
    @SignalMethod void decideApproval(boolean approved);
    @QueryMethod String state();
}
```

> **Verify:** Confirm the annotation packages and the starter configuration keys for SDK 1.35.0. Temporal's Spring Boot starter starts the worker automatically when the app starts.

**Exercise.** Start a run through a REST endpoint. Read its state with a query. Approve a critical run. Confirm one alert posts.

## Part 7: Capstone

### Chapter 25: Assemble the Log Incident Watcher

The capstone runs every part together. Each run is a Temporal workflow. Each model call and each tool call is an activity. Approval is a signal. Memory is Spring AI Session. Retrieval is hybrid search with a cross-encoder reranker.

Temporal's Spring AI integration does not yet support Spring AI 2.x. The integration is in public preview with Spring AI 1.1.0 listed. Upgrading it is tracked in temporalio/ai-integrations PR #40. This chapter uses plain activities that do the same job.

| Activity | Role |
| --- | --- |
| `ModelActivity` | Reads the session, calls the model, saves the reply last |
| `ToolActivity` | Checks the allowlist, runs the tool, saves the result |
| `AlertActivity` | Posts the alert, only after approval |

The workflow runs the loop. It stops on a final answer, a `submitFinding` tool call, the step limit, loop detection, an approval timeout, or a rejection. It never calls a model or a tool itself.

```java
@WorkflowImpl(workers = "watcher")
public class WatcherWorkflowImpl implements WatcherWorkflow {
    private static final int MAX_STEPS = 12;
    private static final int MAX_REPEATS = 3;
    // activity stubs for model, tools, and alerts
    // loop: model turn, then each tool call, then stop rules
}
```

**Rule to teach.** A retried activity can save its message twice if it fails after saving. Save last. Verify whether Session accepts a message id for idempotent saves.

**Switching later.** When `io.temporal:spring-ai` ships a public release, replace the model activity with its chat model class. The stop rules and approval code stay the same.

**Final exercise.** Run the full eval set. Break one drill from Chapter 21, fix it, and record the final score.

## Progress checklist

- [x] Front matter and glossary
- [x] Part 1: Foundations (chapters 1 to 4)
- [x] Part 2: The Loop (chapters 5 to 9)
- [x] Part 3: Memory and Retrieval (chapters 10 to 13)
- [x] Part 4: Skills and Agents (chapters 14 to 18)
- [x] Part 5: Observability, Evaluation, and Cost (chapters 19 to 22)
- [x] Part 6: Durable Execution with Temporal (chapters 23 and 24)
- [x] Part 7: Capstone (chapter 25)

### Open items

- [ ] Confirm class names and annotations against the pinned versions. Several chapters are marked to verify.
- [ ] Add the fake log data set and runbook files to the course repository.
- [ ] Add an answer key for each chapter exercise.
- [ ] Confirm the BM25 index statement and the probe syntax (Ch. 11, 12).
- [ ] Confirm the reranker `/rerank` request shape (Ch. 13).
- [ ] Confirm the Temporal annotation packages and starter keys (Ch. 24).
- [ ] Switch Chapter 25 to `io.temporal:spring-ai` after a public release (PR #40 is open).

## Changelog

- v0.1: Table of contents.
- v0.2: Front matter, glossary, chapters 1 to 7.
- v0.3: Chapters 8 to 25.
- v0.4: Hybrid retrieval with VectorChord (keyword and vector, merged with RRF).
- v0.5: Local BGE-M3 embeddings. Plain JUnit evals. Spring Cache with Caffeine.
- v0.6: Approvals and run state in PostgreSQL. LM Studio embeddings. Skill pre-filtering.
- v0.7: Knowledge graph in Apache AGE. Reranker over REST.
- v0.8: Spring AI Session for short-term memory. LM Studio chat with Gemma.
- v0.9: Temporal required for every run.
- v1.0: Versions pinned. Chapter 25 uses plain Temporal activities. Version policy added.
- v1.1: Consolidated into one document. Spring Boot 4.1.1, Spring AI 2.0.1, Session 0.6.0, Temporal 1.35.0.
- v1.2 (this document): Chapters 2 to 4 match the course repository. Gradle build, `application.yaml`, `TestController`, Javadoc, and recorded replies.
