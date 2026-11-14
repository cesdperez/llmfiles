# Builders

Which builder takes a brief, by task kind. Check how each one does with `python3 ~/llmfiles/scripts/builder-evals.py summary`.

## Routing

| Task kind | Builder | Model |
| --- | --- | --- |
| `mechanical`: renames, boilerplate, config, test scaffolding, docs | `builder-flash` | `opencode/deepseek-v4.1-flash-free#low` |
| `feature`, `bugfix`, `refactor`, `frontend-logic`, `frontend`, `infra`, `long-context`: normal features and bug fixes, refactors, UI work, browser debugging, shell-heavy debugging, and reading big files or logs | `builder-terra` | `openai/gpt-6.1-terra#low` |

Use the task kind names above in briefs and ledger rows. When a brief fits no row, send it to `builder-terra`.

A/Bs of `builder-flash` against `builder-terra` on `feature` and `refactor` briefs decide whether Flash takes more kinds.

## Quota fallback

When `builder-flash` stops on a usage or rate limit instead of failing the task (a 429, "Free usage limit reached", `provider.free-limit`, `provider.rate-limit`, `provider.quota`, or any other error about usage or limits), send the same brief unchanged to `builder-luna` at once. This is not a retry or an escalation. A task failure on Flash follows the normal retry and escalation path.

## Escalation

After a failure, a narrowed retry in a fresh session, and a second failure:

- `builder-flash`, `builder-luna` and `builder-terra` go to `codex-worker` (`gpt-6.1-sol#high`), which stays on the ChatGPT plan.

## Why

- Flash is free on OpenCode Zen, its provider keeps no data, and it was the fastest builder on the fixture. The free tier is for a limited time, publishes no quota, and can stop for hours, so Luna stays as its fallback and Flash may disappear.
- Luna costs a tenth of Terra on the API ($0.10/$0.50 against $1/$5 per 1M tokens). Its `-fast` tier saved little time and draws 2.5x of the plan allowance.
- Terra passed every measured brief and the 3-file refactor in the same time as a small task, so it takes all work that is not mechanical.
- Terra's low, medium and default variants ran at the same speed. The Coding Agent Index puts Terra at 48, Luna at 31 and Sol at 54 ([source](https://www.orcarouter.ai/blog/gpt-6-1-terra-benchmark)).
- Sonnet 5.5 was the fastest model measured here, but using Terra keeps all builder work on the ChatGPT plan.
- Haiku 5.5 is not a builder. It was slower than Sonnet on a multi-file task and used about 4x the output tokens ([source](https://chaseai.io/blog/haiku-5-5-vs-gpt-6-luna), [source](https://www.developersdigest.tech/blog/haiku-5-5-vs-gpt-6-luna-subagent)).
- `claude-agent` models draw from the Claude subscription ([source](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)), and `openai` models from the ChatGPT plan.

## Measured speed

`opencode run --auto`, two runs each, seconds. Every run passed its tests, so this compares speed only. Flash was measured on a later day, when Terra took 15.7 and 26.7, and used 1.3 to 2.5 times Terra's output tokens plus reasoning tokens.

| Model | Small task | 3-file refactor |
| --- | --- | --- |
| `deepseek-v4.1-flash-free` | 12.6, 7.6 | 16.7, 17.8 |
| `gpt-6-luna#low` | 21, 17 | 34, 26 |
| `gpt-6.1-terra#low` | 16, 16 | 26, 27 |
| `sonnet#low` | 9, 9 | 9, 9 |
| `haiku` | 8, 11 | 23, 20 |
