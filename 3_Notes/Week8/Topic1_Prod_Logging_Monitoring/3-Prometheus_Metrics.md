# Note 3: Prometheus Metrics — Counters, Histograms, and Gauges

## Why Prometheus?

Prometheus is the industry standard for metrics collection and alerting. It's the foundation of most modern observability stacks, from Kubernetes monitoring to custom application metrics.

**Key characteristics:**

- **Pull-based model**: Prometheus scrapes your `/metrics` endpoint on a schedule (typically every 15-30 seconds). Your application exposes metrics; Prometheus pulls them.
- **Time-series database**: Every metric is stored as timestamped values, enabling queries over time.
- **PromQL**: A powerful query language for aggregations, percentiles, rates, and alerts.
- **Ecosystem**: Grafana dashboards, Alertmanager for notifications, exporters for every common system.

For LLM systems, Prometheus gives you:

- Latency percentiles (p50, p95, p99) without storing every request
- Token consumption tracking over time
- Cost accumulation per hour/day/week
- Error rate trends
- All queryable and visualizable without custom infrastructure

---

## The Three Metric Types

Prometheus has three core metric types. Choosing the right one depends on what you're measuring.

### Counter: Things That Only Go Up

A **Counter** is a cumulative value that only increases (or resets to zero when the process restarts).

**Use for:**

- Total requests processed
- Total tokens consumed
- Total errors encountered
- Total cost accumulated

**Mental model:** An odometer. It only goes up. If you want "requests per second," you calculate the _rate_ of counter increase.

```python
# Reference: prometheus_client PyPI documentation
# https://pypi.org/project/prometheus-client/

from prometheus_client import Counter

# Define the counter (do this at module level, not per-request)
REQUESTS_TOTAL = Counter(
    'llm_requests_total',           # Metric name (must be unique)
    'Total LLM requests processed',  # Description (required)
    ['status', 'query_type']         # Labels (dimensions)
)

# Increment the counter
REQUESTS_TOTAL.labels(status='success', query_type='internal_docs').inc()
REQUESTS_TOTAL.labels(status='error', query_type='web_search').inc()

# Increment by a specific amount
TOKENS_TOTAL = Counter(
    'llm_tokens_total',
    'Total tokens consumed',
    ['model', 'direction']  # direction: input or output
)

TOKENS_TOTAL.labels(model='gpt-4o-mini', direction='input').inc(1500)
TOKENS_TOTAL.labels(model='gpt-4o-mini', direction='output').inc(350)
```

**Important:** Counter names should end with `_total` (the library handles this automatically in OpenMetrics format).

**PromQL to calculate rate:**

```promql
# Requests per second over last 5 minutes
rate(llm_requests_total[5m])

# Error rate
sum(rate(llm_requests_total{status="error"}[5m])) / sum(rate(llm_requests_total[5m]))
```

### Histogram: Distributions (for Percentiles)

A **Histogram** tracks the _distribution_ of values by counting how many fall into each bucket. This allows calculating percentiles without storing every individual value.

**Use for:**

- Request latency (need p50, p95, p99)
- Response sizes
- Token counts per request

**Mental model:** Sorting requests into bins. "How many requests took 0-100ms? How many took 100-500ms? How many took 500ms-1s?"

```python
# Reference: prometheus_client documentation
# https://prometheus.github.io/client_python/instrumenting/histogram/

from prometheus_client import Histogram

# Define histogram with custom buckets
REQUEST_LATENCY = Histogram(
    'llm_request_latency_seconds',
    'Request latency in seconds',
    ['query_type'],
    # buckets: upper bounds for each bucket
    # Choose based on your expected latency range
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

# Record an observation
REQUEST_LATENCY.labels(query_type='internal_docs').observe(0.85)  # 850ms

# Use as a context manager (automatically times the block)
with REQUEST_LATENCY.labels(query_type='web_search').time():
    result = call_llm()

# Use as a decorator
@REQUEST_LATENCY.labels(query_type='general').time()
def process_query():
    # ... processing ...
    pass
```

