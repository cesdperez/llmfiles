---
description: Read-only search agent for the conductor, for broad fan-out searches across many files when only the conclusion is needed, on DeepSeek Flash through OpenCode Go. Only the conductor calls it.
mode: subagent
model: opencode-go/deepseek-v4.1-flash#low
permissions:
  - action: edit
    resource: "*"
    effect: deny
---

Read `~/llmfiles/agents/Explore.md` and follow its Markdown body after the YAML frontmatter.
