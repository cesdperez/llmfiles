---
description: Read-only audit agent for findings that hinge on pattern recognition against stated rules (test health, code standards, reuse, ticket alignment, performance smells), on Claude Opus. Reports findings, never edits.
mode: subagent
model: claude-agent/opus#medium
permissions:
  - action: edit
    resource: "*"
    effect: deny
---

Read `~/llmfiles/agents/reviewer-fast.md` and follow its Markdown body after the YAML frontmatter.