**What gets stored:**

For each label combination, a histogram stores:

- `llm_request_latency_seconds_bucket{le="0.1"}` — count of requests ≤ 100ms
- `llm_request_latency_seconds_bucket{le="0.25"}` — count of requests ≤ 250ms
- ... (one counter per bucket)
- `llm_request_latency_seconds_bucket{le="+Inf"}` — count of all requests
- `llm_request_latency_seconds_sum` — total sum of all observed values
- `llm_request_latency_seconds_count` — total count of observations

**PromQL to calculate percentiles:**

```promql
# 95th percentile latency
histogram_quantile(0.95, sum by (le) (rate(llm_request_latency_seconds_bucket[5m])))

# 95th percentile by query type
histogram_quantile(0.95, sum by (query_type, le) (rate(llm_request_latency_seconds_bucket[5m])))

# Average latency
sum(rate(llm_request_latency_seconds_sum[5m])) / sum(rate(llm_request_latency_seconds_count[5m]))
```

### Gauge: Current Values That Go Up and Down

A **Gauge** is a point-in-time value that can increase or decrease.

**Use for:**

- Currently active requests (concurrent connections)
- Cache size (entries currently stored)
- Queue depth
- Temperature, memory usage, etc.

**Mental model:** A speedometer or thermometer. It shows the _current_ value, not a cumulative total.

```python
# Reference: prometheus_client documentation

from prometheus_client import Gauge

# Define the gauge
ACTIVE_REQUESTS = Gauge(
    'llm_active_requests',
    'Currently processing requests'
)

# Manually set, increment, decrement
ACTIVE_REQUESTS.inc()   # +1
ACTIVE_REQUESTS.dec()   # -1
ACTIVE_REQUESTS.set(5)  # Set to specific value

# Use track_inprogress() for automatic inc/dec
@ACTIVE_REQUESTS.track_inprogress()
def process_request():
    # Gauge incremented on entry, decremented on exit
    pass

# Or as context manager
with ACTIVE_REQUESTS.track_inprogress():
    # Gauge incremented while in this block
    pass
```

---

## Choosing the Right Type: Decision Tree

```
What are you measuring?
│
├── "Total X ever" (always increases)
│   └── Use COUNTER
│       Examples: total requests, total tokens, total cost, total errors
│
├── "Distribution of X" (need percentiles)
│   └── Use HISTOGRAM
│       Examples: latency, response size, tokens per request
│
└── "Current X" (can go up or down)
    └── Use GAUGE
        Examples: active requests, queue depth, cache size
```

**Common mistakes:**

