# Agent Instructions

## Code Style
- Minimal comments. Code should be self explanatory.
- Single Level of Abstraction Principle.

### Comments
- Only comment the non-obvious "why" or missing context. Never restate what the code does.
- A test or a better name beats a comment when either will do.
- Put the comment on the line that is easy to get wrong, not at the top of the function. Its job is to stop a plausible refactor from breaking something.
- Doc comments only on public/exported API, so a caller can skip reading the implementation.
- Write for someone reading in 10 months. Describe the constraint, not today's task. No "new", "for now", "temporary", "recently changed", no sprint or migration status, no dates.
- Do not name Jira tickets or MRs by default. Only when the ticket holds context that does not fit in one line and will still matter later.
- Reading rule: do not open a Jira ticket just because a comment names one. Only if the current task actually needs it.
- Plain english. One or two lines. If it needs a paragraph, the code or the test is the wrong shape.
- While editing code, delete or fix any nearby comment you cannot verify.

## Testing
- TDD when it adds value: literally write the test first, watch it fail, then write the code that makes it pass. Skip it where coverage already exists.

## Skill Maintenance

Skills are stored in `~/llmfiles/skills/<name>/SKILL.md`. When using a skill, update it where the session showed the skill wrong or stale, or surfaced a pattern, gotcha, or technique it should carry.

Before updating a skill, prompt the user with what you want to change and why. Wait for approval.

### Writing skills, commands, and CLAUDE.md
- Every line must change behaviour versus the model default. A line the model already obeys pays context on every turn to say nothing. When a line fails that test, delete the whole sentence rather than trim words from it. Settle a disagreement about what the default is by running the document, not by arguing about it.
- Prompt the positive. Steering by prohibition makes the forbidden behaviour more available, not less, so name the target behaviour and the banned one never gets spoken. A prohibition earns its place only as a hard guardrail no positive phrasing covers, and even then it carries the target beside it.

## Writing Style
- Never use em dashes (`—`). Rewrite the sentence with the punctuation it actually wants: a comma, colon, period, parentheses, or a conjunction. Never swap the character for another one in place.
- Never use emojis.
- Plain language. One idea per sentence: several simple sentences beat one clever one.
- State the point as a plain declarative sentence. Never announce it first ("The key thing:", "The important part:", "What this means:"). The label reads as filler and the sentence under it is weaker for having been introduced.
- Anything others will read (MR comments and descriptions, Jira tickets, docs): lead with the point, cut preamble and filler, say it once. No softeners bolted on ("happy to be wrong", "just a thought"), write the condition instead ("unless X"). No metaphor for mechanics ("the knob is inert"), name the thing that stopped working.
