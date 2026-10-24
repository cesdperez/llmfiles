---
name: intervals-icu
description: Interact with the intervals.icu training platform API. Use when fetching activity history, cycling/running totals, workout library, race calendar, fitness chart (CTL/ATL/TSB), FTP/zones, wellness data, or when the user asks about their training, fitness, races, workouts, or intervals.icu data.
---

# Intervals.icu API

REST API for the intervals.icu training platform. Manage activities, workouts, calendar events, athlete profile, and fitness metrics.

## Auth & Base URL

```
Base URL: https://intervals.icu
Auth: HTTP Basic with username: API_KEY, password: $INTERVALS_API_KEY
Athlete ID shortcut: use 0 or $INTERVALS_ATHLETE_ID
```

```bash
# Always source env vars first
source ~/.zshrc

# Base curl pattern
curl -s -u "API_KEY:$INTERVALS_API_KEY" \
  "https://intervals.icu/api/v1/athlete/$INTERVALS_ATHLETE_ID/..."
```

## References

- Read `~/llmfiles/skills/intervals-icu/references/api.md` when you need an endpoint or field not shown below: single activity, creating/uploading/updating/deleting activities, power curves, athlete profile, FTP/zones/sport settings, wellness ranges or updates, or field units.
- Read `~/llmfiles/skills/intervals-icu/references/calendar-and-workouts.md` when creating, updating, or deleting calendar events or races, planning workouts, writing workout descriptions, or using the workout library.

## Common Queries

### "How much did I cycle this year?"

No `/stats` or `/totals` endpoint exists (both 404). Aggregate the activities list client-side by type.

```bash
source ~/.zshrc
curl -s -u "API_KEY:$INTERVALS_API_KEY" \
  "https://intervals.icu/api/v1/athlete/$INTERVALS_ATHLETE_ID/activities?oldest=$(date +%Y)-01-01&newest=$(date +%Y-%m-%d)" \
  | jq '[.[] | select(.type == "Ride" or .type == "VirtualRide")] |
    { count: length,
      total_km: (map(.distance) | add) / 1000,
      total_hours: (map(.moving_time) | add) / 3600,
      total_tss: (map(.icu_training_load // 0) | add) }'
```

### "What's my current fitness (CTL/ATL/TSB)?"

```bash
source ~/.zshrc
curl -s -u "API_KEY:$INTERVALS_API_KEY" \
  "https://intervals.icu/api/v1/athlete/$INTERVALS_ATHLETE_ID/wellness/$(date +%Y-%m-%d)" \
  | jq '{ date: .id, ctl, atl, tsb: (.ctl - .atl), ramp_rate: .rampRate }'
```

TSB has no field. Compute `ctl - atl` (positive = fresh, negative = fatigued).

### "Summarize my recent activities"

```bash
source ~/.zshrc
curl -s -u "API_KEY:$INTERVALS_API_KEY" \
  "https://intervals.icu/api/v1/athlete/$INTERVALS_ATHLETE_ID/activities?oldest=2026-05-01&newest=2026-05-26&limit=50" \
  > /tmp/activities.json

jq '[.[] | {
  name,
  type,
  date: .start_date_local[:10],
  dist_km: (if .distance != null then (.distance / 1000 * 10 | round) / 10 else null end),
  dur_min: (.moving_time / 60 | round),
  tss: .icu_training_load,
  avg_hr: .average_heartrate
}]' /tmp/activities.json
```

### "When is my next race?"

```bash
source ~/.zshrc
curl -s -u "API_KEY:$INTERVALS_API_KEY" \
  "https://intervals.icu/api/v1/athlete/$INTERVALS_ATHLETE_ID/events?oldest=$(date +%Y-%m-%d)&newest=$(date -v+1y +%Y-%m-%d)" \
  | jq '[.[] | select(.category | startswith("RACE"))] | sort_by(.start_date_local) | first |
    { name: .name, date: .start_date_local, type: .type, description: .description }'
```

## Activity Types

`Ride`, `VirtualRide`, `EMountainBikeRide`, `Run`, `Walk`, `Swim`, `WeightTraining`, `Hike`, `Yoga`, `Workout`, `Rowing`, `Transition`

- `EMountainBikeRide`: e-MTB rides, different bike, exclude from road cycling totals
- `Transition`: triathlon T1/T2, negligible distance, not a cycling type
- Triathlon bike legs are recorded as `Ride` and already included in cycling totals

## Pitfalls

- **Date format**: `oldest`/`newest` params = `YYYY-MM-DD`; event `start_date_local` = `YYYY-MM-DDTHH:MM:SS` (no timezone suffix)
- **Distance in meters**: always divide by 1000 for km
- **Wellness vs activities**: fitness chart data (CTL/ATL) lives in `/wellness`, not `/activities`
- **macOS date**: use `date -v+1y` not `date --date="+1 year"` (GNU syntax)
- **jq null safety**: use `// 0` for fields that may be null (e.g. `icu_training_load // 0`)
- **Athlete ID 0**: works as shortcut for your own data in most endpoints
- **No server-side type filtering**: `?type=Ride` is silently ignored; always filter client-side with jq
- **jq arithmetic after pipe**: `| * 10` is invalid jq. The dot is implicit in filters but NOT in math operators. Use `| . * 10` or restructure: `(.distance / 1000 * 10 | round) / 10`, never `(.distance / 1000 | * 10 | round / 10)`
- **Pagination required for large date ranges**: API caps at ~500 results per request; if `length == 500`, the results are truncated. Paginate by using the oldest `start_date_local` in the batch as `newest` for the next request, then `unique_by(.id)` when merging
- **Save responses to files before jq**: activity responses are large, and piping them through shell variables causes control character parse errors in jq; use `curl ... > /tmp/batch.json` and pass files directly to jq
- **Indoor vs outdoor**: use `type == "VirtualRide"`, not power presence, to identify indoor trainer rides; `icu_weighted_avg_watts` can be non-null on some `Ride` activities
- **VirtualRide distance is unreliable**: the UI may show different values (pulls from Garmin Connect as a secondary source with different virtual distance calculation); don't use VirtualRide distance for precision calculations
- **HTTP/2 POST bug (macOS curl)**: `curl` on macOS silently drops POST body over HTTP/2, returning `{"error":"JSON parse error"}`. Always use `--http1.1` for POST requests. GET/PUT are not affected.
- **Race category format**: use `RACE_A`/`RACE_B`/`RACE_C`, not `RACE`, because the latter doesn't work; when querying for races, filter with `.category | startswith("RACE")`
