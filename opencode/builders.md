# Builders

Which builder takes a brief, by task kind. Check how each one does with `python3 ~/llmfiles/scripts/builder-evals.py summary`.

## Routing

| Task kind | Builder | Model |
| --- | --- | --- |
| `mechanical`, `bugfix`, `frontend`: renames, boilerplate, config, test scaffolding, docs, bug fixes, UI work | `builder-flash` | `opencode-go/deepseek-v4.1-flash#low` |
| `feature`, `refactor`, `frontend-logic`, `infra`, `long-context`: normal features, refactors, UI logic and browser debugging, shell-heavy debugging, and reading big files or logs | `builder-terra` | `openai/gpt-6.1-terra#low` |

Use the task kind names above in briefs and ledger rows. When a brief fits no row, send it to `builder-terra`.

The conductor A/Bs `builder-flash` against `builder-terra` on a quarter of the briefs that are not `mechanical`. After about 15 A/Bs of a kind, route it to Flash when Flash wins at least half, and back to Terra when Flash wins under 40%.

## Other conductor roles on Flash

- The rule-lens bundle of a review runs as `reviewer-flash`. The `reviewer` lenses (correctness, security) stay on Sol.
- Browser checks and other verify steps the conductor's shell cannot prove run as `worker-flash`.
- `ab-judge` and the escalation target stay on Sol, so a Flash diff is never judged or rescued by Flash.

## Quota fallback

When a Flash agent stops on a usage or rate limit instead of failing the task (a 429, `provider.free-limit`, `provider.rate-limit`, `provider.quota`, or any other error about usage or limits), send the same brief unchanged to its fallback at once: `builder-flash` to `builder-luna`, `reviewer-flash` to `reviewer-fast`, `worker-flash` to `worker`. This is not a retry or an escalation. A task failure on Flash follows the normal retry and escalation path.

## Escalation

After a failure, a narrowed retry in a fresh session, and a second failure:

- `builder-flash`, `builder-luna` and `builder-terra` go to `codex-worker` (`gpt-6.1-sol#high`), which stays on the ChatGPT plan.

## Why

- Flash runs on the OpenCode Go plan, which gives it a $100 monthly allowance at $0.15/$0.60 per 1M tokens (double at peak hours), capped at 20% in any 5 hours and 50% in any week. Go's agreement with DeepSeek keeps no data. It was the fastest builder on the fixture. Luna takes its briefs once a cap is hit.
- In the first 14 A/Bs on a real project, Flash won 8, Terra 5, with 1 no winner. Flash won `bugfix` 4 to 3 and `frontend` 2 to 0, lost `feature` 1 to 2, and took 1.7 to 2.7 times Terra's wall time. Moving builders and the rule lenses to Flash cuts the conductor's OpenAI use by about half, and the Opus conductor stays at about half of all tokens.
- Flash needs Global regions enabled in the OpenCode console privacy settings, since DeepSeek hosts it outside Europe and the US.
- Luna costs a tenth of Terra on the API ($0.10/$0.50 against $1/$5 per 1M tokens). Its `-fast` tier saved little time and draws 2.5x of the plan allowance.
- Terra passed every measured brief and the 3-file refactor in the same time as a small task, so it takes the kinds where Flash has not yet won its A/Bs.
- Terra's low, medium and default variants ran at the same speed. The Coding Agent Index puts Terra at 48, Luna at 31 and Sol at 54 ([source](https://www.orcarouter.ai/blog/gpt-6-1-terra-benchmark)).
- Sonnet 5.5 was the fastest model measured here, but using Terra keeps all builder work on the ChatGPT plan.
- Haiku 5.5 is not a builder. It was slower than Sonnet on a multi-file task and used about 4x the output tokens ([source](https://chaseai.io/blog/haiku-5-5-vs-gpt-6-luna), [source](https://www.developersdigest.tech/blog/haiku-5-5-vs-gpt-6-luna-subagent)).
- `claude-agent` models draw from the Claude subscription ([source](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)), and `openai` models from the ChatGPT plan.

## Measured speed

`opencode run --auto`, two runs each, seconds. Every run passed its tests, so this compares speed only. Flash was measured on a later day, when Terra took 15.7 and 26.7, and used 1.3 to 2.5 times Terra's output tokens plus reasoning tokens.

| Model | Small task | 3-file refactor |
| --- | --- | --- |
| `deepseek-v4.1-flash` (free tier) | 12.6, 7.6 | 16.7, 17.8 |
| `gpt-6-luna#low` | 21, 17 | 34, 26 |
| `gpt-6.1-terra#low` | 16, 16 | 26, 27 |
| `sonnet#low` | 9, 9 | 9, 9 |
| `haiku` | 8, 11 | 23, 20 |
