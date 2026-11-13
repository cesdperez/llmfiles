# Builders

Which builder takes a brief, by task kind. Every builder runs on OpenAI, checked with `python3 ~/llmfiles/scripts/builder-evals.py summary`.

## Routing

| Task kind | Builder | Model |
| --- | --- | --- |
| `mechanical`: renames, boilerplate, config, test scaffolding, docs | `builder-luna` | `openai/gpt-6-luna#low` |
| `feature`, `bugfix`, `refactor`, `frontend-logic`, `frontend`, `infra`, `long-context`: normal features and bug fixes, refactors, UI work, browser debugging, shell-heavy debugging, and reading big files or logs | `builder-terra` | `openai/gpt-6.1-terra#low` |

Use the task kind names above in briefs and ledger rows. When a brief fits no row, send it to `builder-terra`.

## Escalation

After a failure, a narrowed retry in a fresh session, and a second failure:

- `builder-luna` and `builder-terra` go to `codex-worker` (`gpt-6.1-sol#high`), which stays on the ChatGPT plan.

## Why

- Luna costs a tenth of Terra on the API ($0.10/$0.50 against $1/$5 per 1M tokens). Its `-fast` tier saved little time and draws 2.5x of the plan allowance.
- Terra passed every measured brief and the 3-file refactor in the same time as a small task, so it takes all work that is not mechanical.
- Terra's low, medium and default variants ran at the same speed. The Coding Agent Index puts Terra at 48, Luna at 31 and Sol at 54 ([source](https://www.orcarouter.ai/blog/gpt-6-1-terra-benchmark)).
- Sonnet 5.5 was the fastest model measured here, but using Terra keeps all builder work on the ChatGPT plan.
- Haiku 5.5 is not a builder. It was slower than Sonnet on a multi-file task and used about 4x the output tokens ([source](https://chaseai.io/blog/haiku-5-5-vs-gpt-6-luna), [source](https://www.developersdigest.tech/blog/haiku-5-5-vs-gpt-6-luna-subagent)).
- `claude-agent` models draw from the Claude subscription ([source](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)), and `openai` models from the ChatGPT plan.

## Measured speed

`opencode run --auto`, two runs each, seconds. Every run passed its tests, so this compares speed only.

| Model | Small task | 3-file refactor |
| --- | --- | --- |
| `gpt-6-luna#low` | 21, 17 | 34, 26 |
| `gpt-6.1-terra#low` | 16, 16 | 26, 27 |
| `sonnet#low` | 9, 9 | 9, 9 |
| `haiku` | 8, 11 | 23, 20 |
