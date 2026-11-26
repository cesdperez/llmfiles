# Agent Instructions

For CLI upgrades, including "upgrade all my CLIs", read
`~/llmfiles/shared/agentic-clis.md` and follow its CLI and companion-skill procedure.

## Shell
- Read a directory whose path holds `$`, a glob character or `$(...)` by passing its full single-quoted path to the command, or with the Read tool, `git -C '<dir>'` or `grep -r <pattern> '<dir>'`. Never `cd` into it: the harness cannot resolve that directory, so the `Read(./secrets/**)` deny rule blocks every later relative read, quoted or not.

## Code Style
- Minimal comments. Code should be self explanatory.
- Single Level of Abstraction Principle.

### Comments
- Only comment the non-obvious "why" or missing context. Never restate what the code does.
- A test or a better name beats a comment when either will do.
- Put the comment on the line that is easy to get wrong, not at the top of the function. Its job is to stop a plausible refactor from breaking something.
- Doc comments only on public/exported API, so a caller can skip reading the implementation.
- Write for someone reading in 10 months. Describe the constraint, not today's task. No "new", "for now", "temporary", "recently changed", no sprint or migration status, no dates.
- Do not name Jira tickets or MRs by default. Only when the ticket holds context that does not fit in one line and will still matter later.
- Reading rule: do not open a Jira ticket just because a comment names one. Only if the current task actually needs it.
- Plain english. One or two lines. If it needs a paragraph, the code or the test is the wrong shape.
- While editing code, delete or fix any nearby comment you cannot verify.

## Testing
- TDD when it adds value: literally write the test first, watch it fail, then write the code that makes it pass. Skip it where coverage already exists.

## Skill Maintenance

Skills are stored in `~/llmfiles/skills/<name>/SKILL.md`. When using a skill, update it where the session showed the skill wrong or stale, or surfaced a pattern, gotcha, or technique it should carry.

Before updating a skill, prompt the user with what you want to change and why. Wait for approval.

### Writing skills, commands, and CLAUDE.md
- Read `~/llmfiles/shared/agent-docs-bar.md` first. It is the bar for every line.

## Delegation
Keep a step in this session when it builds on the details of the step before it: a chain of edits over the same files, or a fix that follows its own investigation. A handoff passes only a summary, and the next step loses the details. Delegate a piece when it is independent and only its conclusion comes back, when pieces run in parallel, or when this session's context is filling up.

Executors are the named agents in `~/llmfiles/agents/`, each pinned to a model and effort so the session's own effort never leaks into delegated work. Pick by how much reasoning the task needs: `worker` for changes and investigations, `worker-fast` for chores with known steps, `reviewer` and `reviewer-fast` for read-only audits, `Explore` for locating code. `codex-worker` and `codex-reviewer` run the task on Codex, billed to the ChatGPT plan. Pick `codex-worker` over `worker` when the brief is complete on its own, needs no network, and the result needs no follow-up in the same context: a follow-up starts Codex fresh. A lensed review runs `codex-reviewer` on correctness alongside the Claude reviewers every time, as `~/llmfiles/shared/review-lenses.md` says, and any other review adds it when a diff is high-risk. Use them whenever the user asks for Codex or says Anthropic usage is tight. When an executor fails on a usage limit, rerun the same brief on the other side: `codex-worker` and `codex-reviewer` fall back to `worker` and `reviewer`, and a Claude executor falls back to its Codex counterpart. If the Codex forwarder hits the Anthropic limit too, run its `codex exec` command yourself with Bash. A fork runs on the session model and effort, so fork only when the executor needs this conversation itself.

Give each executor one working set: the files and decisions its task depends on. Send follow-up work in that working set to the same agent while it is under 150k tokens of context. Start a fresh agent when the working set changes or the context passes that limit, and hand it `file:line` pointers and decisions so it reads instead of re-explores.

## Writing Style
- Never use em dashes (`—`). Rewrite the sentence with the punctuation it actually wants: a comma, colon, period, parentheses, or a conjunction. Never swap the character for another one in place.
- Never use emojis.
- Chat replies to the user: answer first and keep it short. Use the project's own terms, skip recaps and closing summaries, and leave out what the reader can work out alone.
- Plain language. One idea per sentence: several simple sentences beat one clever one.
- State the point as a plain declarative sentence. Never announce it first ("The key thing:", "The important part:", "What this means:"). The label reads as filler and the sentence under it is weaker for having been introduced.
- Anything others will read (MR comments and descriptions, Jira tickets, docs): lead with the point, cut preamble and filler, say it once. No softeners bolted on ("happy to be wrong", "just a thought"), write the condition instead ("unless X"). No metaphor for mechanics ("the knob is inert"), name the thing that stopped working.
