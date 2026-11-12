---
description: Read-only audit agent for findings that hinge on reasoning about execution (correctness, security, cross-repo impact, verification by running tests), on Claude Opus. Reports findings, never edits.
mode: subagent
model: claude-agent/opus#high
permissions:
  - action: edit
    resource: "*"
    effect: deny
---

Read `~/llmfiles/agents/reviewer.md` and follow its Markdown body after the YAML frontmatter.
