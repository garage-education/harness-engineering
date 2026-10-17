# Building an Agent Harness with Spring AI

Oct 10, 2026 · @Ahmed Hassanien

This course teaches Java engineers to build an agent harness with Spring AI. The running example is the Log Incident Watcher. It has 7 parts and 25 chapters. Each chapter adds one idea. All examples use fake data and run offline.

**Versions:** Spring Boot 4.1.1, Spring AI 2.0.1, Spring AI Session 0.6.0, Temporal 1.35.0.

Read the course on the [Garage Education website](https://www.garageeducation.org/docs/agent-harness-spring-ai/), or serve it locally (see below).

## Take the course

### Before you start

| You need | Check |
|---|---|
| JDK 27 | `java -version` prints 27. Gradle does not download it for you. |
| LM Studio, server on port 1234 | `curl http://localhost:1234/v1/models` lists the models below |
| Model `google/gemma-4-12b-qat` | Chat and tool calls |
| Model `text-embedding-bge-m3` | Embeddings, from Chapter 11 |
| IntelliJ IDEA, or VS Code with the REST Client extension | Opens `requests/harness.http` |

Clone the repository and start the app:

```bash
git clone git@github.com:garage-education/harness-engineering.git
cd harness-engineering/java
./gradlew bootRun
```

On Windows, run `gradlew.bat bootRun`. The app listens on port 8080.

### Each chapter, in four steps

1. **Read** the chapter. It shows the code for that chapter only.
2. **Write** the code, or compare it with `java/src/main/java/com/garageeducation/harness/`.
3. **Send** the chapter's requests in `requests/harness.http`. Each request names its chapter.
4. **Read** the console log. Each chapter shows the log lines to expect. Chapter 2, Table 2.1 explains every log tag.

Run Chapter 2's two requests first. Gemma must return a tool call before you start Chapter 3.

### What `java/` holds

`java/` holds the code after Chapter 6. It is ahead of Chapters 3 to 5. For example, `Assistant.java` already has `askHaltToolCall` from Chapter 5. Each chapter shows the version of each file for that point in the course.

Model replies differ between runs. Compare the shape of each reply and log, not the exact words.

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
| `python course/tools/sync_to_hugo.py PATH/TO/website` | Copies the course into the Garage Education website |

`site/` is build output. Git ignores it. Edit the sources instead:

| Path | Holds |
|---|---|
| `course/pages/course/<part>/*.md` | One chapter per file |
| `course/pages/course/<part>/_group.json` | The part's label, description, and color |
| `course/index.html` | The landing page |
| `course/site.json` | The site title, colors, footer, and print settings |
| `course/assets/` | The site CSS and the diagram script |
| `java/` | The Spring Boot code the chapters walk through. Open this folder in your IDE. |
| `requests/harness.http` | Every test request in the course, in chapter order |

### Publish

The course is published on the Garage Education website. Clone `garage-education/website`, then run:

```bash
python course/tools/sync_to_hugo.py PATH/TO/website
```

Commit the change in the website repository. Its pipeline deploys the site.
