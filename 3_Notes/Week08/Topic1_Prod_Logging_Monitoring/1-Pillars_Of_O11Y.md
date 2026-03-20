# Note 1: Logs, Metrics, and Traces — The Three Pillars of Observability

## Context: From Tracing to Production Monitoring

Week 7 gave you **tracing** — the ability to see what happened inside a single request. You instrumented your Research Assistant with LangSmith or LangFuse, and now you can click on any request and see the full chain: query → retrieval → reranking → generation → response.

That's powerful for debugging individual failures. But it doesn't answer production questions:

- Is latency getting worse over the last hour?
- Did yesterday's deployment increase error rates?
- Are we on track to exceed our monthly token budget?
- Is one user consuming 80% of resources?

**Tracing is a microscope. Production monitoring is a dashboard with gauges, warning lights, and trend lines.**

You need both. The difference:

|Concern|Tool|Question|
|---|---|---|
|"Why did this request fail?"|Tracing|What happened step-by-step?|
|"Are requests failing more than usual?"|Monitoring|What's the error rate trend?|
|"Where in the flow did it slow down?"|Tracing|Which span took longest?|
|"Is the system slower than yesterday?"|Monitoring|What's p95 latency over time?|

This note introduces the three pillars that make production monitoring possible: **logs**, **metrics**, and **traces**. You already know traces from Week 7. Now we complete the picture.

---

## The Three Pillars: What Each Answers

```
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│        LOGS         │  │       METRICS       │  │       TRACES        │
│                     │  │                     │  │                     │
│   Discrete events   │  │     Aggregates      │  │    Request flow     │
│   with context      │  │     over time       │  │    across steps     │
│                     │  │                     │  │                     │
│  "What happened"    │  │  "How is it going"  │  │  "How did it flow"  │
│                     │  │                     │  │                     │
│  Error at 14:32:05  │  │  Error rate: 2.3%   │  │  Query → RAG → LLM  │
│  User X, Query Y    │  │  p95 latency: 850ms │  │  RAG took 400ms     │
│  Failed: timeout    │  │  Cost today: $12.50 │  │  LLM took 600ms     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

### Logs: What Happened?

Logs are **discrete events** with **context**. Each log entry captures a moment in time with enough information to understand what occurred.

**Characteristics:**

- Timestamped events (something happened at time T)
- Human-readable or structured (JSON)
- Immutable records (written once, never modified)
- High cardinality (you can log anything — user IDs, queries, error messages)

**What logs answer:**

- What exact error did user X see at 14:32?
- What query caused the timeout?
- What was the LLM's response when it hallucinated?
- Which tools did the agent invoke for this request?

**The tradeoff:** Logs are rich in detail but expensive to query at scale. Finding patterns across millions of logs requires indexing, search infrastructure, and compute. You can't efficiently ask "what's the error rate?" by counting log entries in real-time.

### Metrics: How Is the System Behaving?

Metrics are **aggregate measurements** sampled over **time**. They sacrifice per-event detail for efficient trend analysis.

**Characteristics:**

- Numeric values (counts, gauges, histograms)
- Low cardinality labels (status: success/error, model: gpt-4o/gpt-4o-mini)
- Time-series data (values at regular intervals)
- Cheap to query (pre-aggregated, purpose-built storage)

**What metrics answer:**

- What's the error rate over the last hour?
- Is p95 latency increasing?
- How many tokens did we consume today?
- What's the cost per query by model?

**The tradeoff:** Metrics are efficient but lossy. You know error rate is 5%, but you don't know which errors or what caused them. Metrics tell you something is wrong; logs and traces tell you what.

**Metric types you'll use:**

- **Counter**: Cumulative value that only increases (total requests, total tokens, total cost)
- **Gauge**: Point-in-time value that can go up or down (active requests, queue depth, cache size)
- **Histogram**: Distribution of values (latency — gives you p50, p95, p99 without storing every value)

### Traces: How Did This Request Flow?

Traces capture the **lifecycle of a single request** across components and steps. You covered this in Week 7.

**Characteristics:**

- Spans with parent-child relationships
- Timing for each step
- Context propagation across services
- Sampling (you often trace a subset of requests)

**What traces answer:**

- Which step in the pipeline caused the slowdown?
- Did the agent call tools in the expected order?
- How much time was spent in retrieval vs. generation?
- What was the reasoning chain for this decision?

**The tradeoff:** Traces are detailed but typically sampled. You can't afford to trace every request in a high-volume system. Traces also require correlation infrastructure to connect spans across components.

---

## When to Use Which

The pillars aren't alternatives — they're complementary. The question is which to reach for first.

### Debugging a Single Request → Traces

A user reports: "My query took 30 seconds."

You don't want to grep through logs. You want to pull up the trace for that request ID and see exactly where the time went:

```
Request: req_abc123 (30.2s total)
├── parse_query: 50ms
├── rag_retrieval: 400ms
├── rerank: 150ms
├── llm_generation: 29.5s  ← Found it
│   └── model: gpt-4o
│   └── tokens: 8,500 output
└── format_response: 100ms
```

The trace immediately shows the LLM generation step was the bottleneck — a verbose response with high token count.

### Detecting Systemic Issues → Metrics

Your alerting system fires: "Error rate exceeded 5% for 10 minutes."

You don't start by reading logs. You check the metrics dashboard:

- When did error rate spike? (10:45 AM)
- Did latency also spike? (Yes, p95 went from 800ms to 4s)
- Is it one query type or all? (Filter by label: it's web_search queries)
- Did anything else change at 10:45? (Deployment at 10:42)

Metrics tell you there's a systemic issue, when it started, and what category of requests are affected. Now you have a hypothesis.

### Understanding Specific Failures → Logs

Metrics showed you web_search queries are failing. Now you need details.

Query logs filtered to `query_type=web_search AND status=error AND timestamp > 10:45`:

```json
{
  "timestamp": "2024-01-15T10:47:23Z",
  "request_id": "req_def456",
  "query_type": "web_search",
  "status": "error",
  "error_type": "RateLimitError",
  "error_message": "Rate limit exceeded for search API",
  "user_id": "user_789"
}
```

Now you know: the 10:42 deployment introduced a bug that hammers the search API, triggering rate limits.

---

## How They Complement Each Other

The canonical flow:

```
METRICS ALERT           →    LOGS INVESTIGATE       →    TRACES PINPOINT
                                                    
