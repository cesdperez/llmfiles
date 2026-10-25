# /dailyworkrecap local style

Optional. Overrides the sample post in `commands/dailyworkrecap.md` and adds gotchas that
only hold for your team.

This is the length and tone I write myself:

```text
Team:
- Password import: identity provider now accepts legacy passwords, tested locally, MRs up [PROJ-493](https://acme.atlassian.net/browse/PROJ-493)
- Deployed orders-api to prod, token exchange included

No team:
- Prepared and organized the platform status meeting

Reviews: 5 MRs
```

## Gotchas

- **A fix can be merged and still inert.** <Work that does nothing until another change lands.>
