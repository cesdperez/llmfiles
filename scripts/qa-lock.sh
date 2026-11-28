#!/usr/bin/env bash
# The fullsend machine lock: heavy test commands on this machine take turns.
#   qa-lock.sh run <label> -- <command...>   wait, run the command, release; exits with its code
#   qa-lock.sh take <label>                  wait and print a token for a held span (the stage 4 stack)
#   qa-lock.sh touch <token>                 keep a held span fresh, at least every 30 minutes
#   qa-lock.sh release <token>               release a held span; exits 1 when another token holds it
#   qa-lock.sh status                        print the holder, or "free"
# run and take go straight through when their label already holds the lock.
set -u

LOCK="$HOME/.cache/fullsend/qa.lock"
STALE_SECONDS=3600
# A take killed between its mkdir and its owner write leaves a lock nobody names.
ORPHAN_SECONDS=60
POLL_SECONDS=${QA_LOCK_POLL_SECONDS:-15}
BEAT_SECONDS=${QA_LOCK_BEAT_SECONDS:-600}
TOKEN=""
BEAT=""
REENTERED=0

usage() { sed -n '2,8p' "$0" >&2; exit 2; }

age_of() {
  local mtime
  mtime=$(stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null) || return 1
  echo $(($(date +%s) - mtime))
}

owner() { cat "$LOCK/owner" 2>/dev/null; }

label_of() { echo "${1%:*:*}"; }

holds() { [ "$(owner)" = "$1" ]; }

stale_reason() {
  local age pid
  if [ ! -e "$LOCK/owner" ]; then
    age=$(age_of "$LOCK") && [ "$age" -gt "$ORPHAN_SECONDS" ] && echo "a take that died before naming itself"
    return 0
  fi
  pid=$(cat "$LOCK/pid" 2>/dev/null)
  if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
    echo "a run whose process $pid is gone"
    return 0
  fi
  age=$(age_of "$LOCK/owner") && [ "$age" -gt "$STALE_SECONDS" ] && echo "a span untouched for over an hour"
  return 0
}

clear_if_stale() {
  local seen reason
  seen=$(owner)
  reason=$(stale_reason)
  [ -n "$reason" ] || return 0
  # Re-read before removing, so a holder that took the lock meanwhile keeps it.
  [ "$(owner)" = "$seen" ] || return 0
  echo "qa-lock: removing a stale lock from $reason: ${seen:-no owner}" >&2
  rm -rf "$LOCK"
}

# Sets TOKEN, and REENTERED=1 when the label already held the lock.
take() {
  local label pid=${2:-} held announced=""
  label=$(printf '%s' "$1" | tr -c 'A-Za-z0-9._/+@-' '-')
  mkdir -p "$(dirname "$LOCK")"
  until mkdir "$LOCK" 2>/dev/null; do
    held=$(owner)
    if [ -n "$held" ] && [ "$(label_of "$held")" = "$label" ]; then
      touch "$LOCK/owner"
      TOKEN=$held REENTERED=1
      return 0
    fi
    if [ "$held" != "$announced" ]; then
      echo "qa-lock: waiting for ${held:-a run}" >&2
      announced=$held
    fi
    clear_if_stale
    sleep "$POLL_SECONDS"
  done
  TOKEN="$label:$$:$(date +%s)"
  # The pid goes first, so a run is never briefly named without its liveness check.
  [ -n "$pid" ] && echo "$pid" > "$LOCK/pid"
  echo "$TOKEN" > "$LOCK/owner"
}

release() {
  if [ ! -d "$LOCK" ]; then
    echo "qa-lock: not held, nothing to release" >&2
    return 0
  fi
  if holds "$1"; then
    rm -rf "$LOCK"
    return 0
  fi
  echo "qa-lock: held by '$(owner)', not by '$1'. Pass the whole token, quoted." >&2
  return 1
}

touch_span() {
  if holds "$1"; then
    touch "$LOCK/owner"
    return 0
  fi
  echo "qa-lock: held by '$(owner)', not by '$1'. Take the lock again." >&2
  return 1
}

status() {
  local held reason pid
  if [ ! -d "$LOCK" ]; then
    echo "free"
    return 0
  fi
  held=$(owner)
  echo "held by: ${held:-no owner}"
  [ -e "$LOCK/owner" ] && echo "touched: $(age_of "$LOCK/owner")s ago"
  pid=$(cat "$LOCK/pid" 2>/dev/null) && echo "run process: $pid"
  reason=$(stale_reason)
  [ -n "$reason" ] && echo "stale: $reason, the next waiter clears it"
  return 0
}

run_locked() {
  local label=$1
  shift
  take "$label" "$$"
  if [ "$REENTERED" = 1 ]; then
    echo "qa-lock: running under the lock $TOKEN already holds" >&2
    "$@"
    return
  fi
  # Stops when this script dies, so a killed run cannot keep its lock fresh forever. Its
  # sleep outlives a kill, so it must not hold the output open the caller waits on.
  (while sleep "$BEAT_SECONDS" && kill -0 $$ 2>/dev/null; do holds "$TOKEN" && touch "$LOCK/owner"; done) \
    </dev/null >/dev/null 2>&1 &
  BEAT=$!
  trap 'kill "$BEAT" 2>/dev/null; holds "$TOKEN" && rm -rf "$LOCK"' EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  "$@"
}

case "${1:-}" in
  run)
    [ $# -ge 3 ] || usage
    label=$2
    shift 2
    [ "${1:-}" = "--" ] && shift
    [ $# -ge 1 ] || usage
    run_locked "$label" "$@"
    ;;
  take)
    [ $# -eq 2 ] || usage
    take "$2"
    echo "$TOKEN"
    ;;
  touch)
    [ $# -eq 2 ] || usage
    touch_span "$2"
    ;;
  release)
    [ $# -eq 2 ] || usage
    release "$2"
    ;;
  status) status ;;
  *) usage ;;
esac
