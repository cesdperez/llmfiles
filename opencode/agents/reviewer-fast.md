---
description: Read-only audit agent for findings that hinge on pattern recognition against stated rules (test health, code standards, reuse, ticket alignment, performance smells), on GPT Sol. Reports findings, never edits.
mode: subagent
model: openai/gpt-6.1-sol#medium
permissions:
  - action: edit
    resource: "*"
    effect: deny
---

Read `~/llmfiles/agents/reviewer-fast.md` and follow its Markdown body after the YAML frontmatter.
