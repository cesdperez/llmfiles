---
name: grafana-k6
description: Load testing with Grafana k6. Use when writing k6 scripts, creating load tests, configuring scenarios, working with virtual users, thresholds, checks, executors, or when the user mentions k6, load testing, performance testing, stress testing, or k6 scenarios.
---

# Grafana k6

## Overview

k6 is a Go-based CLI tool that executes JavaScript ES modules for load testing. It is **not** Node.js — no `package.json`, no npm, no TypeScript, no bundler. All files are plain `.js` using ES module syntax.

## Key Patterns

### File Structure

```
load-tests/
├── load-test.js          # Entry point; exports all scenario functions + options
├── playground.js         # Manual single-VU exploratory runs
├── options/
│   ├── index.js          # Maps profile key → options object
│   └── avg-load.js       # Each profile exports `k6Options`
└── requests/             # One file per endpoint; each exports one function
    └── get-example.js
```

### Request Function Pattern

Each `requests/` file exports exactly one function:

```js
import http from 'k6/http';
import { check } from 'k6';

export function getExample(baseUrl, token) {
    const headers = {
        headers: {
            'Content-Type': 'application/json',
            'accept': 'application/json',
            'authorization': `Bearer ${token}`,
        },
    };

    const response = http.get(`${baseUrl}/api/example`, headers);
    check(response, {
        [`GET api/example response status was 200`]: (r) => r.status === 200,
    });

    const data = response.json();
    check(data, {
        [`GET api/example response has non empty json`]: () => !!data,
    });

    return data;
}
```

**`check()` label conventions:**
- Status: `` `{METHOD} {path} response status was {code}` ``
- Body: `` `{METHOD} {path} response has non empty {thing}` ``
- Use template literals; use the URL path without base URL or leading slash.

### Scenario / Options Pattern

Options files export `k6Options` with `userAgent` and `scenarios`. Use `constant-arrival-rate` for rate-based load:

```js
// options/avg-load.js
let duration = __ENV.DURATION ? __ENV.DURATION : '10s';
let preAllocatedVUs = __ENV.PRE_ALLOCATED_VUS ? __ENV.PRE_ALLOCATED_VUS : 1;
let maxVUs = __ENV.MAX_VUS ? __ENV.MAX_VUS : 10;

export const k6Options = {
    userAgent: 'k6_load_tests/1.0',
    scenarios: {
        get_example: {                          // snake_case key
            exec: 'getExampleScenario',         // camelCase + "Scenario"
            executor: 'constant-arrival-rate',
            rate: 50,
            timeUnit: '10s',
            duration: duration,
            preAllocatedVUs: preAllocatedVUs,
            maxVUs: maxVUs,
        },
    },
};
```

### Entry Point Pattern

`load-test.js` — validates env vars at module scope, exports `setup()` + scenario functions:

```js
import { fail } from 'k6';
import { getExample } from './requests/get-example.js';
import { optionsMap } from './options/index.js';

let baseUrl = __ENV.BASE_URL ? __ENV.BASE_URL : fail('BASE_URL is not set');
let username = __ENV.USERNAME ? __ENV.USERNAME : fail('USERNAME is not set');
let password = __ENV.PASSWORD ? __ENV.PASSWORD : fail('PASSWORD is not set');

const selectedOption = __ENV.K6_OPTIONS || 'avg-load-noghcc';
if (!optionsMap[selectedOption]) {
  fail(`Invalid K6_OPTIONS value: ${selectedOption}`);
}

export const options = optionsMap[selectedOption];

export function setup() {
    const token = postToken(baseUrl, username, password);
    return { token };
}

export function getExampleScenario(data) {
    getExample(baseUrl, data.token);
}
```

### Options Index Pattern

```js
// options/index.js
import { k6Options as avgLoadNoGhcc } from './avg-load-noghcc.js';
import { k6Options as avgLoad } from './avg-load.js';

export const optionsMap = {
    'avg-load-noghcc': avgLoadNoGhcc,
    'avg-load': avgLoad,
};
```

### Naming Conventions

| Scope | Convention | Example |
|-------|-----------|---------|
| Files | `kebab-case` | `post-token.js`, `avg-load-noghcc.js` |
| Request files | `{method}-{endpoint}.js` | `put-websession2.js` |
| Exported functions | `camelCase` | `postToken`, `getCourseContent` |
| Request functions | `{httpMethod}{ResourceName}` | `postGhccStartActivity` |
| Scenario wrappers | `{requestFn}Scenario` | `postGhccStartActivityScenario` |
| k6 scenario keys | `snake_case` | `get_websession2`, `put_websession2` |
| Options export | `k6Options` | always named `k6Options` in options files |

### Variable Declarations

- `let` for module-level env-derived variables (runtime-determined)
- `const` for local request data: payloads, headers, responses

### Imports

- k6 built-ins use bare specifiers: `import http from 'k6/http'`
- Local imports use relative paths with `.js` extension: `import { postToken } from './requests/post-token.js'`
- No npm packages

## Commands

### Run full load test

