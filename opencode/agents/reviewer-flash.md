---
description: Read-only rule-lens reviewer for the conductor (test health, code standards, reuse, performance), on DeepSeek Flash through OpenCode Go. Reports findings, never edits. Only the conductor calls it.
mode: subagent
model: opencode-go/deepseek-v4.1-flash#high
permissions:
  - action: edit
    resource: "*"
    effect: deny
---

Read `~/llmfiles/agents/reviewer-fast.md` and follow its Markdown body after the YAML frontmatter.
