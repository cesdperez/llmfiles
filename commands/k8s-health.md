Perform a Kubernetes cluster health scan using the Grafana MCP tools. Do not connect to Kubernetes directly — all data comes from Grafana (Prometheus metrics + Loki logs).

## Setup

**Argument:** `$ARGUMENTS` — must be `dev`, `staging`, or `prod`.

Map to cluster label:
- `dev` → `aws-dev`
- `staging` → `aws-staging`
- `prod` → `aws-prod`

If no argument is provided, ask which environment to scan.

**Grafana datasources:**
- Prometheus: uid `grafanacloud-prom`
- Loki: uid `grafanacloud-logs`

**Time window:** last 7 days. Compute `startRfc3339` as 7 days before now.

**Exclude namespaces in all queries:** `kube-system|monitoring|kube-public|cert-manager|traefik`

---

## Checks

Run each check in order. For each, note findings to include in the final report — do not print intermediate results.

### 1. Non-Running Pods

```promql
kube_pod_status_phase{cluster="<CLUSTER>", phase!~"Running|Succeeded", namespace!~"kube-system|monitoring|kube-public|cert-manager|traefik"} == 1
```

Note each pod with namespace, phase, and start time.

### 2. Waiting Containers

```promql
kube_pod_container_status_waiting_reason{cluster="<CLUSTER>", namespace!~"kube-system|monitoring|kube-public|cert-manager|traefik"} == 1
```

- CRITICAL reasons: `CrashLoopBackOff`, `OOMKilled`, `Error`
- WARNING reasons: `ImagePullBackOff`, `ErrImagePull`, `CreateContainerConfigError`

### 3. Restart Hotspots

```promql
increase(kube_pod_container_status_restarts_total{cluster="<CLUSTER>", namespace!~"kube-system|monitoring|kube-public|cert-manager|traefik"}[7d]) > 3
```

Sort descending. Take the top 10. For each of the **top 3 restarters that are NOT OOMKilled**, pull logs from Loki to find why:

```logql
{cluster="<CLUSTER>", namespace="<NAMESPACE>", app="<APP>"} |~ "(?i)(error|exception|panic|fatal|killed|oom)"
```

Limit 20 lines. Note the error pattern in 1 sentence.

### 4. OOMKilled Containers

```promql
kube_pod_container_status_last_terminated_reason{cluster="<CLUSTER>", reason="OOMKilled", namespace!~"kube-system|monitoring|kube-public|cert-manager|traefik"} == 1
```

For each, fetch peak memory usage and configured limit:

```promql
max_over_time(container_memory_working_set_bytes{cluster="<CLUSTER>", container="<CONTAINER>", namespace="<NAMESPACE>"}[7d])
```

```promql
kube_pod_container_resource_limits{cluster="<CLUSTER>", resource="memory", container="<CONTAINER>", namespace="<NAMESPACE>"}
```

Interpretation:
- Peak ≈ limit → limit too low, suggest raising ~50%
- Peak << limit → likely a memory leak, flag for investigation

Do **not** pull logs for OOMKilled containers.

### 5. Memory Pressure

```promql
(
  max_over_time(container_memory_working_set_bytes{cluster="<CLUSTER>", namespace!~"kube-system|monitoring|kube-public|cert-manager|traefik", container!=""}[1h])
  /
  kube_pod_container_resource_limits{cluster="<CLUSTER>", resource="memory", namespace!~"kube-system|monitoring|kube-public|cert-manager|traefik"}
) > 0.85
```

- >95% → CRITICAL
- >85% → WARNING

### 6. CPU Throttling

```promql
(
  rate(container_cpu_cfs_throttled_periods_total{cluster="<CLUSTER>", namespace!~"kube-system|monitoring|kube-public|cert-manager|traefik", container!=""}[1h])
  /
  rate(container_cpu_cfs_periods_total{cluster="<CLUSTER>", namespace!~"kube-system|monitoring|kube-public|cert-manager|traefik", container!=""}[1h])
) > 0.25
```

- >75% → CRITICAL
- >25% → WARNING

### 7. Node Health

```promql
kube_node_status_condition{cluster="<CLUSTER>", condition="Ready", status!="true"}
```

Any result → CRITICAL.

---

## Output

After all checks are complete, print a single consolidated report:

```
## K8s Health Report — <CLUSTER> — <DATE>
Time window: last 7 days

### CRITICAL
- [category] namespace/name: issue with concrete numbers
  → Action: specific recommended action

### WARNING
- [category] namespace/name: issue with concrete numbers
  → Action: specific recommended action

### INFO
- Notable patterns or trends that don't need immediate action

### Summary
2-3 sentence overall health assessment.
```

Rules:
- Only include sections with actual findings; omit empty sections
- Be specific: include namespace, container name, real numbers (e.g. "peaked at 498Mi vs 512Mi limit")
- If all checks pass, output: "✓ Cluster healthy — no issues detected" with a brief confirmation of what was checked
