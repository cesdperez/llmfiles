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
- TDD when it adds value. Unless coverage already exists - literally write the test(s) first, make it fail, and then write the code to make it pass.

## Skill Maintenance

Skills are stored in `~/llmfiles/skills/<name>/SKILL.md`. When using a skill:
- **Correct outdated/incorrect info**: If skill data is wrong or no longer accurate
- **Capture useful learnings**: If the session reveals patterns, gotchas, or techniques relevant to the skill

Before updating a skill, prompt the user with what you want to change and why. Wait for approval.

## Writing Style
- Never use em dashes (`—`). Use a comma, colon, or rewrite the sentence instead.
- Never use emojis.
- Plain language. Short sentences. One idea per sentence. Do not pack several clauses into one line. Do not compress a paragraph into a single dense sentence. Several simple sentences beat one clever one.
- Anything others will read (MR comments and descriptions, Jira tickets, docs): lead with the point, cut preamble and filler, say it once. No softeners bolted on ("happy to be wrong", "just a thought"), write the condition instead ("unless X"). No metaphor for mechanics ("the knob is inert"), name the thing that stopped working.
