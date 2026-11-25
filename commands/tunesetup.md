---
description: Review my Claude Code setup over the last period, every 1 or 2 weeks. Measures usage with scripts, reads the transcripts for friction, checks new outside evidence, compares with the run before, and proposes changes to commands, agents and shared files. Proposes only.
argument-hint: '[days] [focus: a command name, "cost", "speed" or "quality"]'
disable-model-invocation: true
---

# /tunesetup

Find what in this repo costs money, time or rework, and propose the changes that fix it. `$ARGUMENTS` may hold the period in days and a focus. Without a period, use the days since the newest `~/llmfiles/local/tunesetup/<date>/`, or 14 when there is none. A command name as focus limits the friction read and the report to that command. `cost`, `speed` or `quality` limits the report to that group.

Propose only. This command edits two files: the price table in `~/llmfiles/scripts/claude-usage.py` (step 2) and the tuning ledger. Everything else waits for my answer at the end.

`D` is today's date, and `~/llmfiles/local/tunesetup/D/` holds this run's files. `L` stands for `python3 ~/llmfiles/scripts/tuning-ledger.py`.

## 1. Read the ledger and the previous run

`~/llmfiles/local/tunesetup/ledger.jsonl` is the one record of proposals and changes across runs, from this command, `/whichmodels` and by hand. Its fields are in `~/llmfiles/local.example/tunesetup/ledger.md`. Read and write it only through `L`, which rejects an invalid entry.

- `L pending` lists, for each `proposed` entry, the commits on `main` since its date that touch its files, and the settings keys it names, which no commit shows: read those settings yourself. When a commit or a setting makes the change, run `L set <id> status=applied where+=<sha> date=<date applied>`; `+=` appends, so a settings key already in `where` stays. A proposal not applied yet stays `proposed` and is listed as pending.
- `L list --status rejected` gives the proposals I declined, with my reason in `note`. Do not propose one again unless this period brings evidence it did not have.
- `L list --open` gives the applied entries with no verdict and a week of data since their date. Step 2 measures them.

Read the newest earlier run directory, if there is one: `usage.json`, `stages.json` and `report.md`. The periods can differ in length, so compare rates: per session, per run or per day, never totals.

## 2. Measure

Create the run directory, then run the three scripts in parallel, one Bash call each. A week takes under a minute.

```bash
python3 ~/llmfiles/scripts/claude-usage.py --days <days> > ~/llmfiles/local/tunesetup/D/usage.json
python3 ~/llmfiles/scripts/fullsend-stages.py --days <days> > ~/llmfiles/local/tunesetup/D/stages.json
python3 ~/llmfiles/scripts/session-friction.py --days <days> [--command <focus>] > ~/llmfiles/local/tunesetup/D/friction.json
```

If `usage.json` has `unpriced_requests`, load the `claude-api` skill, add each missing model's list prices to `PRICES` in `claude-usage.py`, set `PRICES_CHECKED` to `D`, and run it again. Name that edit in the report so it gets committed.

`usage.json` holds `headline`, the flat metrics the next run compares, plus cost by model, command, agent type and context size, cache misses by idle gap, compactions, tool mix and result sizes, and main-session idle time while subagents run. `stages.json` holds minutes per `/fullsend` stage. `cost_state_check` compares the script's cost with Claude Code's own on the `sessions` whose totals are complete: a gap over 5% means the prices or the deduplication are off, so say so before using the dollar figures.

Then settle the open entries from step 1, one date at a time. A settled entry leaves the open list for good, so its figures must cover only the days after its date. For each date among them, run the three scripts again with `--days` set to the days since that date, `friction` without `--command`, into `~/llmfiles/local/tunesetup/D/since-<date>/`, then:

```bash
R=~/llmfiles/local/tunesetup/D/since-<date>
L measure --since <date> --usage $R/usage.json --stages $R/stages.json --friction $R/friction.json
```

It reads each entry's metric, scales a period total to its `baseline_days`, and writes `measured`, `moved` and `verdict`. An entry with `hand_counted` goes to the friction worker, which counts it again the way its `note` says; record the count with `L set` as the ledger format describes. A `moved` of `against` leaves the verdict to me.

## 3. Friction and outside evidence

Spawn two `worker` agents in one message.

**Friction.** Give it `friction.json`, the commands in scope, the rejected ledger entries, and the open hand-counted entries to count again.
- It reads the extracts one command at a time: `jq '.sessions[] | select(.command | startswith("<name>"))'`.
- It opens one session with `session-friction.py --session <id>` when an extract is too short to judge.
- It reads `~/llmfiles/commands/<name>.md` and the files it loads.
- Problems to look for: human corrections, stalls and interrupts, rework loops, skipped or useless steps, thin briefs, review findings that were noise, bugs the review missed, and repeated tool errors.
- Each problem has a count as n of m sessions, one quoted example with session id and date, and the `file:line` that causes it.
- It returns what works too, so the report can name it.

**Outside evidence.** Give it the previous run's date, or the start of the period. It gathers only what was published since then: the Claude Code changelog and docs, benchmarks on code review, orchestration and cost, and practitioner reports. Each claim gets its URL, publish date and a tag: `official docs`, `benchmark`, `vendor claim` or `anecdote`. It reports only claims that bear on a command, agent or setting in this repo.

Model and effort choices belong to `/whichmodels`. When the numbers suggest one is wrong (an agent type's cost against its work, a model or effort nobody pinned), say to run `/whichmodels` and why. Do not propose the change here.

## 4. Draft the proposals

Each proposal has:
- the files to change and the change in one line;
- evidence from the transcripts or the numbers: n of m runs, or a dollar or minute figure;
- the expected effect, with estimates marked as estimates;
- the metric it should move, as a path into this run's script output, with its value now as the baseline. Use a hand count only when no script measures it, and say in `note` how to count it again.

Append each one with `L add` as `proposed`, `source` `tunesetup`, dated `D`. The id it prints is the proposal's id in the report.

Outside evidence alone supports only "test this", never a change. Prefer one change at a cause over several at its symptoms. A secret found in a transcript is reported by session and date, never by value.

## Output

Write `report.md` in the plain style of this repo's commands: tables first, under about 900 words.

```
tunesetup D, <days> days, <sessions> sessions, $<total> list price

Since last run
| Metric | Then | Now | Change |

Settled since last run
| Id | Change | Metric | Baseline | Now | Moved |

Proposals: review quality / cost / speed and stalls / tool friction
| Id | File | Change | Evidence | Expected effect |

Test this: one line each, with its source.
Leave alone: 3 to 6 lines on what the data shows working.
Secrets: session, date and kind, when any were found.
```

Under the tables, at most two lines per proposal that needs more than its row. An entry that moved `against` gets a line suggesting to revert or rework it. Pending proposals get one line each. Skip a section that has nothing.

End by asking which proposals to apply, and what to do with each entry that moved `against`. Group the accepted proposals by the files they touch and offer to run them with `/fleet`, one item per group. Accepted ones stay `proposed` until a commit applies them. For each one I decline, run `L set <id> status=rejected note="<my reason>"`. For an entry I revert, set `status=reverted verdict=reverted`; for one I keep, `verdict=kept`.
