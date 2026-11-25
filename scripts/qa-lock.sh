#!/usr/bin/env bash
# The fullsend machine lock: heavy test commands on this machine take turns.
#   qa-lock.sh run <label> -- <command...>   wait, run the command, release; exits with its code
#   qa-lock.sh take <label>                  wait and print a token for a held span (the stage 4 stack)
#   qa-lock.sh touch <token>                 keep a held span fresh, at least every 30 minutes
#   qa-lock.sh release <token>               release a held span
set -u

LOCK="$HOME/.cache/fullsend/qa.lock"
STALE_SECONDS=3600

owner_age() {
  local mtime
  mtime=$(stat -f %m "$LOCK/owner" 2>/dev/null || stat -c %Y "$LOCK/owner" 2>/dev/null) || return 1
  echo $(($(date +%s) - mtime))
}

clear_if_stale() {
  local seen age
  seen=$(cat "$LOCK/owner" 2>/dev/null) || return 0
  age=$(owner_age) || return 0
  # Re-read before removing, so a holder that took the lock meanwhile keeps it.
  if [ "$age" -gt "$STALE_SECONDS" ] && [ "$(cat "$LOCK/owner" 2>/dev/null)" = "$seen" ]; then
    echo "qa-lock: removing a stale lock from a crashed run: $seen" >&2
    rm -rf "$LOCK"
  fi
}

take() {
  local token waited=0
  token="$1 $$ $(date +%s)"
  mkdir -p "$(dirname "$LOCK")"
  until mkdir "$LOCK" 2>/dev/null; do
    [ "$waited" -eq 0 ] && echo "qa-lock: waiting for $(cat "$LOCK/owner" 2>/dev/null || echo 'a run')" >&2
    waited=1
    clear_if_stale
    sleep 15
  done
  echo "$token" > "$LOCK/owner"
  echo "$token"
}

holds() { [ "$(cat "$LOCK/owner" 2>/dev/null)" = "$1" ]; }

release() { holds "$1" && rm -rf "$LOCK"; return 0; }

case "${1:-}" in
  run)
    label="${2:?label}"; shift 2
    [ "${1:-}" = "--" ] && shift
    token=$(take "$label")
    (while sleep 600; do holds "$token" && touch "$LOCK/owner"; done) &
    beat=$!
    trap 'kill "$beat" 2>/dev/null; release "$token"' EXIT INT TERM
    "$@"
    ;;
  take) take "${2:?label}" ;;
  touch) holds "${2:?token}" && touch "$LOCK/owner" ;;
  release) release "${2:?token}" ;;
  *) sed -n '2,7p' "$0" >&2; exit 2 ;;
esac
