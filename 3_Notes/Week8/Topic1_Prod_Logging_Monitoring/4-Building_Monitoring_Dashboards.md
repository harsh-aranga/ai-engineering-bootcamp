# Note 4: Building Monitoring Dashboards

## Purpose of Dashboards: At-a-Glance System Health

A monitoring dashboard answers one question: **Is the system healthy right now?**

You glance at it and know within seconds:

- Are requests flowing normally?
- Is latency acceptable?
- Are errors spiking?
- Are we burning through budget?

Dashboards are not for deep investigation — that's what logs and traces are for. Dashboards are the **early warning system** that tells you something is wrong, so you know when to dig deeper.

**The mental model:**

```
Dashboard          →  "Something's wrong with latency"
  ↓
Metrics query      →  "p95 spiked at 10:45 AM for web_search queries"
  ↓
Logs investigation →  "RateLimitError from search API"
  ↓
Trace inspection   →  "Single request shows 47 search API calls"
```

The dashboard is layer one. It doesn't tell you the root cause — it tells you there's a problem worth investigating.

---

## Key Dashboard Panels for LLM Systems

An LLM monitoring dashboard should have these core panels:

### 1. Request Rate Over Time

**What it shows:** How many requests per second the system is handling.

**Why it matters:**

- Sudden drop = something is broken (users can't reach you)
- Sudden spike = traffic surge (may cause latency/errors)
- Expected pattern = normal daily/weekly usage

**PromQL:**

```promql
# Requests per second, summed across all statuses and query types
sum(rate(llm_requests_total[5m]))

# Requests per second, broken down by query type
sum by (query_type) (rate(llm_requests_total[5m]))
```

**Visualization:** Time series line chart.

---

### 2. Error Rate Over Time

**What it shows:** Percentage of requests that failed.

**Why it matters:**

- Baseline should be < 1% for healthy systems
- Spike above 5% = immediate investigation
- Trending upward = degradation (even if not alarming yet)

**PromQL:**

```promql
# Error rate as a percentage
sum(rate(llm_requests_total{status="error"}[5m])) 
/ 
sum(rate(llm_requests_total[5m])) 
* 100

# Error rate by query type (which type is failing?)
sum by (query_type) (rate(llm_requests_total{status="error"}[5m])) 
/ 
sum by (query_type) (rate(llm_requests_total[5m])) 
* 100
```

**Visualization:** Time series line chart with threshold lines (green < 1%, yellow 1-5%, red > 5%).

---

### 3. Latency Percentiles Over Time (p50, p95, p99)

**What it shows:** How long requests take, across the distribution.

**Why it matters:**

- **p50 (median):** Typical user experience
- **p95:** What 95% of users experience — your SLO target
- **p99:** Worst-case (excluding extreme outliers)

If p50 is fine but p95 is terrible, you have a tail latency problem — most requests are fast, but some are very slow.

**PromQL:**

```promql
# p50 latency
histogram_quantile(0.50, sum by (le) (rate(llm_request_latency_seconds_bucket[5m])))

# p95 latency
histogram_quantile(0.95, sum by (le) (rate(llm_request_latency_seconds_bucket[5m])))

# p99 latency
histogram_quantile(0.99, sum by (le) (rate(llm_request_latency_seconds_bucket[5m])))

# p95 latency by query type (which type is slowest?)
histogram_quantile(0.95, sum by (query_type, le) (rate(llm_request_latency_seconds_bucket[5m])))
```

**Visualization:** Time series with all three percentiles overlaid. Include SLO threshold line (e.g., horizontal line at 5s if SLO is "p95 < 5s").

---

### 4. Token Usage Over Time

**What it shows:** Token consumption rate (input and output).

**Why it matters:**

- Token usage = cost driver
- Sudden spike = prompt injection, runaway agent, or bug
- Useful for capacity planning

**PromQL:**

```promql
# Tokens per minute, by direction
sum by (direction) (rate(llm_tokens_total[5m])) * 60

# Tokens per minute, by model
sum by (model) (rate(llm_tokens_total[5m])) * 60

# Total tokens per minute
sum(rate(llm_tokens_total[5m])) * 60
```

**Visualization:** Stacked area chart (input vs. output tokens).

---

### 5. Cost Accumulation (Daily, Hourly)

**What it shows:** How much money you're spending.

**Why it matters:**

- Budget tracking
- Cost anomaly detection
- Per-model cost comparison

**PromQL:**

```promql
# Cost rate (USD per hour)
sum(rate(llm_cost_usd_total[1h])) * 3600

# Cumulative cost today (requires recording rule or clever query)
# Simplest: just show the counter value (total since start)
sum(llm_cost_usd_total)

# Cost by model
sum by (model) (llm_cost_usd_total)
```

**Visualization:**

- Stat panel showing today's total cost
- Time series showing cost rate over time
- Pie chart showing cost by model

---

### 6. Active Requests (Current Load)

**What it shows:** How many requests are currently being processed.

**Why it matters:**

- Capacity indicator
- Stuck requests = this number stays high
- Useful for understanding concurrency

**PromQL:**

```promql
# Current active requests
llm_active_requests

# Or if you have per-instance:
sum(llm_active_requests)
```

**Visualization:** Gauge or stat panel showing current value.

---

## Breakdowns: Slicing by Dimensions

Beyond the totals, you need to answer: **Where is the problem?**

### By Query Type

"Which types of queries are slowest or most expensive?"

```promql
# p95 latency by query type
histogram_quantile(0.95, sum by (query_type, le) (rate(llm_request_latency_seconds_bucket[5m])))

# Error rate by query type
sum by (query_type) (rate(llm_requests_total{status="error"}[5m])) 
/ 
sum by (query_type) (rate(llm_requests_total[5m]))

# Token usage by query type
sum by (query_type) (rate(llm_tokens_total[5m]))
```

**Use case:** "web_search queries are 3x slower than internal_docs — is that expected?"

### By Model

"How is cost distributed across models?"

```promql
# Cost by model
sum by (model) (llm_cost_usd_total)

# Requests by model
sum by (model) (rate(llm_requests_total[5m]))

# Tokens by model
sum by (model, direction) (rate(llm_tokens_total[5m]))
```

**Use case:** "We're spending 80% of budget on GPT-4o. Should we route more to GPT-4o-mini?"

### By Status

"What's succeeding vs. failing?"

```promql
# Request rate by status
sum by (status) (rate(llm_requests_total[5m]))

# Success rate over time
sum(rate(llm_requests_total{status="success"}[5m])) 
/ 
sum(rate(llm_requests_total[5m]))
```

**Use case:** "Errors jumped from 0.5% to 4% at 10:45 AM."

---

## Grafana Basics

Grafana is the standard visualization tool for Prometheus metrics. Here's how to set it up.

### Connecting Prometheus as a Data Source

1. Open Grafana (default: `http://localhost:3000`, login `admin/admin`)
2. Go to **Configuration** (gear icon) → **Data Sources**
3. Click **Add data source** → Select **Prometheus**
4. Enter your Prometheus URL:
    - Local: `http://localhost:9090`
    - Docker Compose: `http://prometheus:9090`
5. Click **Save & Test**

Reference: [Grafana Prometheus data source documentation](https://grafana.com/docs/grafana/latest/datasources/prometheus/configure/)

### Creating a Dashboard

1. **Dashboards** → **New Dashboard**
2. Click **Add visualization**
3. Select your Prometheus data source
4. Enter your PromQL query
5. Configure visualization options (chart type, legend, thresholds)
6. Click **Apply** to add the panel
7. **Save dashboard** (disk icon)

### The Query Editor

Grafana offers two modes:

- **Builder mode:** Visual query builder (good for learning)
- **Code mode:** Raw PromQL (use this for complex queries)

Key options:

- **Legend:** How the series appears in the legend (use `{{label_name}}` for label values)
- **Format:** Time series (default), Table, or Heatmap
- **Min step:** Controls query resolution

### Time Range Selection

Top-right corner of dashboard:

- Quick ranges: Last 5m, 15m, 1h, 6h, 24h, 7d
- Custom range: Click to select specific start/end
- Auto-refresh: Set refresh interval (e.g., 30s)

For on-call dashboards, use "Last 1h" with 30s refresh. For daily reviews, use "Last 24h."

---

## Dashboard Design Principles

### 1. Most Important Metrics at Top

Layout your dashboard in order of "how quickly do I need to see this?"

```
┌─────────────────────────────────────────────────────────────┐
│  ROW 1: CRITICAL HEALTH (Error Rate, p95 Latency, Active)   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Requests │ │  Errors  │ │p95 Latency│ │ Active  │       │
│  │  /sec    │ │   Rate   │ │  (sec)   │ │Requests │       │
│  │   142    │ │   1.2%   │ │   2.3    │ │    8    │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────┤
│  ROW 2: TRENDS (Time series charts)                         │
│  ┌─────────────────────────┐ ┌─────────────────────────┐    │
│  │    Request Rate         │ │    Error Rate           │    │
│  │    [chart over time]    │ │    [chart over time]    │    │
│  └─────────────────────────┘ └─────────────────────────┘    │
│  ┌─────────────────────────┐ ┌─────────────────────────┐    │
│  │  Latency Percentiles    │ │    Token Usage          │    │
│  │  [p50, p95, p99]        │ │    [input, output]      │    │
│  └─────────────────────────┘ └─────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  ROW 3: BREAKDOWNS (By dimension)                           │
│  ┌─────────────────────────┐ ┌─────────────────────────┐    │
│  │  Latency by Query Type  │ │   Cost by Model         │    │
│  └─────────────────────────┘ └─────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  ROW 4: COSTS                                               │
│  ┌──────────┐ ┌─────────────────────────────────────┐       │
│  │Today's   │ │    Cost Over Time                    │       │
│  │Cost: $12 │ │    [chart with daily trend]          │       │
│  └──────────┘ └─────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 2. Red/Yellow/Green Thresholds

Configure visual thresholds so status is obvious at a glance:

**Error Rate:**

- Green: < 1%
- Yellow: 1-5%
- Red: > 5%

**p95 Latency:**

- Green: < 3s (or your SLO)
- Yellow: 3-5s
- Red: > 5s

**Active Requests:**

- Green: < 80% of capacity
- Yellow: 80-95%
- Red: > 95%

In Grafana, set these in the panel's **Thresholds** settings.

### 3. Drill-Down Capability

Your dashboard should support progressive investigation:

**Level 1: Overview**

- Single stat panels: "Error rate is 4%"
- Tells you there's a problem

**Level 2: Time series**

- When did it start? ("Spiked at 10:45")
- Is it getting worse? ("Trending up")

**Level 3: Breakdowns**

- Which query type? ("web_search only")
- Which model? ("All models affected")

**Level 4: Logs/Traces** (link out to other tools)

- Add dashboard links to your log viewer or tracing UI
- In Grafana, use **Data links** to create clickable drill-downs

### 4. Consistent Time Ranges

All panels on a dashboard should respect the same time range. Grafana handles this automatically with the dashboard time picker — don't override with per-panel time ranges unless you have a specific reason (e.g., a "last 7 days" cost panel).

### 5. Avoid Clutter

A dashboard with 50 panels is not a dashboard — it's a wall of noise.

Good dashboard: 8-15 panels, answering specific questions. Bad dashboard: Every metric you have, dumped onto one page.

Separate concerns: Have an "overview" dashboard and "deep dive" dashboards for specific areas (cost, latency, errors).

---

## Essential PromQL Queries Reference

Here's a quick reference for the queries you'll use most often:

### Request Rate

```promql
# Total requests per second
sum(rate(llm_requests_total[5m]))

# By status
sum by (status) (rate(llm_requests_total[5m]))

# By query type
sum by (query_type) (rate(llm_requests_total[5m]))
```

### Error Rate

```promql
# Error rate (0-1)
sum(rate(llm_requests_total{status="error"}[5m])) 
/ 
sum(rate(llm_requests_total[5m]))

# Error rate as percentage (0-100)
sum(rate(llm_requests_total{status="error"}[5m])) 
/ 
sum(rate(llm_requests_total[5m])) 
* 100

# Error rate by query type
sum by (query_type) (rate(llm_requests_total{status="error"}[5m])) 
/ 
sum by (query_type) (rate(llm_requests_total[5m])) 
* 100
```

### Latency Percentiles

```promql
# p50 (median)
histogram_quantile(0.50, sum by (le) (rate(llm_request_latency_seconds_bucket[5m])))

# p95
histogram_quantile(0.95, sum by (le) (rate(llm_request_latency_seconds_bucket[5m])))

# p99
histogram_quantile(0.99, sum by (le) (rate(llm_request_latency_seconds_bucket[5m])))

# p95 by query type
histogram_quantile(0.95, sum by (query_type, le) (rate(llm_request_latency_seconds_bucket[5m])))

# Average latency (not a percentile, but useful)
sum(rate(llm_request_latency_seconds_sum[5m])) 
/ 
sum(rate(llm_request_latency_seconds_count[5m]))
```

### Token Usage

```promql
# Tokens per minute
sum(rate(llm_tokens_total[5m])) * 60

# By direction (input/output)
sum by (direction) (rate(llm_tokens_total[5m])) * 60

# By model
sum by (model) (rate(llm_tokens_total[5m])) * 60
```

### Cost

```promql
# Total cost (since process start)
sum(llm_cost_usd_total)

# Cost rate (USD per hour)
sum(rate(llm_cost_usd_total[1h])) * 3600

# Cost by model
sum by (model) (llm_cost_usd_total)
```

### Active Requests

```promql
# Current active requests
sum(llm_active_requests)
```

---

## PromQL Tips for Dashboards

### Use `$__rate_interval` Instead of Hardcoded Intervals

Grafana provides `$__rate_interval` which automatically calculates the appropriate interval based on your dashboard's time range and scrape interval:

```promql
# Instead of:
rate(llm_requests_total[5m])

# Use:
rate(llm_requests_total[$__rate_interval])
```

This prevents issues where your rate interval is shorter than your scrape interval.

### Label Consistency in Fractions

When dividing metrics, both sides must have the same `by()` clause:

```promql
# CORRECT: Both sides grouped by query_type
sum by (query_type) (rate(llm_requests_total{status="error"}[5m])) 
/ 
sum by (query_type) (rate(llm_requests_total[5m]))

# WRONG: Numerator grouped, denominator not
sum by (query_type) (rate(llm_requests_total{status="error"}[5m])) 
/ 
sum(rate(llm_requests_total[5m]))  # This divides each type by total, giving wrong results
```

### Handling Missing Data

If a label combination has no data (e.g., no errors yet), the query returns nothing — which can break division:

```promql
# Add `or vector(0)` to handle missing data
(
  sum(rate(llm_requests_total{status="error"}[5m])) 
  or vector(0)
) 
/ 
sum(rate(llm_requests_total[5m]))
```

---

## Key Takeaways

1. **Dashboards are for glancing, not investigating.** They tell you something is wrong — logs and traces tell you why.
    
2. **Core panels for LLM systems:** Request rate, error rate, latency percentiles, token usage, cost, active requests.
    
3. **Breakdowns reveal the "where":** Slice by query type, model, and status to localize problems.
    
4. **Design for quick scanning:** Most important metrics at top, thresholds for color-coding, minimal clutter.
    
5. **PromQL patterns to memorize:** `rate()` for counters, `histogram_quantile()` for percentiles, `sum by (label)` for grouping.
    
6. **Link to investigation tools:** Your dashboard should be the starting point that leads to logs and traces.