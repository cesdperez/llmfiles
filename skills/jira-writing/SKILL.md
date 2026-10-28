---
name: jira-writing
description: How to write Jira ticket text - summaries, descriptions with acceptance criteria and definition of done, and comments. Use whenever creating, refining, or commenting on a Jira ticket, together with twg-jira for the mechanics.
---

Jira text is read by product managers, testers, and engineers who were not in the
conversation. Write so each of them can act on it without asking. Load the `plainenglish`
skill first; the rules below are the Jira-specific additions.

## Summary

One line, an outcome in the reader's words: "Customers can resend the verification email",
not "Fix resend endpoint". No Jira keys, no type prefix.

## Description

Three sections, in this order. Bullets, not paragraphs.

```
**Why**
One to three sentences: the problem, who has it, what it costs. Link the Slack thread or
incident instead of retelling it.

**Acceptance criteria**
- <observable result a tester can check, one per bullet>

**Definition of done**
- [ ] <the delivery steps this ticket needs>
```

Acceptance criteria:
- Each one is a result someone can see or measure: "A customer with an expired link sees
  'Link expired' and a resend button." Not "Handle expired links."
- Name the user role, the trigger, and the visible result. Given/When/Then only when the
  setup is not obvious.
- Cover the failure and edge cases that matter, not only the happy path.
- Keep the implementation out. If a technical constraint is part of the ask, state it as
  one criterion.

Definition of done is the checklist for this ticket, not a team-wide boilerplate. Pick
from: tests cover the criteria, verified on staging, deployed to production, feature flag
removed or rolled out, docs or runbook updated, stakeholders told. Leave out the items
that do not apply.

## Comments

- Status updates: what changed and what is next, with links (MR, deploy, dashboard). Two
  or three lines.
- Questions: one question per comment, mention the person who can answer it.
- When a decision changes scope, edit the acceptance criteria and say so in a comment.
  The description stays the current truth; the comments hold the history.
