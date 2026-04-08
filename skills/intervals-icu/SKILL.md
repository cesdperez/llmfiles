---
name: intervals-icu
description: Interact with the intervals.icu training platform API. Use when fetching activity history, cycling/running totals, workout library, race calendar, fitness chart (CTL/ATL/TSB), FTP/zones, wellness data, or when the user asks about their training, fitness, races, workouts, or intervals.icu data.
---

# Intervals.icu API

## Overview

REST API for the intervals.icu training platform. Manage activities, workouts, calendar events, athlete profile, and fitness metrics.

## Auth & Base URL

```
Base URL: https://intervals.icu
Auth: HTTP Basic — username: API_KEY, password: $INTERVALS_API_KEY
Athlete ID shortcut: use 0 or $INTERVALS_ATHLETE_ID
```

```bash
# Always source env vars first
source ~/.zshrc

# Base curl pattern
curl -s -u "API_KEY:$INTERVALS_API_KEY" \
  "https://intervals.icu/api/v1/athlete/$INTERVALS_ATHLETE_ID/..."
```

## Core Endpoints

### Activities

```bash
# List activities (with date range)
GET /api/v1/athlete/{id}/activities?oldest=YYYY-MM-DD&newest=YYYY-MM-DD&limit=100

# Key response fields: id, name, type, start_date_local, distance (meters),
# moving_time (seconds), average_heartrate, icu_training_load,
# icu_weighted_avg_watts, icu_atl, icu_ctl

# Get single activity
GET /api/v1/activity/{id}?intervals=true

# Create manual activity
POST /api/v1/athlete/{id}/activities/manual
Body: { "name": "...", "type": "Ride|Run|Swim|...", "start_date_local": "YYYY-MM-DDTHH:MM:SS",
        "moving_time": 3600, "distance": 40000 }

# Upload file (FIT/TCX/GPX)
POST /api/v1/athlete/{id}/activities   (multipart form)

# Update activity
PUT /api/v1/activity/{id}
Body: { "name": "...", "description": "..." }

# Delete activity
DELETE /api/v1/activity/{id}
```

### Athlete Profile & Sport Settings (FTP, Zones)

```bash
# Get profile
GET /api/v1/athlete/{id}

# Get sport settings (FTP, LTHR, zones, threshold pace)
GET /api/v1/athlete/{id}/sport-settings
# Returns array, one entry per sport group:
#   types[]        — e.g. ["Ride","VirtualRide","GravelRide"]
#   ftp            — cycling FTP in watts
#   indoor_ftp     — indoor FTP
#   lthr           — lactate threshold HR
#   max_hr
#   threshold_pace — m/s (divide into 1000 for pace in sec/km)
#   power_zones[]  — % of FTP breakpoints (e.g. [55,75,90,105,120,150,999])
#   hr_zones[]     — absolute HR values

# Create/update sport settings
POST /api/v1/athlete/{id}/sport-settings
PUT  /api/v1/athlete/{id}/sport-settings/{settingsId}
```

### Fitness Chart (CTL/ATL/TSB)

```bash
# Get wellness data (includes CTL, ATL, TSB)
GET /api/v1/athlete/{id}/wellness?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
# Key fields:
#   id        — date (YYYY-MM-DD)
#   ctl       — chronic training load (fitness), e.g. 39.3
#   ctlLoad   — TSS contribution to CTL that day
#   atl       — acute training load (fatigue), e.g. 50.4
#   atlLoad   — TSS contribution to ATL that day
#   rampRate  — weekly CTL change rate
#   restingHR, weight, sleepSecs, sleepScore, mood, hrv
# TSB (form) = ctl - atl (calculate client-side, no dedicated field)

# Single day
GET /api/v1/athlete/{id}/wellness/YYYY-MM-DD

# Update wellness entry
PUT /api/v1/athlete/{id}/wellness/{date}
Body: { "weight": 70.5, "restingHR": 48 }
```

### Historic Totals

