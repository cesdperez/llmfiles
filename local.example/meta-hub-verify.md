# Hub verify

Optional. Loaded by `~/llmfiles/shared/meta-hub.md` when a run sits in a hub. Describe how
to run the hub's shared local stack on one run's worktree instead of the main clones:

1. Which apps the stack serves, where it lives, and why only one run can use it at once.
   The run holds the `/fullsend` verify lock for the whole recipe.
2. How to point an app at the worktree, for example a Compose override file written
   outside the repo that replaces the app's source bind mount.
3. The command that recreates the app on that source, and how to tell it is serving.
4. A check that the app serves the worktree's code before testing.
5. Known traps and which of them need the user.
6. How to put the stack back on the main clones, also on failure.
