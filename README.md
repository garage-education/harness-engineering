# Building an Agent Harness with Spring AI

Oct 10, 2026 · @Ahmed Hassanien

This course teaches engineers to build an agent harness with Spring AI in Java. Chapters 2 to 8 also show every step in Python with LangChain. The running example is the Log Incident Watcher. It has 7 parts and 25 chapters. Each chapter adds one idea. All examples use fake data and run offline.

**Versions:** Spring Boot 4.1.1, Spring AI 2.0.1, Spring AI Session 0.6.0, Temporal 1.35.0.

Read the course on the [Garage Education website](https://www.garageeducation.org/docs/agent-harness-spring-ai/), or serve it locally (see below).

## Take the course

### Before you start

| You need | Check |
|---|---|
| JDK 27, for Java | `java -version` prints 27. Gradle does not download it for you. |
| uv, for Python | `uv --version`. uv downloads Python 3.14 for you. |
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

On Windows, run `gradlew.bat bootRun`.

For Python, start the app from the `python/` folder instead:

```bash
cd harness-engineering/python
uv run harness
```

Both apps listen on port 8080 and answer the same requests. Run one at a time.

### Each chapter, in four steps

1. **Read** the chapter. It shows the code for that chapter only.
2. **Write** the code, or compare it with `java/src/main/java/com/garageeducation/harness/` or `python/src/harness/`. Each chapter has a Java tab and a Python tab.
3. **Send** the chapter's requests in `requests/harness.http`. Each request names its chapter.
4. **Read** the console log. Each chapter shows the log lines to expect. Chapter 2, Table 2.1 explains every log tag.

Run Chapter 2's two requests first. Gemma must return a tool call before you start Chapter 3.

### What `java/` and `python/` hold

`java/` and `python/` hold the code after the latest chapter. The Git history has one commit for each chapter, so you can see the code at any point in the course. Each commit has a tag: `chapter-01`, `chapter-02`, and so on.

```bash
git checkout chapter-05            # the code at the end of Chapter 5
git diff chapter-04 chapter-05     # what Chapter 5 changed
git checkout main                  # back to the latest chapter
```

Chapter 1 has no code. Its commit adds only the chapter page. The first commit, before Chapter 1, sets up the course site.

Model replies differ between runs. Compare the shape of each reply and log, not the exact words.

### Run the tests

From Chapter 8, each edge of the agent loop has a unit test. The tests use a scripted model, so LM Studio does not need to run.

```bash
cd java && ./gradlew test       # Java
cd python && uv run pytest -v   # Python
```

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
| `python/` | The same app in Python, with LangChain and FastAPI |
| `requests/harness.http` | Every test request in the course, in chapter order |

### Publish

The course is published on the Garage Education website. Clone `garage-education/website`, then run:

```bash
python course/tools/sync_to_hugo.py PATH/TO/website
```

Commit the change in the website repository. Its pipeline deploys the site.