"Error rate 8%"         →    "RateLimitError        →    "Step 3: search_api
 for 15 minutes"              from search API             called 47 times
                              in web_search               in single request
                              queries"                    (loop bug)"
```

**Metrics** are your early warning system. They tell you something is wrong, often before users complain. They answer "is there a problem?" and "how bad is it?"

**Logs** are your investigation records. Once metrics flag an issue, you search logs to understand what's happening. They answer "what errors?" and "what context?"

**Traces** are your surgical tools. When you need to understand exactly how a specific request behaved, traces show you the path. They answer "how did it break?" and "which component?"

### A Mental Model

Think of running a restaurant:

- **Metrics** = Dashboard on the wall: orders per hour, average wait time, kitchen backlog, table turnover rate. Tells you if the restaurant is running smoothly.
- **Logs** = Incident reports: "Table 7 complained about cold food at 7:45 PM. Server: Alice. Dish: Risotto." Captures specific events for later review.
- **Traces** = Following one order through the kitchen: ticket printed → chef acknowledges → prep starts → cooking → plating → runner takes it → served. Shows where delays happen.

The dashboard tells you "kitchen is backed up." The incident log tells you "three cold food complaints tonight." Tracing an order shows you "the risotto sat under the heat lamp for 8 minutes because runner was busy."

---

## LLM-Specific Considerations

Traditional observability applies to LLM systems, but with unique wrinkles.

### Non-Determinism Makes Logs More Important

Traditional services are deterministic: same input → same output → same logs. If you log the input and output, you can reproduce behavior.

LLMs are stochastic. The same query might produce different responses, tool sequences, or even errors. This means:

- **Log outputs aggressively.** You can't reproduce what the model said without capturing it.
- **Log reasoning steps.** Agent tool calls, retrieved chunks, and intermediate prompts matter.
- **Log model parameters.** Temperature, model version, system prompt hash — anything that affects output.

If you only log "query: X, status: success," you've lost the ability to debug quality issues later.

### Token/Cost Metrics Are Unique

Traditional systems track CPU, memory, requests, latency. LLM systems add:

- **Tokens**: Input tokens, output tokens, by model, by feature
- **Cost**: Cost per request, per user, per query type, daily burn rate
- **Model distribution**: How much traffic goes to GPT-4o vs. GPT-4o-mini?

These metrics don't exist in traditional monitoring. You'll need to instrument them explicitly:

```
COST METRICS (LLM-specific)
├── tokens_total (labels: model, direction)
├── cost_usd_total (labels: model)
├── requests_by_model (labels: model)
└── cost_per_query_type (labels: query_type)
```

Cost alerting is critical. A bug that sends verbose prompts can burn through budget in hours.

### Traces Capture Reasoning, Not Just Calls

Traditional traces show API calls: Service A → Service B → Database → Response.

LLM traces should capture reasoning:

```
Traditional Web Service:
  API Gateway → Auth Service → User Service → Postgres → Response

LLM Agent:
  Query → Intent Classification → Tool Decision → [search_api] → 
  Retrieved Chunks → Relevance Filtering → Prompt Assembly → 
  LLM Generation → Output Parsing → Guardrail Check → Response
```

Each of those steps might have its own sub-trace. The "tool decision" might be an LLM call itself. The "guardrail check" might invoke another model.

Week 7's tracing captured this. The key insight here: LLM traces aren't just for performance — they're for understanding model behavior. You'll review traces to answer:

- Why did the agent choose tool X over tool Y?
- What chunks influenced this response?
- Did the guardrail catch anything?

This is observability for correctness, not just performance.

---

## Summary: The Three Pillars in Production

|Pillar|Data Type|Cardinality|Cost to Store|Cost to Query|Primary Use|
|---|---|---|---|---|---|
|Logs|Discrete events|High (anything)|High|Medium-High|Investigation|
|Metrics|Numeric time-series|Low (labels)|Low|Low|Alerting, trends|
|Traces|Request spans|Medium (sampled)|Medium|Low-Medium|Debugging flow|

**The production monitoring stack:**

1. **Metrics** continuously sampled → dashboards and alerts
2. **Logs** written for every request → searchable for investigation
3. **Traces** sampled or triggered → detailed debugging when needed

You've already built tracing in Week 7. The next notes build out structured logging (Note 2), metrics collection (Note 3), dashboards (Note 4), and alerting (Note 5).

---

## Key Takeaways

1. **Tracing is microscopic; monitoring is macroscopic.** Traces show you one request in detail. Metrics show you system behavior over time.
    
2. **Metrics alert, logs investigate, traces pinpoint.** They work together — don't pick one over another.
    
3. **LLM systems need extra observability.** Non-determinism requires logging outputs. Token economics require cost metrics. Agent reasoning requires rich traces.
    
4. **Metrics are cheap to query; logs are not.** Aggregate questions ("what's error rate?") should hit metrics, not scan logs.
    
5. **All three pillars are essential in production.** Skipping any one leaves blind spots that will bite you during incidents.