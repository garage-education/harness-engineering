# Building an Agent Harness with Spring AI

Oct 10, 2026 · @Ahmed Hassanien

This course teaches Java engineers to build an agent harness with Spring AI. The running example is the Log Incident Watcher. It has 7 parts and 25 chapters. Each chapter adds one idea. All examples use fake data and run offline.

**Versions:** Spring Boot 4.1.1, Spring AI 2.0.1, Spring AI Session 0.6.0, Temporal 1.35.0.

The chapters live in `course/pages/course/`. Start with the front matter, `00-start/01-front-matter.md`, or serve the site below.

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
| `src/` | The Spring Boot code the chapters walk through |
| `requests/harness.http` | Every test request in the course, in chapter order |

### Publish

The course is published on the Garage Education website. Clone `garage-education/website`, then run:

```bash
python course/tools/sync_to_hugo.py PATH/TO/website
```

Commit the change in the website repository. Its pipeline deploys the site.
