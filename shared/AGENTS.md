# Agent Instructions

## Code Style
- Minimal comments. Code should be self explanatory. Only comment the non-obvious "why" or missing context.
- Single Level of Abstraction Principle.

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
- Anything others will read (MR comments and descriptions, Jira tickets, docs): lead with the point, cut preamble and filler, say it once. No softeners bolted on ("happy to be wrong", "just a thought"), write the condition instead ("unless X"). No metaphor for mechanics ("the knob is inert"), name the thing that stopped working.
