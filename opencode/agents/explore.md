---
description: Read-only search agent for broad fan-out searches across many files, directories, or naming conventions when only the conclusion is needed, on GPT Luna. Replaces the built-in explore.
mode: subagent
model: openai/gpt-6-luna#medium
permissions:
  - action: edit
    resource: "*"
    effect: deny
---

Read `~/llmfiles/agents/Explore.md` and follow its Markdown body after the YAML frontmatter.