```bash
# Activities list with date range — aggregate client-side by sport type
GET /api/v1/athlete/{id}/activities?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
# Sum distance (÷1000 for km), moving_time, icu_training_load by type

# Power curves (includes historical bests)
GET /api/v1/athlete/{id}/power-curves
```

### Events & Race Calendar

```bash
# List events (oldest/newest required)
GET /api/v1/athlete/{id}/events?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
# Key fields: id, name, start_date_local, category, type, description

# Create event/race
POST /api/v1/athlete/{id}/events
Body: {
  "name": "Race Name",
  "start_date_local": "2026-06-15T00:00:00",
  "category": "RACE",        # RACE | WORKOUT | NOTE
  "type": "Run",             # sport type
  "description": "..."
}

# Update event
PUT /api/v1/athlete/{id}/events/{eventId}

# Delete event
DELETE /api/v1/athlete/{id}/events?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
# Or for a single event by id — use PUT with empty body or check specific delete endpoint
```

### Workout Event Description Format

Calendar event descriptions use a plain-text block format. Always use percentages — never watts or absolute paces.

**Cycling** — intensity as % of FTP:
```
- 10m 65%

4x
- 7m 95-98%
- 1m 65%

- 10m 65%
```

**Running** — intensity as % of threshold pace, with `pace` suffix:
```
- 10m 71% pace

8x
- 3m 97-100% pace
- 1m 71% pace

- 10m 71% pace
```

Rules:
- Each line starts with `- `
- Duration in minutes: `{N}m`
- Repetitions: `Nx` on its own line, no indentation
- Blank line between warmup / intervals block / cooldown
- Running uses `% pace` suffix; cycling omits it
- Easy/recovery intensity is typically 65% (cycling) or 71% pace (running)

Real examples from the calendar:

| Session | Description |
|---------|-------------|
| R Q short | `- 10m 65%` / `8x - 3m 97-100% - 1m 65%` / `- 10m 65%` |
| R Q med | `- 10m 65%` / `4x - 7m 95-98% - 1m 65%` / `- 10m 65%` |
| R Q long | `- 10m 65%` / `3x - 10m 93-96% - 1m 65%` / `- 10m 65%` |
| Q short (run) | `- 10m 71% pace` / `8x - 3m 97-100% pace - 1m 71% pace` / `- 10m 71% pace` |
| 3x12 Sweet Spot | `- 15m 65%` / `3x - 12m 88-93% - 4m 65%` / `- 15m 65%` |
| R E | `- 1h 65%` |
| E (run) | `- 40m 71% pace` |
| L (run) | `- 75m 71% pace` |

Note: for durations ≥ 60 min, use `1h`, `1h30m`, etc. instead of `60m`.

### Workout Library

```bash
# List workouts
GET /api/v1/athlete/{id}/workouts

# List folders
GET /api/v1/athlete/{id}/folders

# Create workout
POST /api/v1/athlete/{id}/workouts
# Accepts ZWO, MRC, ERG files or JSON definition
```

## Common Tasks

### "How much did I cycle this year?"

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

### "When is my next race?"

```bash
source ~/.zshrc
curl -s -u "API_KEY:$INTERVALS_API_KEY" \
  "https://intervals.icu/api/v1/athlete/$INTERVALS_ATHLETE_ID/events?oldest=$(date +%Y-%m-%d)&newest=$(date -v+1y +%Y-%m-%d)" \
  | jq '[.[] | select(.category == "RACE")] | sort_by(.start_date_local) | first |
    { name: .name, date: .start_date_local, type: .type, description: .description }'
```

### "Add a race to my calendar"

```bash
source ~/.zshrc
# IMPORTANT: use --http1.1 (HTTP/2 POST silently drops body → "JSON parse error")
# IMPORTANT: upsertOnUid=false is a required query param
curl -s --http1.1 -X POST \
  -u "API_KEY:$INTERVALS_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/event.json \
  "https://intervals.icu/api/v1/athlete/$INTERVALS_ATHLETE_ID/events?upsertOnUid=false"

# /tmp/event.json:
# {"name":"Race Name","start_date_local":"2026-06-15T00:00:00","category":"RACE_A","type":"Ride","description":"..."}
```

