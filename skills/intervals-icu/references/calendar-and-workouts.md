# Intervals.icu Calendar, Races, and Workouts

## Events & Race Calendar

```bash
# List events (oldest/newest required)
GET /api/v1/athlete/{id}/events?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
# Key fields: id, name, start_date_local, category, type, description

# Create event/race (see "Add a race" below for the working curl)
POST /api/v1/athlete/{id}/events?upsertOnUid=false
Body: {
  "name": "Race Name",
  "start_date_local": "2026-06-15T00:00:00",
  "category": "RACE_A",      # see Event Categories
  "type": "Run",             # sport type
  "description": "..."
}

# Update event
PUT /api/v1/athlete/{id}/events/{eventId}

# Delete a single event
DELETE /api/v1/athlete/{id}/events/{eventId}

# Delete events in a date range
DELETE /api/v1/athlete/{id}/events?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
```

### Event Categories

`RACE_A`, `RACE_B`, `RACE_C`, `WORKOUT`, `NOTE`, `HOLIDAY`

`RACE_A` is an A-race, `RACE_B` a B-race, `RACE_C` a C-race.

### Add a race

```bash
source ~/.zshrc
curl -s --http1.1 -X POST \
  -u "API_KEY:$INTERVALS_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/event.json \
  "https://intervals.icu/api/v1/athlete/$INTERVALS_ATHLETE_ID/events?upsertOnUid=false"

# /tmp/event.json:
# {"name":"Race Name","start_date_local":"2026-06-15T00:00:00","category":"RACE_A","type":"Ride","description":"..."}
```

- **`upsertOnUid` required for POST /events**: the query param `?upsertOnUid=false` is required when creating events, otherwise you get a 400 JSON parse error
- Use a file (`--data-binary @file`) to avoid shell encoding issues with special characters
- **No Triathlon type**: `Triathlon` is not a valid event/activity type. Use `Ride` for tri races (it's the key leg anyway)

## Plan workouts for next week

1. Fetch recent weeks' activities to understand pattern (type, duration, load)
2. Fetch current CTL/ATL from wellness endpoint
3. Calculate target TSS to achieve +N CTL change
4. POST events with `category: "WORKOUT"` for each planned session

## Workout Event Description Format

Calendar event descriptions use a plain-text block format. Always use percentages. Never use watts or absolute paces.

**Cycling**: intensity as % of FTP.
```
- 10m 65%

4x
- 7m 95-98%
- 1m 65%

- 10m 65%
```

**Running**: intensity as % of threshold pace, with `pace` suffix.
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

## Workout Library

```bash
# List workouts
GET /api/v1/athlete/{id}/workouts

# List folders
GET /api/v1/athlete/{id}/folders

# Create workout
POST /api/v1/athlete/{id}/workouts
# Accepts ZWO, MRC, ERG files or JSON definition
```
