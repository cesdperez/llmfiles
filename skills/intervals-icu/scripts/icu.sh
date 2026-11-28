#!/bin/bash
# Compact read-only reports so a coaching question needs one tool call.
# Usage:
#   icu.sh session [DAYS_BACK=14] [DAYS_AHEAD=14]
#   icu.sh totals OLDEST NEWEST          (YYYY-MM-DD, inclusive)
#   icu.sh plan-vs-actual [DAYS_BACK=14] [ACTIVITY_ID]
set -euo pipefail

if [[ -z "${INTERVALS_API_KEY:-}" || -z "${INTERVALS_ATHLETE_ID:-}" ]]; then
  # ~/.zshrc is zsh syntax, so read the vars through zsh instead of sourcing it here.
  INTERVALS_API_KEY=$(zsh -c 'source ~/.zshrc >/dev/null 2>&1; print -r -- "$INTERVALS_API_KEY"')
  INTERVALS_ATHLETE_ID=$(zsh -c 'source ~/.zshrc >/dev/null 2>&1; print -r -- "$INTERVALS_ATHLETE_ID"')
fi
: "${INTERVALS_API_KEY:?missing}" "${INTERVALS_ATHLETE_ID:?missing}"

API="https://intervals.icu/api/v1"
ATHLETE="$API/athlete/$INTERVALS_ATHLETE_ID"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# Key goes through stdin config, not argv, so it never shows in ps.
get() {
  printf 'user = "API_KEY:%s"\n' "$INTERVALS_API_KEY" | curl -sf -K - "$1" > "$2"
}

day() { date -v"$1"d +%Y-%m-%d; }

ACT_ROW='[.start_date_local[:10], .id, .type, .name,
  (if .distance then (.distance/10|round)/100 else "-" end),
  ((.moving_time//0)/60*10|round/10),
  (.icu_training_load // "-"), (.average_heartrate // "-"), (.paired_event_id // "-")] | @tsv'

session() {
  local back=${1:-14} ahead=${2:-14} today
  today=$(date +%Y-%m-%d)
  get "$ATHLETE/wellness/$today" "$TMP/w.json"
  get "$ATHLETE/activities?oldest=$(day "-$back")&newest=$today&limit=500" "$TMP/a.json"
  get "$ATHLETE/events?oldest=$today&newest=$(day "+$ahead")" "$TMP/e.json"

  echo "# wellness $today"
  jq -r '"ctl=\(.ctl*100|round/100) atl=\(.atl*100|round/100) tsb=\(((.ctl//0)-(.atl//0))*100|round/100) ramp=\(.rampRate*100|round/100) rhr=\(.restingHR) hrv=\(.hrv) weight=\(.weight) sleep_h=\(if .sleepSecs then (.sleepSecs/36|round/100) else null end) sleep_score=\(.sleepScore)"' "$TMP/w.json"
  echo "# activities $(day "-$back")..$today"
  echo "date	id	type	name	km	moving_min	load	avg_hr	paired_event"
  jq -r "sort_by(.start_date_local)[] | $ACT_ROW" "$TMP/a.json"
  echo "# events $today..$(day "+$ahead")"
  echo "date	id	category	type	name	planned_min	planned_load	paired_activity"
  jq -r 'sort_by(.start_date_local)[] | [.start_date_local[:10], .id, .category, (.type // "-"), .name,
    (if .moving_time then .moving_time/60|round else "-" end), (.icu_training_load // "-"), (.paired_activity_id // "-")] | @tsv' "$TMP/e.json"
}

totals() {
  local oldest=${1:?OLDEST} newest=${2:?NEWEST}
  get "$ATHLETE/activities?oldest=$oldest&newest=$newest&limit=500" "$TMP/a.json"
  echo "# totals $oldest..$newest"
  echo "type	count	km	moving_h	load"
  jq -r 'def row: [length, ((map(.distance//0)|add)/100|round/10), ((map(.moving_time//0)|add)/36|round/100), (map(.icu_training_load//0)|add)];
    (group_by(.type)[] | [.[0].type] + row | @tsv), (["TOTAL"] + row | @tsv)' "$TMP/a.json"
}

plan_vs_actual() {
  local back=${1:-14} id=${2:-} today
  today=$(date +%Y-%m-%d)
  if [[ -z "$id" ]]; then
    get "$ATHLETE/activities?oldest=$(day "-$back")&newest=$today&limit=500" "$TMP/a.json"
    id=$(jq -r '[.[] | select(.paired_event_id)] | sort_by(.start_date_local) | last | .id // empty' "$TMP/a.json")
    [[ -n "$id" ]] || id=$(jq -r '[.[] | select(.type=="Run")] | sort_by(.start_date_local) | last | .id // empty' "$TMP/a.json")
    [[ -n "$id" ]] || { echo "no activity found in last $back days"; return 0; }
  fi
  get "$API/activity/$id?intervals=true" "$TMP/act.json"
  local ev
  ev=$(jq -r '.paired_event_id // empty' "$TMP/act.json")

  echo "# actual $id"
  jq -r '"date=\(.start_date_local) type=\(.type) name=\(.name) km=\((.distance//0)/10|round/100) moving=\(.moving_time)s elapsed=\(.elapsed_time)s load=\(.icu_training_load) avg_hr=\(.average_heartrate) max_hr=\(.max_heartrate) compliance=\(.compliance)"' "$TMP/act.json"
  echo "# intervals"
  echo "type	label	moving_s	km	avg_hr	avg_speed_ms"
  jq -r '.icu_intervals[]? | [.type, (.label // "-"), .moving_time, ((.distance//0)/10|round/100), (.average_heartrate // "-"), ((.average_speed//0)*100|round/100)] | @tsv' "$TMP/act.json"

  if [[ -z "$ev" ]]; then echo "# planned: none paired"; return 0; fi
  get "$ATHLETE/events/$ev" "$TMP/ev.json"
  echo "# planned $ev"
  jq -r '"date=\(.start_date_local) name=\(.name) moving=\(.moving_time)s km=\((.distance//0)/10|round/100) load=\(.icu_training_load)"' "$TMP/ev.json"
  echo "# planned steps"
  jq -r '.description // empty' "$TMP/ev.json"
}

case "${1:-}" in
  session) shift; session "$@" ;;
  totals) shift; totals "$@" ;;
  plan-vs-actual) shift; plan_vs_actual "$@" ;;
  *) sed -n '2,6p' "$0" >&2; exit 2 ;;
esac