Notes:
- Use a file (`--data-binary @file`) to avoid shell encoding issues with special characters
- `Triathlon` is not a valid type — use `Ride` for tri races (it's the key leg anyway)
- Race category variants: `RACE_A` (A-race), `RACE_B` (B-race), `RACE_C` (C-race)
- Delete a single event: `DELETE /api/v1/athlete/{id}/events/{eventId}`

### Plan workouts for next week

1. Fetch recent weeks' activities to understand pattern (type, duration, load)
2. Fetch current CTL/ATL from wellness endpoint
3. Calculate target TSS to achieve +N CTL change
4. POST events with `category: "WORKOUT"` for each planned session

## Data Units & Types

| Field | Unit |
|-------|------|
| `distance` | meters (÷1000 for km) |
| `moving_time` | seconds (÷3600 for hours) |
| `icu_training_load` | TSS (Training Stress Score) |
| `icu_weighted_avg_watts` | watts (normalized power) |
| `ctl` | CTL — chronic training load (fitness) |
| `atl` | ATL — acute training load (fatigue) |
| `ctlLoad` / `atlLoad` | TSS added to CTL/ATL that day |
| TSB | Calculate as `ctl - atl` (positive = fresh, negative = fatigued) |

## Activity Types

`Ride`, `VirtualRide`, `EMountainBikeRide`, `Run`, `Walk`, `Swim`, `WeightTraining`, `Hike`, `Yoga`, `Workout`, `Rowing`, `Transition`

- `EMountainBikeRide` — e-MTB rides; different bike, exclude from road cycling totals
- `Transition` — triathlon T1/T2; negligible distance, not a cycling type
- Triathlon bike legs are recorded as `Ride` and already included in cycling totals

## Event Categories

`RACE_A`, `RACE_B`, `RACE_C`, `WORKOUT`, `NOTE`, `HOLIDAY`

## Pitfalls

- **Date format**: `oldest`/`newest` params = `YYYY-MM-DD`; event `start_date_local` = `YYYY-MM-DDTHH:MM:SS` (no timezone suffix)
- **Distance in meters**: always divide by 1000 for km
- **Wellness vs activities**: fitness chart data (CTL/ATL) lives in `/wellness`, not `/activities`
- **macOS date**: use `date -v+1y` not `date --date="+1 year"` (GNU syntax)
- **jq null safety**: use `// 0` for fields that may be null (e.g. `icu_training_load // 0`)
- **Athlete ID 0**: works as shortcut for your own data in most endpoints
- **No server-side type filtering**: `?type=Ride` is silently ignored; always filter client-side with jq
- **No `/stats` or `/totals` endpoints**: both return 404; all aggregation must be done client-side
- **Pagination required for large date ranges**: API caps at ~500 results per request; if `length == 500`, the results are truncated — paginate by using the oldest `start_date_local` in the batch as `newest` for the next request, then `unique_by(.id)` when merging
- **Save batches to files before merging**: piping large JSON through shell variables causes control character parse errors in jq; use `curl ... > /tmp/batch.json` and pass files directly to jq
- **Indoor vs outdoor**: use `type == "VirtualRide"` — not power presence — to identify indoor trainer rides; `icu_weighted_avg_watts` can be non-null on some `Ride` activities
- **VirtualRide distance is unreliable**: the UI may show different values (pulls from Garmin Connect as a secondary source with different virtual distance calculation); don't use VirtualRide distance for precision calculations
- **HTTP/2 POST bug (macOS curl)**: `curl` on macOS silently drops POST body over HTTP/2, returning `{"error":"JSON parse error"}`. Always use `--http1.1` for POST requests. GET/PUT are not affected.
- **`upsertOnUid` required for POST /events**: the query param `?upsertOnUid=false` is required when creating events, otherwise you get a 400 JSON parse error
- **Race category format**: use `RACE_A`/`RACE_B`/`RACE_C`, not `RACE` — the latter doesn't work; when querying for races, filter with `.category | startswith("RACE")`
- **No Triathlon type**: `Triathlon` is not a valid event/activity type; use `Ride` for tri races
