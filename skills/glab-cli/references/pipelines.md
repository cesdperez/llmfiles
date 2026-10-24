# CI/CD Pipelines

## Commands

```bash
glab ci view                              # Interactive pipeline view
glab ci list                              # List recent pipelines
glab ci trace <job_id>                    # Stream job logs
glab ci run                               # Trigger new pipeline
glab ci retry <job_id>                    # Retry failed job
glab ci cancel                            # Cancel running pipeline
glab ci lint                              # Validate .gitlab-ci.yml
```

## Polling Status

`glab ci status` returns a snapshot by default. `--live` streams until the pipeline
ends, and `--wait` blocks until completion. Keep `--live=false` explicit when polling
from a script. The text output ends with `Pipeline state: <state>`:

```bash
for i in $(seq 1 60); do
  case "$(glab ci status --live=false 2>/dev/null | awk '/Pipeline state:/{print $3}')" in
    success|failed|canceled) break;;
  esac
  sleep 20
done
glab ci status --live=false | tail -25
```

For structured snapshots, use `glab ci status --output json`, optionally with
`--jq`. JSON output cannot combine with `--live`, `--wait`, or `--compact`.

Bound the loop. `glab ci status` fails outside a git repo (and on any auth or network
error), which prints nothing, matches no state, and turns an `until` into an infinite
spin. The failure mode is a hung command, not an error.

## Reading Failures

**A "failed" pipeline is not always a blocking failure.** Jobs with
`allow_failure: true` show as failed without gating the merge, so read the job list
before reporting a break. `allow_failure` is not in `ci status` output, so get it
from the API:

```bash
glab api "projects/<url_encoded_path>/pipelines/<pipeline_id>/jobs?per_page=100" \
  --paginate --output ndjson | jq -r 'select(.status=="failed") | "\(.name)\tallow_failure=\(.allow_failure)\t\(.id)"'
```

Note the pipeline SHA in `ci status` will not match your pushed commit when merged
results pipelines are enabled: it is the simulated merge commit, not your HEAD.

## Check Pipeline Before Merge

```bash
glab mr view <mr_id> --output json | jq '.pipeline'
# mr list/view also accept a built-in --jq to filter JSON without piping:
glab mr view <mr_id> --output json --jq '.pipeline'
```
