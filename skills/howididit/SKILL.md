---
name: howididit
description: Write a short Slack-ready post that shows colleagues how a task in this session was done - where it ran, model and effort, the prompts verbatim, what each prompt got back, the result and one lesson. Use when the user says /howididit or asks to share how they did something with Claude.
---
# How I did it

Summarise the current session so a colleague can repeat it. Work only from this conversation: do not re-run commands or fetch anything new.

## Gather

- **Where:** the working directory the prompts ran in, and what it is (for example "meta repo, all child repos cloned").
- **Tool:** Claude Code, the session model and effort. List subagents by type with their model and effort, which come from their agent definition. Write `?` for an effort you cannot tell, so the user fills it in.
- **Took:** wall-clock time from the first prompt to the last result, rounded, and the number of prompts.
- **Prompts:** the user's messages that steered the work, verbatim. Skip acknowledgements like "yes" or "go on". Under each one, one line on what came back.
- **Tools used:** skills, CLIs, MCP connectors and subagents that did real work.

## Redact

The post goes to colleagues, so replace before printing:
- Slack links with `<slack link>`, and a DM or private channel with a description of it.
- Customer and person names, emails, tokens, and anything secret with a role or placeholder (`<customer>`, `<PO>`).
Repo names, public advisories and public docs stay.

## Format

Print it in the chat inside a fenced block, in Slack mrkdwn (`*bold*`, `•` bullets). The main post stays under about 15 lines.

Link everything that has a URL a colleague can open, as `[text](url)`: Slack renders that on paste and the draft tool accepts it. Take repo URLs from `git remote get-url origin`, converted to https. Link skills, Jira tickets, MRs, Confluence pages and docs the same way. A private Slack link stays redacted.

```
*How I did it: <task in a few words>*
*Where:* [<repo name>](<repo url>) (<what it is>)
*Tool:* Claude Code · <model> (<effort>) · <n> <subagent type> subagents (<model>, <effort>)
*Took:* ~<n> min, <n> prompts

*Prompts*
1. `<prompt verbatim>`
   → <one line: what came back>
2. `<prompt verbatim>`
   → <one line: what came back>

*What happened*
• <3 to 5 bullets: the steps that mattered, not every tool call>

*Result:* <one line>
*Lesson:* <the one non-obvious thing a colleague would get wrong>
_Written with [/howididit](https://github.com/cesdperez/llmfiles/blob/main/skills/howididit/SKILL.md)_
```

Add a second block, labelled as the thread reply, only when there is something worth it: the skills, CLIs and connectors used, what a later prompt caught that an earlier one missed, or what to do differently.

## Sharing

Stop after printing. When the user asks to share it, save it as a Slack draft in the channel or thread they name, and never send it.
