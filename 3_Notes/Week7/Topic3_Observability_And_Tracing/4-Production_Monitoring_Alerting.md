# Note 4: Production Monitoring and Alerting

## Documentation Reference

This note draws from:

- LangSmith Observability docs (https://docs.langchain.com/langsmith/observability)
- LangSmith Alerts announcement (https://blog.langchain.com/langsmith-alerts/) — April 2025
- LangSmith PII removal repo (https://github.com/langchain-ai/langsmith-pii-removal)
- Various production deployment guides

---

## Offline vs. Online Monitoring

You've already built offline evaluation in Week 6 — testing against curated datasets before deployment. That catches known failure modes. But production traffic is different: real users, real queries, real edge cases you didn't anticipate.

### Offline Evaluation (Pre-deployment)

- **When**: Before deployment, during development
- **What**: Run against test datasets with known expected outputs
- **Purpose**: Catch regressions, validate changes, benchmark quality
- **Limitation**: Only tests scenarios you anticipated

### Online Monitoring (Post-deployment)

- **When**: Continuously, on real production traffic
- **What**: Track metrics, detect anomalies, score live outputs
- **Purpose**: Catch issues you didn't anticipate, monitor drift
- **Limitation**: Reactive — issues hit users before you catch them

Both are necessary. Offline evaluation is your unit tests. Online monitoring is your production observability.

```
Development Cycle:
                                    ┌─────────────────┐
                                    │ Offline Eval    │
                                    │ (Test Datasets) │
                                    └────────┬────────┘
                                             │
┌──────────┐     ┌──────────┐     ┌──────────▼──────────┐
│ Develop  │────▶│ Test     │────▶│ Deploy              │
│          │     │          │     │                     │
└──────────┘     └──────────┘     └──────────┬──────────┘
      ▲                                      │
      │                                      ▼
      │                           ┌──────────────────────┐
      │                           │ Online Monitoring    │
      │                           │ (Production Traffic) │
      │                           └──────────┬───────────┘
      │                                      │
      └──────────────────────────────────────┘
              Feedback loop: issues → fixes → redeploy
```

---

## Key Metrics to Track in Production

### Error Rate

**What**: Percentage of requests that fail (exceptions, timeouts, invalid outputs)

**Why it matters**: Directly impacts user experience. High error rate = broken system.

**Thresholds**:

- < 1%: Normal operation
- 1-5%: Investigate
- > 5%: Alert immediately
    

**Granularity**: Track overall and per-span. "5% error rate" is less useful than "retrieval has 0.1% errors, generation has 4.9% errors."

```python
# Simple error rate calculation
def calculate_error_rate(traces: list[dict]) -> float:
    """Calculate error rate from traces."""
    if not traces:
        return 0.0
    
    errors = sum(1 for t in traces if t.get("status") == "error")
    return errors / len(traces)
```

### Latency Percentiles

**What**: Response time distribution — p50 (median), p95, p99

**Why p50/p95/p99 instead of average**: Averages hide tail behavior. A system with 200ms average might have 2000ms p99 — meaning 1 in 100 users waits 10x longer.

**Typical targets**:

- p50 < 500ms: Most users get fast responses
- p95 < 2s: Occasional slow requests acceptable
- p99 < 5s: Rare worst cases still tolerable

**What to watch**:

- p99 creeping up often signals upstream issues (model provider, database)
- Big gap between p50 and p95 suggests bimodal behavior — investigate why some requests are slow

### Cost Per Request

**What**: Average and distribution of cost per query

**Why track distribution, not just average**: A few expensive queries can dominate budget. If 5% of queries cost 10x the average, you need to understand why.

**Metrics**:

- Average cost per query
- p95 cost (catches expensive outliers)
- Total daily/weekly spend
- Cost by feature/model/user

### Token Usage

**What**: Input and output tokens over time

**Why it matters**: Token usage drives cost. Trends reveal:

- Prompt drift (system prompts growing over time)
- Context creep (more RAG chunks being retrieved)
- Verbose generation (model outputting more than needed)

### Retrieval Quality

**What**: Relevance scores, empty result rate, reranking distribution

**Metrics**:

- Empty retrieval rate: % of queries with 0 results
- Low-score rate: % of queries where top result < threshold
- Relevance score distribution: Are scores clustering high (good) or spreading (inconsistent)?

**Why track in production**: Retrieval quality degrades when:

- Corpus changes (new docs, deleted docs)
- Query patterns shift (users asking different things)
- Index issues (stale embeddings, corrupted index)

### User Feedback

**What**: Explicit signals — thumbs up/down, ratings, corrections

**Collection methods**:

- Thumbs up/down buttons in UI
- "Was this helpful?" prompts
- Regeneration rate (user clicks "try again" = implicit negative)
- Copying response (implicit positive)

**Integration with traces**: Link feedback to trace IDs so you can inspect exactly what the user rated poorly.

---

## LangSmith Dashboards

LangSmith provides customizable dashboards for production monitoring.

### Creating Custom Views

In the LangSmith UI:

1. Navigate to your project
2. Open the "Monitor" tab
3. Create custom dashboard widgets for:
    - Latency distribution (p50/p95/p99)
    - Error rate over time
    - Token usage breakdown
    - Feedback scores

### Filtering

Filter traces by:

- **Time range**: Last hour, day, week, custom range
- **Tags**: Production vs. staging, feature flags, experiments
- **Metadata**: User ID, model version, prompt version
- **Status**: Success vs. error
- **Run type**: LLM, retriever, tool, chain

### Comparing Deployments

Tag traces with version/deployment info:

```python
from langsmith import traceable

@traceable(
    name="rag_query",
    tags=["production", "v2.3.1"],
    metadata={
        "deployment": "blue",
        "prompt_version": "hyde-v3",
        "model": "gpt-4o-mini"
    }
)
def rag_query(query: str) -> dict:
    # ...
    pass
```

Then filter dashboard by tag to compare:

- v2.3.1 vs. v2.3.0
- Blue deployment vs. green deployment
- hyde-v3 vs. hyde-v2

---

## Setting Up Alerts

LangSmith supports alerting on key metrics with notification delivery to Slack, PagerDuty, or webhooks.

### Available Alert Metrics

As of early 2025, LangSmith supports alerts on:

- **Error rate**: % of runs that fail
- **Run latency**: Response time thresholds
- **Feedback scores**: User satisfaction metrics

**Coming soon** (per LangSmith roadmap): Run count, token usage, and relative change alerts (e.g., "latency increased 25%").

### Threshold-Based Alerts

Set fixed thresholds that trigger when crossed:

|Metric|Warning|Critical|
|---|---|---|
|Error rate|> 2%|> 5%|
|p99 latency|> 3s|> 10s|
|Avg feedback score|< 3.5|< 2.5|

### Configuration Example

In LangSmith UI:

1. Go to Settings → Alerts
2. Create new alert:
    - **Metric**: Error rate
    - **Threshold**: > 5%
    - **Window**: 15 minutes
    - **Filters**: tag = "production"
    - **Notification**: Slack channel #llm-alerts

### Anomaly Detection Patterns

Beyond fixed thresholds, watch for anomalies:

**Cost spike**: Sudden increase in spend

- Could indicate: Model change, runaway agent loop, traffic spike
- Alert: Cost > 2x rolling 7-day average

**Traffic pattern change**: Unusual request volume

- Could indicate: Bot traffic, viral post, DDoS
- Alert: Request count > 3x hourly average

**Latency degradation**: Gradual p99 increase

- Could indicate: Provider issues, memory leak, queue backup
- Alert: p99 trending up over 4 hours

### External Integration

For advanced alerting beyond LangSmith's built-in capabilities:

```python
# Export metrics to external monitoring
import requests

def send_alert(alert_type: str, message: str, severity: str):
    """Send alert to PagerDuty or Slack."""
    
    if severity == "critical":
        # PagerDuty for critical alerts
        requests.post(
            "https://events.pagerduty.com/v2/enqueue",
            json={
                "routing_key": "YOUR_PAGERDUTY_KEY",
                "event_action": "trigger",
                "payload": {
                    "summary": message,
                    "severity": severity,
                    "source": "llm-production"
                }
            }
        )
    else:
        # Slack for warnings
        requests.post(
            "YOUR_SLACK_WEBHOOK",
            json={"text": f"⚠️ {alert_type}: {message}"}
        )
```

---

## Handling Anomalies — Example Patterns

### Pattern 1: Single User Sends 1000 Queries/Hour

**Detection**: Aggregate by user_id, alert when any user exceeds threshold.

**Possible causes**:

- Automated script (legitimate or malicious)
- User running bulk analysis
- Bot/scraper

**Response**:

1. Rate limit the user
2. Investigate: Is this expected usage?
3. If malicious: Block and alert security

```python
from collections import defaultdict
from datetime import datetime, timedelta

class UserRateLimiter:
    def __init__(self, max_per_hour: int = 100):
        self.max_per_hour = max_per_hour
        self.user_counts: dict[str, list[datetime]] = defaultdict(list)
    
    def check_and_record(self, user_id: str) -> bool:
        """
        Returns True if user is within limits, False if rate limited.
        """
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Clean old entries
        self.user_counts[user_id] = [
            t for t in self.user_counts[user_id] if t > hour_ago
        ]
        
        # Check limit
        if len(self.user_counts[user_id]) >= self.max_per_hour:
            self._alert_rate_limit(user_id)
            return False
        
        self.user_counts[user_id].append(now)
        return True
    
    def _alert_rate_limit(self, user_id: str):
        """Send alert for rate-limited user."""
        send_alert(
            "Rate Limit",
            f"User {user_id} exceeded {self.max_per_hour} requests/hour",
            "warning"
        )
```

### Pattern 2: Sudden Cost Spike

**Detection**: Compare current hourly cost to rolling average.

**Possible causes**:

- Model changed (accidentally switched to expensive model)
- Runaway agent loop (agent keeps calling itself)
- Traffic spike (more users than usual)
- Prompt regression (prompt got longer)

**Investigation steps**:

1. Check model distribution — did mix change?
2. Check avg tokens per query — did prompts get longer?
3. Check request count — is traffic up?
4. Check error rate — are retries causing extra calls?

```python
def investigate_cost_spike(
    current_hour_cost: float,
    avg_hourly_cost: float,
    traces: list[dict]
) -> dict:
    """Investigate why cost spiked."""
    
    # Check model distribution
    model_counts = defaultdict(int)
    for t in traces:
        model_counts[t.get("model", "unknown")] += 1
    
    # Check avg tokens
    total_tokens = sum(t.get("total_tokens", 0) for t in traces)
    avg_tokens = total_tokens / len(traces) if traces else 0
    
    # Check for loops (same trace_id multiple times)
    trace_ids = [t.get("trace_id") for t in traces]
    loops = len(trace_ids) - len(set(trace_ids))
    
    return {
        "cost_multiplier": current_hour_cost / avg_hourly_cost,
        "model_distribution": dict(model_counts),
        "avg_tokens_per_query": avg_tokens,
        "suspected_loops": loops,
        "request_count": len(traces)
    }
```

### Pattern 3: Error Rate Spike

**Detection**: Error rate exceeds threshold.

**Possible causes**:

- External API down (model provider, tool API)
- Prompt regression (new prompt causes parsing failures)
- Data issue (corrupted index, missing documents)
- Rate limiting (hit provider's rate limit)

**Investigation steps**:

1. Check error types — what's failing?
2. Check by span — which step fails?
3. Check timing — when did it start?
4. Check correlation — did deployment happen?

```python
def diagnose_error_spike(traces: list[dict]) -> dict:
    """Diagnose sudden error spike."""
    
    # Group errors by type
    error_types = defaultdict(int)
    error_spans = defaultdict(int)
    
    for t in traces:
        if t.get("status") == "error":
            error_type = t.get("error_type", "unknown")
            error_types[error_type] += 1
            
            span = t.get("span_name", "unknown")
            error_spans[span] += 1
    
    # Find most common error
    most_common_error = max(error_types, key=error_types.get) if error_types else None
    most_failing_span = max(error_spans, key=error_spans.get) if error_spans else None
    
    return {
        "error_distribution": dict(error_types),
        "errors_by_span": dict(error_spans),
        "most_common_error": most_common_error,
        "most_failing_span": most_failing_span,
        "suggested_action": _suggest_action(most_common_error, most_failing_span)
    }

def _suggest_action(error_type: str, span: str) -> str:
    """Suggest action based on error pattern."""
    if error_type == "RateLimitError":
        return "Check provider rate limits, consider backoff/retry"
    elif error_type == "TimeoutError":
        return "Check provider status, increase timeout, add fallback"
    elif "retrieval" in span.lower():
        return "Check vector store health, index status"
    elif "generation" in span.lower():
        return "Check model provider status, prompt validity"
    else:
        return "Inspect error traces for root cause"
```

---

## Sampling Strategies

Tracing every request in production can be expensive. Smart sampling captures enough data for debugging without breaking the budget.

### Development/Staging: 100% Tracing

In non-production environments, trace everything. Storage is cheap compared to debugging time lost from missing traces.

### Production: Sampled Tracing

Sample 10-20% of successful requests, but keep special handling for important cases:

```python
import random
from langsmith import traceable
from functools import wraps


def sampled_traceable(
    sample_rate: float = 0.1,
    always_trace_errors: bool = True,
    always_trace_slow: bool = True,
    slow_threshold_ms: float = 3000
):
    """
    Decorator for sampled tracing.
    
    Args:
        sample_rate: Fraction of requests to trace (0.0 to 1.0)
        always_trace_errors: Always trace requests that raise exceptions
        always_trace_slow: Always trace requests exceeding threshold
        slow_threshold_ms: Threshold for "slow" requests
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Decide whether to trace
            should_trace = random.random() < sample_rate
            
            if should_trace:
                # Use normal traceable
                traced_func = traceable(name=func.__name__)(func)
                return traced_func(*args, **kwargs)
            else:
                # Run without tracing, but catch errors/slowness
                import time
                start = time.perf_counter()
                
                try:
                    result = func(*args, **kwargs)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    
                    # Trace slow requests even if not sampled
                    if always_trace_slow and elapsed_ms > slow_threshold_ms:
                        _log_slow_request(func.__name__, elapsed_ms, args, kwargs)
                    
                    return result
                    
                except Exception as e:
                    # Always trace errors
                    if always_trace_errors:
                        _log_error(func.__name__, e, args, kwargs)
                    raise
        
        return wrapper
    return decorator


def _log_slow_request(name: str, elapsed_ms: float, args, kwargs):
    """Log slow request that wasn't initially sampled."""
    # Could send to LangSmith via API or log locally
    print(f"SLOW REQUEST: {name} took {elapsed_ms:.0f}ms")


def _log_error(name: str, error: Exception, args, kwargs):
    """Log error that wasn't initially sampled."""
    print(f"ERROR: {name} - {type(error).__name__}: {error}")


# Usage
@sampled_traceable(sample_rate=0.1)
def rag_query(query: str) -> dict:
    # 10% of successful requests traced
    # 100% of errors traced
    # 100% of slow requests traced
    pass
```

### Always Trace These Cases

Regardless of sampling, always capture:

1. **Errors**: Every failed request should have a trace for debugging
2. **Slow requests**: Requests exceeding latency threshold
3. **Low feedback scores**: When user indicates poor quality
4. **High cost**: Requests exceeding cost threshold
5. **New users**: First N requests from each user

### LangSmith Retention Tiers

LangSmith uses two retention tiers:

- **Base traces**: 14-day retention, lower cost
- **Extended traces**: 400-day retention, higher cost

Strategy: Keep most traces as base, automatically upgrade important ones (errors, feedback, slow) to extended.

---

## PII and Sensitive Data Handling

Traces contain user queries and LLM outputs — potentially including sensitive information. Production systems must handle this carefully.

### The Problem

A typical trace might contain:

```
Input: "My SSN is 123-45-6789 and I need help with my account"
Output: "I see your account ending in 6789. Here's your balance..."
```

If this trace is stored in a third-party service (even LangSmith), you now have PII in an external system.

### Option 1: Redact Before Logging

Use LangSmith's `create_anonymizer` hook to redact PII client-side, before traces leave your application:

```python
import re
from langsmith import Client
from langsmith.anonymizer import create_anonymizer
from langsmith.wrappers import wrap_openai
import openai

# Define PII patterns
PII_PATTERNS = [
    # SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN_REDACTED]"),
    # Email
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL_REDACTED]"),
    # Phone
    (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE_REDACTED]"),
    # Credit card
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CC_REDACTED]"),
]

# Create anonymizer
anonymizer = create_anonymizer([
    {"pattern": pattern.pattern, "replace": replacement}
    for pattern, replacement in PII_PATTERNS
])

# Use with LangSmith client
langsmith_client = Client(anonymizer=anonymizer)
openai_client = wrap_openai(openai.OpenAI())

# PII is automatically redacted in traces
response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "My email is john@example.com"}],
    langsmith_extra={"client": langsmith_client}
)
```

**Doc reference**: LangSmith PII removal repo (https://github.com/langchain-ai/langsmith-pii-removal)

### Option 2: Hide Inputs/Outputs Globally

For maximum protection, hide all inputs/outputs:

```bash
export LANGSMITH_HIDE_INPUTS=true
export LANGSMITH_HIDE_OUTPUTS=true
```

This logs trace structure (timing, spans) without content. Useful for latency analysis when content doesn't matter.

### Option 3: Custom Redaction Functions

For fine-grained control, define custom redaction logic:

```python
from langsmith import Client

def redact_system_messages(inputs: dict) -> dict:
    """Redact system messages that might contain sensitive instructions."""
    messages = inputs.get("messages", [])
    redacted = []
    
    for msg in messages:
        if msg.get("role") == "system":
            redacted.append({"role": "system", "content": "[SYSTEM_REDACTED]"})
        else:
            redacted.append(msg)
    
    return {**inputs, "messages": redacted}


def redact_tool_results(outputs: dict) -> dict:
    """Redact tool results that might contain PII."""
    # Apply PII patterns to tool outputs
    # Implementation depends on your output structure
    return outputs


langsmith_client = Client(
    hide_inputs=redact_system_messages,
    hide_outputs=redact_tool_results
)
```

### Option 4: Self-Host for Data Control

If data can't leave your environment:

- **LangSmith BYOC (Bring Your Own Cloud)**: LangSmith runs in your cloud account
- **LangSmith Self-Hosted**: Full control in your Kubernetes cluster
- **Langfuse**: Open-source alternative, self-hostable

### The Trade-off

More redaction = less debuggability. If you redact user queries, you can't see what the user actually asked when debugging failures.

**Practical approach**:

1. Redact obvious PII patterns (SSN, CC, etc.)
2. Keep query content for debugging
3. Shorter retention for sensitive projects (delete after 14 days)
4. Access controls on trace data

---

## Aggregate Analytics

Individual traces show what happened. Aggregate analytics show patterns.

### Query Patterns

Cluster similar queries to understand what users actually ask:

```python
from collections import defaultdict
from sklearn.cluster import KMeans
import numpy as np

def analyze_query_patterns(
    queries: list[str],
    embeddings: list[list[float]],
    n_clusters: int = 10
) -> dict:
    """Cluster queries to find common patterns."""
    
    # Cluster embeddings
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(np.array(embeddings))
    
    # Group queries by cluster
    clusters = defaultdict(list)
    for query, label in zip(queries, labels):
        clusters[label].append(query)
    
    # Find representative query per cluster
    patterns = {}
    for label, cluster_queries in clusters.items():
        patterns[f"cluster_{label}"] = {
            "count": len(cluster_queries),
            "examples": cluster_queries[:3],  # First 3 as examples
            "percentage": len(cluster_queries) / len(queries) * 100
        }
    
    return patterns
```

Insights from query clustering:

- "40% of queries are simple lookups" → Optimize for these
- "15% ask about topic X which isn't in our corpus" → Add content
- "10% are variations of 'I don't understand'" → Improve explanations

### Failure Mode Analysis

Group errors to find systemic issues:

```python
def analyze_failure_modes(error_traces: list[dict]) -> dict:
    """Identify common failure patterns."""
    
    # Group by error type and span
    failure_groups = defaultdict(list)
    
    for trace in error_traces:
        key = (
            trace.get("error_type", "unknown"),
            trace.get("span_name", "unknown")
        )
        failure_groups[key].append(trace)
    
    # Analyze each group
    analysis = {}
    for (error_type, span), traces in failure_groups.items():
        analysis[f"{span}:{error_type}"] = {
            "count": len(traces),
            "percentage": len(traces) / len(error_traces) * 100,
            "example_inputs": [t.get("input", "")[:100] for t in traces[:3]],
            "first_seen": min(t.get("timestamp") for t in traces),
            "last_seen": max(t.get("timestamp") for t in traces),
        }
    
    return dict(sorted(analysis.items(), key=lambda x: -x[1]["count"]))
```

### LangSmith Insights Agent

LangSmith has introduced an AI-powered insights agent ("Polly") that automatically:

- Clusters similar conversations
- Identifies common failure patterns
- Surfaces anomalies
- Suggests optimizations

This automates much of the manual analysis work.

---

## Connecting Traces to Business Metrics

Traces show technical performance. Business cares about outcomes.

### Tag by Business Dimension

Add business context to traces:

```python
@traceable(
    name="rag_query",
    tags=["production"],
    metadata={
        "feature": "customer_support",
        "user_tier": "enterprise",
        "experiment": "hyde_v3",
        "cohort": "onboarding_week_1"
    }
)
def rag_query(query: str, user_context: dict) -> dict:
    # ...
    pass
```

Now you can analyze:

- Does enterprise tier get better quality than free tier?
- How does the new experiment affect latency?
- Do onboarding users have different failure patterns?

### A/B Testing Integration

For A/B tests, tag traces with variant:

```python
def get_variant(user_id: str) -> str:
    """Determine A/B variant for user."""
    # Your A/B testing logic
    return "variant_a" if hash(user_id) % 2 == 0 else "variant_b"


@traceable(name="rag_query")
def rag_query_with_ab(query: str, user_id: str) -> dict:
    variant = get_variant(user_id)
    
    # Log variant in trace
    # (Implementation varies by how you configure traceable)
    
    if variant == "variant_a":
        return rag_query_v1(query)
    else:
        return rag_query_v2(query)
```

Then compare metrics by variant:

- Variant A: 2.1s avg latency, 4.2 avg feedback
- Variant B: 1.8s avg latency, 4.5 avg feedback
- Decision: Ship variant B

### Correlation with User Satisfaction

Link traces to downstream metrics:

```
Trace ID: abc-123
├── Latency: 1.2s
├── Retrieval score: 0.85
├── Cost: $0.003
│
└── Downstream:
    ├── User clicked "helpful": Yes
    ├── User asked follow-up: No
    ├── Session duration after: 5 min
    └── Converted to paid: Yes (7 days later)
```

This lets you ask: "Do low-latency, high-retrieval-score traces correlate with higher conversion?"

---

## Production Monitoring Checklist

### Before Launch

- [ ] 100% tracing enabled in staging
- [ ] Alerts configured for error rate, latency, cost
- [ ] PII redaction implemented and tested
- [ ] Dashboards showing key metrics
- [ ] On-call rotation knows how to investigate LLM issues

### First Week in Production

- [ ] Review all error traces
- [ ] Check latency percentiles match expectations
- [ ] Verify cost tracking is accurate
- [ ] Adjust alert thresholds based on real traffic patterns
- [ ] Collect initial feedback data

### Ongoing

- [ ] Weekly review of query patterns
- [ ] Monthly failure mode analysis
- [ ] Quarterly cost optimization review
- [ ] Continuous feedback collection and correlation

---

## What's Next

You now have observability in place — tracing what happens, tracking costs, monitoring in real-time, and alerting on issues. The next phase of Week 7 connects this to LLMOps: production logging, caching strategies, and cost optimization at scale.