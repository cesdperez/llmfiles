# TODO

## Finish the em dash sweep

103 occurrences left, all in `skills/`. `README.md`, `commands/`, and `shared/` are clean.

| File | Count |
| --- | --- |
| `skills/intervals-icu/SKILL.md` | 29 |
| `skills/grafana-k6/SKILL.md` | 18 |
| `skills/playwright-cli/references/test-generation.md` | 15 |
| `skills/graphify/SKILL.md` | 12 |
| `skills/supabase/SKILL.md` | 6 |
| `skills/tailwind-svelte/SKILL.md` | 5 |
| `skills/playwright-cli/references/video-recording.md` | 4 |
| `skills/twg-operational-health/SKILL.md` | 3 |
| `skills/svelte/SKILL.md`, `skills/playwright-cli/SKILL.md`, `skills/cf-cli/SKILL.md` | 2 each |
| `skills/zitadel-api/SKILL.md`, `skills/twg/references/OUTPUT.md`, `skills/twg-confluence/references/body-formats.md`, `skills/playwright-cli/references/session-management.md` | 1 each |

Rewrite each sentence by hand, per the rule in `shared/AGENTS.md`. A blind character swap is
what breaks things: `skills/zitadel-api/SKILL.md:3` is inside the YAML `description:` field, so
a colon there needs the value quoted or the frontmatter stops parsing and the skill silently
disappears from discovery.

Verify with `grep -rn "—" . | grep -v shared/AGENTS.md`, which should return nothing.

## A `/writeup` command for decision records and design docs

Port of `writing-fragments` plus `writing-shape` from
[mattpocock/skills](https://github.com/mattpocock/skills), scoped down.

**Where it fits.** Decision records and design docs, on wikis or in repos. The rationale for a
decision lives only in your head, so a model asked to write the document straight produces
plausible reasoning nobody actually holds. An interview is the only way to get the real
reasoning out.

**Where it does not fit.** Repo `.md` documentation derived from code. The model can read the
code, so interviewing you asks for facts it should look up itself. Reach for the existing
skills there.

**Build it smaller than he did.** His three skills split explore (`writing-fragments`) from
exploit (`writing-shape`, `writing-beats`) because an article gets written over days. An ADR
gets written in one sitting, so one command with two phases is enough.

Phase one, explore: interview, and append every fragment worth keeping to a scratch markdown
file separated by `---`. Fragments are heterogeneous on purpose: a sharp sentence, a claim with
one line of justification, a vignette, a half-thought, the option you rejected and why.
Re-read the file from disk before every write, because you will edit it between turns.

Phase two, exploit: build the document block by block from that pile. Two concepts carry this
phase.

- **Grounding.** No block may lean on a concept the reader has not met yet. Each block requires
  concepts that are already grounded and grounds new ones. Keep the running list. Settle up
  front what the reader walks in knowing, because the lever is what you make a prerequisite
  versus what you ground inside the document. This is what makes a design doc readable by
  someone who was not in the room.
- **The leading word.** One compact term the whole document hangs on, repeated as a token and
  never restated as a sentence. Prefer a term the model already knows over a coinage: a made-up
  word recruits no priors, so you pay in definition tokens what a pretrained word gives free.

**Prerequisite.** Phase one needs an interview loop we do not have. His `grilling` skill is the
model: map the topic as a design tree, work it in rounds, and each round ask the whole
**frontier** (every decision whose prerequisites are settled) as numbered questions with a
recommended answer attached to each. Wait for answers, recompute the frontier, repeat. Finding
facts is the agent's job, never the user's: dispatch a subagent for anything in the filesystem
or the tools rather than asking. Done when the frontier is empty. Worth porting on its own, and
it is the piece to build first.
