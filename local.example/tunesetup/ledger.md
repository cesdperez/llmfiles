# Tuning ledger format

`local/tunesetup/ledger.jsonl` records every setup change `/tunesetup` and `/whichmodels` propose or apply, one JSON object per line. It starts empty: `scripts/tuning-ledger.py add` creates it and checks each entry. Git keeps what changed, so the ledger keeps what git cannot: why, the metric the change should move, and whether it did.

| Field | Meaning |
|---|---|
| `id` | `<date>-<n>`, assigned by `add` when left out |
| `date` | when the change was proposed or applied, `YYYY-MM-DD` |
| `source` | `tunesetup`, `whichmodels` or `manual` |
| `change` | the change in one line |
| `files` | repo paths the change touches; `pending` matches commits on them |
| `where` | commit shas, or a settings key such as `~/.claude/settings.json:effortLevel` |
| `why` | the evidence behind the change |
| `metric` | `usage:`, `stages:` or `friction:` plus a `/` path into that script's JSON, or a plain name when hand-counted; null when no metric fits, with the reason in `note` |
| `baseline` | the metric's value before the change |
| `baseline_days` | set when the metric is a total over a period, so a longer run is scaled to it; null for medians and rates |
| `hand_counted` | true when a person or agent counted the baseline from transcripts; no script can measure it |
| `expected` | `up` or `down` |
| `reversed_by` | the evidence that would undo the decision |
| `note` | why a proposal was rejected, why no metric fits, or how a hand count is made |
| `status` | `proposed`, `applied`, `rejected` or `reverted` |
| `measured`, `measured_on` | the value a later run read, and that run's date |
| `moved` | `as_expected`, `flat` (under 5%) or `against` |
| `verdict` | `kept`, `reverted` or `inconclusive`; null while a move against the expected direction waits for a decision |

A path segment picks a key, or the element of a list whose `kind` equals it: `usage:tools/calls_per_request`, `usage:agents/worker/median_end_ctx`, `stages:stages/3 review/median`, `friction:tool_errors/Bash: permission denied/count`.

A hand-counted metric is settled by counting again the same way over a week after the change, then `set <id> measured=<n> measured_on=<date> moved=<...> verdict=<...>`.
