---
title: "Chapter 21: Failure drills"
sidebar_label: "21. Failure drills"
description: Break one part on purpose, record the eval score, then revert.
---

Break one part on purpose and watch the result. Remove a skill description. Return a large tool output. Remove the step cap. Loosen the fingerprint. Remove the citation check. Record the eval score before and after each drill, then revert.

| Drill | What it breaks | Built in |
| --- | --- | --- |
| Remove a skill description | Skill selection and the model's choice | [Chapter 14](../04-skills-and-agents/14-skills-as-files.html), [Chapter 15](../04-skills-and-agents/15-skill-selection.html) |
| Return a large tool output | A small parent context | [Chapter 18](../04-skills-and-agents/18-context-isolation.html) |
| Remove the step cap | The `STEP_LIMIT` stop | [Chapter 6](../02-the-loop/06-termination.html) |
| Loosen the fingerprint | Duplicate suppression and the triage cache key | [Chapter 20](20-a-small-eval-set.html), [Chapter 22](22-cost-optimization.html) |
| Remove the citation check | Cited answers | [Chapter 12](../03-memory-and-retrieval/12-hybrid-retrieval-inside-the-loop.html) |

<p class="caption"><strong>Table 21.1.</strong> Each drill undoes one earlier chapter. The middle column is a teaching guide; the eval score is the real measure.</p>

<figure class="flow">
<script type="application/json">
{
  "title": "One drill.",
  "steps": [
    {"label": "Record the eval score"},
    {"label": "Break one part"},
    {"label": "Run the eval and record the score"},
    {"label": "Revert the change", "tone": "platform"}
  ]
}
</script>
<figcaption>Figure 21.1. One drill at a time, always reverted, so each score change has one cause.</figcaption>
</figure>