- Using a Counter for "active requests" (wrong — active requests go down)
- Using a Gauge for "total requests" (wrong — you lose data on scrape gaps)
- Using a Summary instead of Histogram (Summaries can't be aggregated across instances)

---

## Key Metrics for LLM Systems

Here's the minimal set of metrics every LLM system should expose:

```python
# llm_metrics.py
# Reference: prometheus_client documentation
# https://pypi.org/project/prometheus-client/

from prometheus_client import Counter, Histogram, Gauge

# === LATENCY (Histogram) ===
# Get p50, p95, p99 from this
REQUEST_LATENCY = Histogram(
    'llm_request_latency_seconds',
    'Total request latency in seconds',
    ['query_type', 'status'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

# Per-step latency (helps identify bottlenecks)
STEP_LATENCY = Histogram(
    'llm_step_latency_seconds',
    'Latency per processing step',
    ['step'],  # step: retrieval, rerank, generation, guardrail
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# === THROUGHPUT (Counter) ===
REQUESTS_TOTAL = Counter(
    'llm_requests_total',
    'Total requests processed',
    ['status', 'query_type']  # status: success, error, timeout
)

# === TOKENS (Counter) ===
TOKENS_TOTAL = Counter(
    'llm_tokens_total',
    'Total tokens consumed',
    ['model', 'direction']  # direction: input, output
)

# === COST (Counter) ===
COST_USD_TOTAL = Counter(
    'llm_cost_usd_total',
    'Total cost in USD',
    ['model']
)

# === ACTIVE REQUESTS (Gauge) ===
ACTIVE_REQUESTS = Gauge(
    'llm_active_requests',
    'Currently processing requests'
)

# === RETRIEVAL QUALITY (Histogram) ===
RETRIEVAL_SCORE = Histogram(
    'llm_retrieval_top_score',
    'Top retrieval relevance score',
    ['query_type'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)
```

---

## Labels: Adding Dimensions Without New Metrics

Labels let you slice one metric by multiple dimensions. Instead of creating `requests_success_total` and `requests_error_total`, you create one metric with a `status` label.

```python
# One metric, sliced by labels
REQUESTS = Counter(
    'llm_requests_total',
    'Total requests',
    ['status', 'query_type', 'model']
)

# Recording observations
REQUESTS.labels(status='success', query_type='internal_docs', model='gpt-4o-mini').inc()
REQUESTS.labels(status='error', query_type='web_search', model='gpt-4o').inc()
```

**Querying by label in PromQL:**

```promql
# All requests
llm_requests_total

# Only errors
llm_requests_total{status="error"}

# Errors by query type
sum by (query_type) (rate(llm_requests_total{status="error"}[5m]))
```

### Good Labels (Low Cardinality)

Labels should have a **bounded, small number of distinct values**:

|Label|Example Values|Cardinality|
|---|---|---|
|`status`|success, error, timeout|3|
|`model`|gpt-4o, gpt-4o-mini, claude-sonnet|~5-10|
|`query_type`|internal_docs, web_search, general|~5-10|
|`step`|retrieval, rerank, generation|~5|

### Bad Labels (High Cardinality) — Avoid These

|Label|Why It's Bad|
|---|---|
|`user_id`|Thousands of unique values = thousands of time series|
|`request_id`|Every request creates a new time series|
|`query_hash`|Unbounded, grows forever|
|`timestamp`|Never use this as a label|

**Why it matters:** Each unique label combination creates a new time series. If you have:

- 3 status values × 5 query types × 5 models = 75 time series (fine)
- 3 status values × 10,000 users = 30,000 time series (problem)

High cardinality causes:

- Memory pressure on Prometheus server
- Slow queries
- Increased storage costs

**Rule of thumb:** If a label can have more than ~100 distinct values, don't use it as a label. Log it instead (logs handle high cardinality fine).

---

## Instrumenting Code with `prometheus_client`

**Installation:**

```bash
pip install prometheus_client
```

### Complete Instrumentation Example

```python
# instrumented_llm.py
# Reference: prometheus_client documentation
# https://pypi.org/project/prometheus-client/

import time
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from dataclasses import dataclass
from typing import Optional


# === Define metrics at module level (singleton pattern) ===
REQUEST_LATENCY = Histogram(
    'llm_request_latency_seconds',
    'Total request latency',
    ['query_type', 'status'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

STEP_LATENCY = Histogram(
    'llm_step_latency_seconds',
    'Per-step latency',
    ['step'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

REQUESTS_TOTAL = Counter(
    'llm_requests_total',
    'Total requests',
    ['status', 'query_type']
)

TOKENS_TOTAL = Counter(
    'llm_tokens_total',
    'Total tokens',
    ['model', 'direction']
)

COST_USD_TOTAL = Counter(
    'llm_cost_usd_total',
    'Total cost in USD',
    ['model']
)

ACTIVE_REQUESTS = Gauge(
    'llm_active_requests',
    'Active requests'
)


@dataclass
class LLMResult:
    response: str
    model: str
    input_tokens: int
    output_tokens: int


# Pricing per 1M tokens
PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING.get(model, {"input": 0, "output": 0})
    return (
        (input_tokens / 1_000_000) * pricing["input"] +
        (output_tokens / 1_000_000) * pricing["output"]
    )


def process_query(query: str, query_type: str = "general") -> str:
    """
    Process an LLM query with full Prometheus instrumentation.
    """
    start_time = time.time()
    status = "success"
    
    # Track active requests
    ACTIVE_REQUESTS.inc()
    
    try:
        # === Step 1: Retrieval ===
        retrieval_start = time.time()
        chunks = retrieve_documents(query)  # Your retrieval function
        STEP_LATENCY.labels(step='retrieval').observe(time.time() - retrieval_start)
        
        # === Step 2: Reranking ===
        rerank_start = time.time()
        ranked_chunks = rerank(chunks, query)  # Your rerank function
        STEP_LATENCY.labels(step='rerank').observe(time.time() - rerank_start)
        
        # === Step 3: Generation ===
        generation_start = time.time()
        result = generate_response(query, ranked_chunks)  # Your LLM call
        STEP_LATENCY.labels(step='generation').observe(time.time() - generation_start)
        
        # === Record token and cost metrics ===
        TOKENS_TOTAL.labels(model=result.model, direction='input').inc(result.input_tokens)
        TOKENS_TOTAL.labels(model=result.model, direction='output').inc(result.output_tokens)
        
        cost = calculate_cost(result.model, result.input_tokens, result.output_tokens)
        COST_USD_TOTAL.labels(model=result.model).inc(cost)
        
        return result.response
        
    except Exception as e:
        status = "error"
        raise
        
    finally:
        # Always record these, even on error
        ACTIVE_REQUESTS.dec()
        
        total_latency = time.time() - start_time
        REQUEST_LATENCY.labels(query_type=query_type, status=status).observe(total_latency)
        REQUESTS_TOTAL.labels(status=status, query_type=query_type).inc()


# Stub implementations for illustration
def retrieve_documents(query: str) -> list:
    time.sleep(0.2)  # Simulate retrieval
    return ["chunk1", "chunk2"]

def rerank(chunks: list, query: str) -> list:
    time.sleep(0.05)  # Simulate reranking
    return chunks

def generate_response(query: str, chunks: list) -> LLMResult:
    time.sleep(0.5)  # Simulate LLM call
    return LLMResult(
        response="Here's the answer...",
        model="gpt-4o-mini",
        input_tokens=1500,
        output_tokens=350
    )


if __name__ == "__main__":
    # Start metrics server on port 8000
    start_http_server(8000)
    print("Metrics available at http://localhost:8000/metrics")
    
    # Simulate some requests
    while True:
        try:
            process_query("What is the refund policy?", "internal_docs")
        except Exception:
            pass
        time.sleep(1)
```

### Exposing the Metrics Endpoint

```python
# Option 1: Standalone HTTP server (simplest)
from prometheus_client import start_http_server

start_http_server(8000)  # Metrics at http://localhost:8000/metrics


# Option 2: Integrate with Flask
from flask import Flask
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


# Option 3: Integrate with FastAPI
from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

@app.get('/metrics')
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

---

## Histogram Buckets: Choosing the Right Boundaries

The default buckets in `prometheus_client` are designed for typical web requests:

```python
# Default buckets (in seconds)
DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf'))
```

These are **wrong for LLM systems**. LLM calls are much slower — typically 500ms to 30+ seconds.

### Recommended Buckets for LLM Systems

```python
# LLM request latency (total end-to-end)
# Range: 100ms to 60 seconds
LLM_REQUEST_BUCKETS = [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0]

# LLM generation step only
# Range: 200ms to 30 seconds
LLM_GENERATION_BUCKETS = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0]

