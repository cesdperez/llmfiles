---
description: Read-only audit on GPT Sol, billed to the ChatGPT plan instead of Anthropic usage. Use for a review from a different model family, or to save Anthropic usage on an audit whose mandate stands on its own. Reports findings, never edits.
mode: subagent
model: openai/gpt-6.1-sol#high
permissions:
  - action: edit
    resource: "*"
    effect: deny
---

Read `~/llmfiles/agents/reviewer.md` and follow its Markdown body after the YAML frontmatter.
