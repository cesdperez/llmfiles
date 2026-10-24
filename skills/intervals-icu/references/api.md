# Intervals.icu API: Activities, Athlete, Wellness

## Activities

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

# Power curves (includes historical bests)
GET /api/v1/athlete/{id}/power-curves
```

## Athlete Profile & Sport Settings (FTP, Zones)

```bash
# Get profile
GET /api/v1/athlete/{id}

# Get sport settings (FTP, LTHR, zones, threshold pace)
GET /api/v1/athlete/{id}/sport-settings
# Returns array, one entry per sport group:
#   types[]        e.g. ["Ride","VirtualRide","GravelRide"]
#   ftp            cycling FTP in watts
#   indoor_ftp     indoor FTP
#   lthr           lactate threshold HR
#   max_hr
#   threshold_pace m/s (divide into 1000 for pace in sec/km)
#   power_zones[]  % of FTP breakpoints (e.g. [55,75,90,105,120,150,999])
#   hr_zones[]     absolute HR values

# Create/update sport settings
POST /api/v1/athlete/{id}/sport-settings
PUT  /api/v1/athlete/{id}/sport-settings/{settingsId}
```

## Wellness (Fitness Chart CTL/ATL/TSB)

```bash
# Get wellness data (includes CTL, ATL, TSB)
GET /api/v1/athlete/{id}/wellness?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
# Key fields:
#   id        date (YYYY-MM-DD)
#   ctl       chronic training load (fitness), e.g. 39.3
#   ctlLoad   TSS contribution to CTL that day
#   atl       acute training load (fatigue), e.g. 50.4
#   atlLoad   TSS contribution to ATL that day
#   rampRate  weekly CTL change rate
#   restingHR, weight, sleepSecs, sleepScore, mood, hrv
# TSB (form) = ctl - atl (calculate client-side, no dedicated field)

# Single day
GET /api/v1/athlete/{id}/wellness/YYYY-MM-DD

# Update wellness entry
PUT /api/v1/athlete/{id}/wellness/{date}
Body: { "weight": 70.5, "restingHR": 48 }
```

## Data Units

| Field | Unit |
|-------|------|
| `distance` | meters (÷1000 for km) |
| `moving_time` | seconds (÷3600 for hours) |
| `icu_training_load` | TSS (Training Stress Score) |
| `icu_weighted_avg_watts` | watts (normalized power) |
| `ctl` | CTL (chronic training load, fitness) |
| `atl` | ATL (acute training load, fatigue) |
| `ctlLoad` / `atlLoad` | TSS added to CTL/ATL that day |
| TSB | Calculate as `ctl - atl` (positive = fresh, negative = fatigued) |
