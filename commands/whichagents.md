---
description: Recommend how to run the task I am about to start: solo session, subagents, a Workflow, or an agent team. Says why, what it costs, and when to switch.
argument-hint: [the task, if not already described in the session]
---

# /whichagents

Pick the execution mode for the task in `$ARGUMENTS`. With no argument, use the task I described most recently in this session. When neither says enough to choose, ask me one question: the fact that decides it (for example "is the contract between the repos already settled?").

Inspect before choosing when it is cheap: which repos are touched, whether a command I named already fans out (`~/llmfiles/commands/<name>.md`), how big the diff or work-list is.

## The four modes

| Mode | Use when | Relative cost |
|---|---|---|
| **Solo** | One context can hold the whole change, e.g. a ticket in one repo | 1x, cheapest |
| **Subagents** (`worker`, `reviewer`, ... from `~/llmfiles/agents/`) | Independent pieces the orchestrator splits at runtime, and only their conclusions come back | ~1x plus the summaries landing in the orchestrator |
| **Workflow** | The fan-out has a known, repeatable shape, the work runs long enough to need resume, or findings need adversarial verification | ~1x per agent, but usually 1.5-3x in total because scripts spawn more agents (a verifier per finding) |
| **Agent team** | Workers must change each other's work while it is in flight: an unsettled contract across repos, competing hypotheses in an incident, a design argued out, parallel panes I steer by hand | ~7x per the docs when teammates run in plan mode, grows with team size and teammate lifetime. Experimental. |

Decide in this order and stop at the first match:
1. Fits in one context: **solo**.
2. Workers need to talk to each other mid-task, and the pieces do not edit the same files: **agent team**.
3. Same shape every run, long horizon, or verify-heavy: **Workflow**.
4. Otherwise: **subagents**.

Constraints that change the answer:
- A Workflow script has no bash or filesystem access, but its agents do. Deterministic gathering (queue scripts, `git` scouting) is cheaper inline and enters as `args`.
- Workflows nest one level only through `workflow()`.
- Workflow agents inherit the session's model and effort unless the script sets `agentType: 'worker'` (or `model`/`effort`). The shape must name the agent type per stage.
- Teammates can spawn from a `~/llmfiles/agents/` definition and take its model, but always inherit the lead's effort. A team loses the effort pinning.
- An agent team is one per session, cannot nest, and in-process teammates do not survive a session resume. Work that must survive a restart goes to a Workflow.
- Parallel agents that edit files need `isolation: 'worktree'` in a Workflow, or separate files per teammate.
- Anything that runs a local stack and verifies end to end belongs in one place, usually the main session. Parallel agents each starting a stack collide on ports.
- A Workflow runs only with explicit opt-in: I say "use a workflow", put "ultracode" in the prompt, or run a command that calls Workflow. Ultracode as a session setting (`/effort ultracode`) makes workflows the default for every substantive task, so recommend it only for audits, migrations or high-stakes reviews.
- A `+500k`-style directive is a hard ceiling on output tokens for the turn, shared by the main loop and every workflow in it.

## Output

- **Use:** the mode, in one line.
- **Why:** two or three sentences tied to this task's facts, not to the table.
- **Shape:** how it would run concretely: which agents, what splits, what stays in the main session.
- **Cost:** the relative estimate and the main cost risk for this task (orchestrator bloat, fan-out explosion, chatty teammates).
- **Switch if:** the one condition that would flip the recommendation.

Then offer to start it in that mode. Start nothing until I say so.
