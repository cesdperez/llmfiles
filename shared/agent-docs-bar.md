# Agent docs bar

The quality bar for files an agent reads: CLAUDE.md, AGENTS.md, rules, skills, commands, agents, and the docs they route to. Used by `/curatemds` and `/skillbuilder`.

The bar targets Opus 5.5. When a new model ships, re-read the sources at the end and update this file, because advice for one model can waste tokens on the next.

## Content

- The reader is a capable model. Cut what it can infer from the code, `--help`, `package.json` scripts, config files, or general knowledge. Keep the unwritten part: conventions, the reason behind a choice, commands that work, and traps.
- Deletion test on every sentence: if removing it would not change what the model does, delete the whole sentence.
- One owner per fact. Other files link to the owner.
- Two files that disagree make the model pick one at random. Resolve the conflict in the owner.
- Every claim is true against today's code, and every path and command it names exists.
- No dated history, migration status, personal names, handles, or personal paths. Git holds the history. A rule a past incident taught stays as a rule with its reason.

## Wording

- Calm. A rule with its reason, not `CRITICAL`, `MUST`, or capitals. Shouting makes current models overreact, and the reason lets the rule generalise.
- State the target behaviour. A positive example works better than a list of things to avoid. Keep a prohibition only as a hard guardrail, with the target next to it.
- Give the whole task up front: the goal, the scope, and what done looks like. Opus 5.5 does best when it gets the full spec and is left to run.

## Instructions that misfire on Opus 5.5

- **Verification steps.** Opus 5.5 checks its own work. "Double-check", "re-verify", "add a final verification step" and "use a subagent to verify" cause over-verification. Keep a check only against a system that fails silently, and say why.
- **Asking for reasoning.** Asking the model to write out its thinking or reasoning, verbatim or in a fixed format, can be refused. Ask for a short explanation of the answer or a summary of the actions instead. A "do not think" rule also backfires.
- **Open-ended delegation.** Opus 5.5 spawns subagents readily. Say which work warrants one: large, independent, parallel tracks. Without that, it delegates work it could finish in a few tool calls.
- **Scope.** Opus 5.5 widens tasks on its own judgment. When a command or skill has a narrow job, state the scope and where to stop.
- **Severity filters in reviews.** "Only report high severity" or "be conservative" is followed literally, and real findings go unreported. Ask for every finding, then filter in a separate step.
- **Length.** Its replies and the documents it writes run long. Where a file produces a report or doc, state the length or shape you want.

## Structure

- Files loaded every session earn every line: CLAUDE.md, rules without `paths`, and skill and agent descriptions. Keep each CLAUDE.md under 200 lines.
- Put a multi-step procedure in a skill. Put a rule for one part of the codebase in `.claude/rules/` with `paths` frontmatter, or in a CLAUDE.md in that subdirectory. Both load only when needed.
- An `@path` import loads the file every session. A plain path with a line saying when to read it loads on demand.
- Headers and short bullets. The model follows them better than dense paragraphs.
- Keep the repo's agent filename. Claude Code reads `AGENTS.md` only when no `CLAUDE.md` exists in the working directory or above it. To share one file with other tools, CLAUDE.md holds `@AGENTS.md`.
- Enforce a hard block with a hook or a `permissions.deny` rule. Prose is context, not enforcement.
- A skill description opens with its trigger and stays under about 500 characters. `SKILL.md` holds the workflow; lookup material goes in `references/`, one level deep.
- Prefer a script to multi-step prose an agent would re-derive each run. Prefer a routed doc section to a skill when the content is a few lines.

## Sources

- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/skills
- https://github.com/mattpocock/skills