# Retrieval step
# Range: 10ms to 2 seconds
RETRIEVAL_BUCKETS = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]

# Reranking step
# Range: 10ms to 500ms
RERANK_BUCKETS = [0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5]
```

### Bucket Design Principles

1. **Cover your expected range**: Buckets outside your typical range waste storage
2. **Concentrate buckets where you care**: More buckets near your SLO threshold
3. **Include your SLO boundary**: If SLO is "95% under 3s," have a bucket at 3.0
4. **Don't over-bucket**: 8-15 buckets is usually enough

**Example: SLO-driven buckets**

If your SLO is "95% of requests complete in under 5 seconds":

```python
# Concentrate buckets around the 5s boundary
SLO_DRIVEN_BUCKETS = [
    0.5,   # Fast
    1.0,   
    2.0,   
    3.0,   # Getting close
    4.0,   
    5.0,   # SLO boundary
    7.5,   # Over SLO
    10.0,  
    30.0   # Way over
]
```

Now you can easily query:

```promql
# Percentage of requests meeting SLO (under 5s)
sum(rate(llm_request_latency_seconds_bucket{le="5.0"}[5m])) 
/ 
sum(rate(llm_request_latency_seconds_count[5m]))
```

---

## What `/metrics` Output Looks Like

When you visit `http://localhost:8000/metrics`, you see Prometheus text format:

