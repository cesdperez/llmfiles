---
description: Research the latest Anthropic models (docs, benchmarks, user reports), then propose which model and effort each agent and the session in this repo should run. Adversarially reviewed. Outputs a today-vs-proposed table.
argument-hint: [optional focus, e.g. a model name or "only the agents"]
---

# /whichmodels

Decide whether the model and effort pinned to each executor still fits now that newer models exist. Run it after a release, and again a few weeks later once user reports have settled. `$ARGUMENTS` narrows the scope when given.

Propose only. Change no file until I say so.

## 1. Inventory what runs today

Do this inline, it is cheap:
- Every `~/llmfiles/agents/*.md`: `model`, `effort`, and the `description` (it says what the agent is for).
- `~/.claude/settings.json`: `model`, `effortLevel`, `modelSettings` (per-model effort overrides), and `env.CLAUDE_CODE_SUBAGENT_MODEL`.
- Which commands dispatch to which agent (`grep -rn` for the agent names in `~/llmfiles/commands` and `~/llmfiles/shared`), so each row has a concrete workload behind it.
- The model rationale in `~/llmfiles/README.md` under "Agents".

Each of these becomes one row of the final table.

## 2. Research in parallel

Spawn three `worker` agents in one message. Give each the list of Anthropic models to cover: the current Fable, Opus, Sonnet and Haiku, plus any model released in the last six months. Each one returns, per model, claims with source URL and publish date. Each one also marks whether a claim is about the current version or an older one.

- **official**: Anthropic model docs, model cards, release posts, pricing, the Claude Code changelog. Cover what each effort level means per model, since a level name does not mean the same amount of thinking across models.
- **benchmarks**: independent results on agentic coding and tool use (SWE-bench Verified/Pro, Terminal-Bench, Aider, LMArena, and similar), with cost and latency where they are published. Vendor numbers count only when an independent result confirms them.
- **field reports**: practitioner reports from Hacker News, Reddit, X, and engineering blogs on coding, reviews, research and long agentic runs. Cover regressions, laziness, over-eagerness, and rate limits. Weight reports from after the first week over launch-day reactions.

Each agent uses WebSearch in `extended` mode for anything from the last month.

## 3. Draft the proposal

For each row, pick model and effort against that row's workload. Reason from:
- the quality gap on that kind of task, not on headline benchmarks;
- cost and latency, which matter more for high-volume rows (`Explore`, `worker-fast`) than for rare ones;
- effort being re-tuned per release, so compare by the thinking the level buys, not by its name;
- aliases (`opus`, `sonnet`, `fable`, `haiku`) already following the newest model of a family. Propose a pinned ID only when a specific version is the point.

"Keep" is a valid proposal and needs a reason too.

## 4. Adversarial round

Spawn two `reviewer` agents in one message, each with the inventory, the research, and the draft:
- **against change**: for every proposed change, make the strongest case for keeping today's setting. Use cost, a regression the research missed, and evidence that is too thin or too early.
- **against keep**: for every "keep", make the strongest case that a change is overdue.

Each one returns a verdict per row (`holds` or `overturned`) with its evidence. Then settle each row in the main session. A row flips only when the reviewer's evidence is sourced and beats the draft's. When neither side clearly wins, the row stays as it is today.

## Output

A table, one row per thing from step 1:

| Thing | Used for | Today | Proposed |
|---|---|---|---|
| `worker` | changes, investigations | opus / high | no change |

Write `Today` and `Proposed` as `model / effort`.

Then one short paragraph per changed row under the table. Each paragraph gives why, the strongest counter-argument, and why it lost. Then one line naming the evidence that would reverse the call, so the next run knows what to check.

End by offering to apply the changes, including the README "Agents" rationale when it no longer matches.
