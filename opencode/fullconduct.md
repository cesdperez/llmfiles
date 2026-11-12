# /fullconduct

`/fullsend` run by the conductor. Follow `~/llmfiles/commands/fullsend.md` with the tool substitutes in `~/llmfiles/opencode/compatibility.md`. Where they disagree, this file wins, and `fullsend.md` wins over `conductor.md`.

## Conductor rules that change

- You commit, granularly, as `fullsend.md` says. The conductor's rule to leave commits to the user does not apply.
- The run ledger and `fullsend-qa/` live in the git directory, not the repo tree. Write them with the shell.
- The run ends with the `fullsend.md` handoff report, not the conductor's report.

## Stages

- **Handoff to a new worktree.** Run it exactly as `fullsend.md` says, with `--agent opencode` and `/fullconduct` in place of `/fullsend` in the prompt, so the new session runs on the conductor too.
- **0. Intake.** Explore the code yourself, or with `explore` for a broad search. No intake worker owns the working set.
- **2. Implement.** Every change, docs included, goes out as a builder brief, routed, retried, escalated and logged as `conductor.md` and `builders.md` say. Review each diff, then commit it. `worker` and `codex-worker` take only escalations.
- **3. Review.** The locallensedreview skill is not available here. Read `~/llmfiles/commands/locallensedreview.md` and `~/llmfiles/shared/review-lenses.md`, and run the lens fan-out yourself with `reviewer`, `reviewer-fast` and `codex-reviewer`, all in one turn. Its `--autofix` step sends each surviving finding as a builder brief, one at a time, and you commit the fixes. Fix only findings inside the task's scope. List the rest in the ledger and the handoff's Open line, as stage 2 does with adjacent problems.
- **4. Verify.** Brief a `worker` with what `fullsend.md` lists, or run curl and the tests in your own shell when they prove every criterion. A Fail goes out as a builder brief before verify runs again.