```
# HELP llm_requests_total Total requests processed
# TYPE llm_requests_total counter
llm_requests_total{status="success",query_type="internal_docs"} 142.0
llm_requests_total{status="error",query_type="internal_docs"} 3.0
llm_requests_total{status="success",query_type="web_search"} 87.0

# HELP llm_request_latency_seconds Total request latency
# TYPE llm_request_latency_seconds histogram
llm_request_latency_seconds_bucket{query_type="internal_docs",status="success",le="0.1"} 0.0
llm_request_latency_seconds_bucket{query_type="internal_docs",status="success",le="0.25"} 2.0
llm_request_latency_seconds_bucket{query_type="internal_docs",status="success",le="0.5"} 15.0
llm_request_latency_seconds_bucket{query_type="internal_docs",status="success",le="1.0"} 89.0
llm_request_latency_seconds_bucket{query_type="internal_docs",status="success",le="2.5"} 135.0
llm_request_latency_seconds_bucket{query_type="internal_docs",status="success",le="5.0"} 140.0
llm_request_latency_seconds_bucket{query_type="internal_docs",status="success",le="10.0"} 142.0
llm_request_latency_seconds_bucket{query_type="internal_docs",status="success",le="+Inf"} 142.0
llm_request_latency_seconds_sum{query_type="internal_docs",status="success"} 198.45
llm_request_latency_seconds_count{query_type="internal_docs",status="success"} 142.0

# HELP llm_active_requests Active requests
# TYPE llm_active_requests gauge
llm_active_requests 3.0

# HELP llm_tokens_total Total tokens consumed
# TYPE llm_tokens_total counter
llm_tokens_total{model="gpt-4o-mini",direction="input"} 213000.0
llm_tokens_total{model="gpt-4o-mini",direction="output"} 49700.0

# HELP llm_cost_usd_total Total cost in USD
# TYPE llm_cost_usd_total counter
llm_cost_usd_total{model="gpt-4o-mini"} 0.0618
```

Prometheus scrapes this every 15-30 seconds and stores the time series. Grafana (or PromQL queries) then visualize trends, calculate rates, and derive percentiles.

---

## Key Takeaways

1. **Three types, three purposes**: Counter for totals, Histogram for distributions, Gauge for current values.
    
2. **Histograms give you percentiles**: Use them for latency. The buckets you choose determine your resolution.
    
3. **Labels add dimensions without new metrics**: Slice by `status`, `model`, `query_type` — but avoid high-cardinality labels like `user_id`.
    
4. **LLM systems need custom buckets**: Default buckets assume millisecond latencies. LLM calls take seconds — adjust accordingly.
    
5. **Expose `/metrics` endpoint**: Use `start_http_server(8000)` or integrate with your web framework. Prometheus will scrape this.
    
6. **Instrument at the right places**: Total latency, per-step latency, tokens, cost, errors. These are your production health signals.