```sh
k6 run \
  -e BASE_URL='https://api.example.com' \
  -e USERNAME='user' \
  -e PASSWORD='pass' \
  -e K6_OPTIONS='avg-load-noghcc' \
  -e DURATION='30s' \
  load-test.js
```

### Smoke run (single VU)

```sh
k6 run \
  -e BASE_URL='https://api.example.com' \
  -e USERNAME='user' \
  -e PASSWORD='pass' \
  playground.js
```

### Output to JSON

```sh
k6 run --out json=results.json load-test.js
```

### Output to InfluxDB / Grafana Cloud

```sh
k6 run --out influxdb=http://localhost:8086/k6 load-test.js
k6 run --out cloud load-test.js   # Grafana Cloud k6
```

## Common Tasks

### Add a New Endpoint

1. Create `requests/{method}-{endpoint}.js` following the request function pattern.
2. Export one function named `{httpMethod}{ResourceName}`.
3. Import it in `load-test.js`, wrap in `{fn}Scenario`.
4. Add scenario to relevant options file(s) with a `snake_case` key.
5. Register in `options/index.js` if a new profile is needed.

### Configure Thresholds (Pass/Fail Criteria)

```js
export const options = {
    thresholds: {
        http_req_failed: ['rate<0.01'],        // error rate < 1%
        http_req_duration: ['p(95)<200'],       // 95th percentile < 200ms
    },
    scenarios: { /* ... */ },
};
```

k6 returns a non-zero exit code when thresholds fail — required for CI automation.

### Data Parameterization with SharedArray

```js
import { SharedArray } from 'k6/data';

const users = new SharedArray('users', function () {
    return JSON.parse(open('./users.json')).users;
});

export default function () {
    const user = users[Math.floor(Math.random() * users.length)];
    // use user.username, user.password, etc.
}
```

`SharedArray` is memory-efficient — data is loaded once and shared across all VUs.

## Executors Reference

| Executor | Use case |
|----------|----------|
| `constant-vus` | Fixed concurrent users for a duration |
| `ramping-vus` | Ramp users up/down through stages |
| `constant-arrival-rate` | Fixed req/s target regardless of response time |
| `ramping-arrival-rate` | Ramp req/s up/down through stages |
| `shared-iterations` | Total iterations shared across all VUs |
| `per-vu-iterations` | Each VU runs N iterations |

**Arrival-rate executors = open model** (iterations start independently of system response).
**VU executors = closed model** (next iteration waits for previous to finish).

For API load testing, prefer arrival-rate executors to model real-world throughput.

**Do not use `sleep()` at the end of arrival-rate iterations** — the executor controls pacing via `rate`/`timeUnit`.

## Test Lifecycle

```
init code      → runs once per VU (module scope)
setup()        → runs once before all VUs start; return value passed to scenarios as `data`
default/scenarios → runs per VU iteration
teardown(data) → runs once after all VUs finish
```

- `setup()` is ideal for auth token acquisition
- Module-scope `fail()` aborts before any VU starts — use for env var validation
- `fail()` inside a VU function aborts only that VU's iteration

## Pitfalls to Avoid

1. **Don't `import fail` unless used** — k6 will error if you import unused symbols that affect the init phase.

2. **Don't use `try/catch` or `throw`** — use `check()` for soft assertions. k6 handles VU-level panics internally.

3. **Don't `fail()` inside request functions** — use `check()` only. `fail()` is for module-scope startup validation.

4. **Don't forget `.js` extension on local imports** — k6 doesn't use Node.js module resolution: `'./requests/get-auth.js'` not `'./requests/get-auth'`.

5. **Don't run `sleep()` in arrival-rate executors** — the executor already paces iterations. Adding sleep distorts throughput.

6. **Don't use `__ENV` values directly as numbers** — they come in as strings: `parseInt(__ENV.MAX_VUS) || 10` or use ternary pattern.

7. **SharedArray must be initialized at module scope (init phase)** — not inside `default` or scenario functions.

## Quick Reference

```js
// Core imports
import http from 'k6/http';
import { check, sleep, fail, group } from 'k6';
import { SharedArray } from 'k6/data';
import { Trend, Counter, Gauge, Rate } from 'k6/metrics';

// HTTP methods
http.get(url, params)
http.post(url, body, params)
http.put(url, body, params)
http.patch(url, body, params)
http.del(url, body, params)

// Batch requests
http.batch([
    ['GET', 'https://example.com/api/1'],
    ['GET', 'https://example.com/api/2'],
])

// Custom metrics
const myTrend = new Trend('my_metric');
myTrend.add(response.timings.duration);

// URL grouping (avoids per-ID metric explosion)
http.get(`${baseUrl}/items/${id}`, { tags: { name: 'GET /items/:id' } });

// Key built-in metrics
// http_req_duration     — request latency
// http_req_failed       — error rate
// http_reqs             — total requests
// iterations            — total iterations
// vus                   — active VUs
```

### Env var pattern

```js
// Module scope — fail fast if missing
let baseUrl = __ENV.BASE_URL ? __ENV.BASE_URL : fail('BASE_URL is not set');

// With default fallback
let duration = __ENV.DURATION || '10s';
```
