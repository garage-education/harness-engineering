---
title: "Chapter 15: Skill selection"
sidebar_label: "15. Skill selection"
description: The five nearest skills by description embedding, and nothing else, reach the prompt.
---

Skills are indexed by their description embedding in PostgreSQL. For each task, the harness takes the five nearest skills. Only those five appear in the prompt, and `useSkill` accepts only those names. Measure recall at five on 20 labeled tasks. Include pre-filtering only when the catalog grows past about ten skills.

<figure class="flow">
<script type="application/json">
{
  "title": "Selecting skills for one task.",
  "steps": [
    {"label": "A task arrives"},
    {"label": "Embed the task"},
    {"label": "Take the five nearest skill descriptions from PostgreSQL"},
    {"label": "Put only those five in the prompt"},
    {"label": "Is the useSkill name one of the five?", "no": "Reject the call"},
    {"label": "Load the full SKILL.md", "tone": "platform"}
  ]
}
</script>
<figcaption>Figure 15.1. Skill selection for one task. The same five names are the prompt list and the <code>useSkill</code> allowlist. Recall at five, on 20 labeled tasks, says whether the right skill made the cut.</figcaption>
</figure>
