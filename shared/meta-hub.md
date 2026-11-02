# Meta hub

A session runs in a hub when its checkout's folder holds the repos the work touches, such
as a `meta` repo whose child repos are gitignored clones. A single repo is never a hub.
The Orca side (registering repos, nesting worktrees) is in
`~/llmfiles/shared/orca-fleet.md`, under Repos under a hub.

## Checkouts

- The repos under the hub are the user's main clones. They stay on their default branch.
  Change code only in this run's worktrees, and read the clones only for reference.
- Give every agent and tool absolute paths. The hub is not the repo it works on.

## Ordering

Two tasks depend on each other when they touch the same file, and also when they touch
these, which conflict like one file:

- numbered DB migrations in the same service;
- the lockfile of a repo, when both add or upgrade dependencies;
- a generated API client or schema, when both change the contract it comes from.

A change that crosses repos ships provider first: the API before its consumers, a shared
package before the apps that bump it.

## Verify

Read `~/llmfiles/local/meta-hub-verify.md` if it exists. It says how to run the hub's local
stack on a run's worktrees. Without it, verify the way the repo's own docs say.
