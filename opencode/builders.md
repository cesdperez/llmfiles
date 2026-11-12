# Builders

Which builder takes a brief, by task kind. The target split is about 4 briefs in 5 on OpenAI and 1 in 5 on Sonnet, checked with `python3 ~/llmfiles/scripts/builder-evals.py summary`.

## Routing

| Task kind | Builder | Model |
| --- | --- | --- |
| `mechanical`: renames, boilerplate, config, test scaffolding, docs | `builder-luna` | `openai/gpt-6-luna#low` |
| `feature`, `bugfix`: normal features and bug fixes | `builder-terra` | `openai/gpt-6.1-terra#low` |
| `frontend`, `refactor`, `infra`, `long-context`: UI, refactors across many files, shell and terminal-heavy debugging, reading big files or logs | `builder-sonnet` | `claude-agent/sonnet#low` |

Use the task kind names above in briefs and ledger rows. When a brief fits no row, send it to `builder-terra`.

## Escalation

After a failure, a narrowed retry in a fresh session, and a second failure:

- `builder-luna` and `builder-terra` go to `codex-worker` (`gpt-6.1-sol#high`), which stays on the ChatGPT plan.
- `builder-sonnet` goes to `worker` (`claude-agent/opus#medium`).

## Why

- Luna costs a tenth of Terra on the API ($0.10/$0.50 against $1/$5 per 1M tokens). Its `-fast` tier saved little time and draws 2.5x of the plan allowance.
- Terra's low, medium and default variants ran at the same speed. The Coding Agent Index puts Terra at 48, Luna at 31 and Sol at 54 ([source](https://www.orcarouter.ai/blog/gpt-6-1-terra-benchmark)).
- Sonnet 5.5 scores 70.6% on Terminal-Bench 4.0 against Terra's 50.3% ([source](https://mixed-news.com/en/claude-sonnet-5-5-terminal-bench-70-6-percent-half-opus-price/), [source](https://letsdatascience.com/blog/gpt-6-1-terra-beats-openai-flagship-claude-still-leads)), and it was the fastest model measured here.
- Haiku 5.5 is not a builder. It was slower than Sonnet on a multi-file task and used about 4x the output tokens ([source](https://chaseai.io/blog/haiku-5-5-vs-gpt-6-luna), [source](https://www.developersdigest.tech/blog/haiku-5-5-vs-gpt-6-luna-subagent)).
- The conductor pins `claude-fable-5-2`, because the `claude-agent/fable` alias resolves to Fable 5.1.
- `claude-agent` models draw from the Claude subscription ([source](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)), and `openai` models from the ChatGPT plan.

## Measured speed

`opencode run --auto`, two runs each, seconds. Every run passed its tests, so this compares speed only.

| Model | Small task | 3-file refactor |
| --- | --- | --- |
| `gpt-6-luna#low` | 21, 17 | 34, 26 |
| `gpt-6.1-terra#low` | 16, 16 | 26, 27 |
| `sonnet#low` | 9, 9 | 9, 9 |
| `haiku` | 8, 11 | 23, 20 |
