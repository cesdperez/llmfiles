---
description: Creates GitLab merge requests using glab CLI, on GPT Terra. Use when the user wants to create an MR after implementing a feature or fix.
mode: subagent
model: openai/gpt-6.1-terra#medium
permissions:
  - action: edit
    resource: "*"
    effect: deny
---

Read `~/llmfiles/agents/gitlab.md` and follow its Markdown body after the YAML frontmatter.

Load the `glab-cli` and `plainenglish` skills with the skill tool first. That body assumes both are in your context.
