# Observability in Production

## The Core Insight

Debug tooling answers: "Why did THIS query fail?"

Production observability answers: "How is my RAG system behaving across ALL queries?"

They're different problems. Debug tooling is deep and narrow — full traces for single queries during active investigation. Production observability is shallow and wide — lightweight signals across thousands of queries, always on, catching problems before users report them.

```
┌─────────────────────────────────────────────────────────────────────┐
│                Debug Tooling vs. Production Observability           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Debug Tooling:                                                    │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                                                             │   │
│   │   Query ──────────────────────────────────────► Answer      │   │
│   │      │                                             │        │   │
│   │      │  [FULL TRACE]                               │        │   │
│   │      │  • Every retrieved chunk                    │        │   │
│   │      │  • Every score                              │        │   │
│   │      │  • Full context text                        │        │   │
│   │      │  • Complete prompt                          │        │   │
│   │      │  • Raw LLM response                         │        │   │
│   │      │                                             │        │   │
│   │   → Deep visibility into ONE query                 │        │   │
│   │   → High overhead (acceptable for debugging)       │        │   │
│   │                                                             │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   Production Observability:                                         │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                                                             │   │
│   │   Query₁ ─[metrics]─► Answer₁                               │   │
│   │   Query₂ ─[metrics]─► Answer₂                               │   │
│   │   Query₃ ─[metrics]─► Answer₃     ──► Dashboard             │   │
│   │   ...                              • p50/p99 latency        │   │
│   │   Query₁₀₀₀ ─[metrics]─► Answer₁₀₀₀ • Error rate            │   │
│   │                                    • Token costs            │   │
│   │   → Lightweight signals across ALL queries                  │   │
│   │   → Low overhead (must be always-on)                        │   │
│   │                                                             │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

You need both. Debug tooling for investigation. Observability for continuous monitoring.

---

## Debug Tooling vs. Production Observability

|Aspect|Debug Tooling|Production Observability|
|---|---|---|
|**Scope**|Single query, deep|All queries, shallow|
|**When enabled**|During active debugging|Always on|
|**Overhead target**|< 500ms acceptable|< 5ms required|
|**Data captured**|Full traces, embeddings, prompts|Metrics, IDs, timing|
|**Storage**|Local files, short-term|Time-series DB, long-term|
|**Primary user**|Developer debugging|Ops team monitoring|
|**Answers**|"Why did this fail?"|"Is the system healthy?"|
|**Alert integration**|No|Yes|

### When to Use Each

```
Production observability catches:
  "p99 latency jumped from 2s to 8s in the last hour"
  "Error rate increased from 0.1% to 2%"
  "Token costs doubled this week"

Then you switch to debug tooling:
  "Let me trace some of those slow queries"
  "What's different about the failing requests?"
  "Why are we using more tokens?"
```

---

## What to Observe in Production

The metrics that matter for RAG systems:

### Latency Metrics

|Metric|What It Tells You|Alert Threshold (Example)|
|---|---|---|
|**Total latency p50**|Typical user experience|> 2s|
|**Total latency p99**|Worst-case experience|> 10s|
|**Retrieval latency**|Vector search performance|> 500ms|
|**Rerank latency**|Cross-encoder bottleneck|> 1s|
|**Generation latency**|LLM response time|> 5s|

### Cost Metrics

|Metric|What It Tells You|Alert Threshold|
|---|---|---|
|**Tokens per request (input)**|Context size trends|> 8000 avg|
|**Tokens per request (output)**|Response verbosity|> 1000 avg|
|**Cost per request**|Unit economics|> $0.05|
|**Daily/weekly spend**|Budget tracking|> budget * 1.2|

### Quality Signals

|Metric|What It Tells You|Alert Threshold|
|---|---|---|
|**Error rate**|Pipeline failures|> 1%|
|**Empty retrieval rate**|Queries finding nothing|> 5%|
|**Thumbs down rate**|User dissatisfaction|> 10%|
|**Regeneration rate**|Users retrying|> 15%|

### Volume Metrics

|Metric|What It Tells You|Alert Threshold|
|---|---|---|
|**Requests per minute**|Traffic patterns|Sudden 10x spike|
|**Unique users**|Adoption|Sudden drop|
|**Queries per session**|Engagement|< 1 (users bouncing)|

---

## The Observability Stack

Three layers work together:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Observability Stack                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                       TRACING                               │   │
│   │   • Distributed traces across services                      │   │
│   │   • Spans for each pipeline stage                           │   │
│   │   • Request correlation (trace_id)                          │   │
│   │   • Tools: LangSmith, Langfuse, Jaeger, OpenTelemetry       │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                       METRICS                               │   │
│   │   • Aggregated numbers over time                            │   │
│   │   • Latency percentiles, error rates, throughput            │   │
│   │   • Dashboards and alerting                                 │   │
│   │   • Tools: Prometheus, Datadog, CloudWatch                  │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                       LOGGING                               │   │
│   │   • Structured event logs                                   │   │
│   │   • Searchable by attributes                                │   │
│   │   • Error details and stack traces                          │   │
│   │   • Tools: ELK, Loki, CloudWatch Logs                       │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### What Each Layer Provides

|Layer|Question It Answers|Retention|
|---|---|---|
|**Tracing**|"What happened in this specific request?"|Days to weeks|
|**Metrics**|"How is the system performing overall?"|Months|
|**Logging**|"What errors occurred and why?"|Weeks to months|

For RAG specifically, **tracing** is most valuable — you need to see the flow through retrieval → reranking → generation to diagnose issues.

---

## LangSmith Overview

LangSmith is LangChain's observability platform. Tight integration if you're using LangChain/LangGraph.

### What It Does

- **Tracing**: Automatic capture of chains, retrievers, LLM calls
- **Datasets**: Create evaluation datasets from production traces
- **Evaluation**: Run evals against datasets
- **Monitoring**: Dashboards for latency, costs, errors
- **Playground**: Test prompts against traced inputs

### Integration

```python
# Set environment variables
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-api-key"
os.environ["LANGCHAIN_PROJECT"] = "my-rag-project"

# That's it — LangChain components auto-trace
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_template("Answer: {question}")

chain = prompt | llm
response = chain.invoke({"question": "What is RAG?"})
# Trace automatically sent to LangSmith
```

### For Non-LangChain Code

```python
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

@traceable(name="rag_query")
def query_rag(question: str) -> str:
    # Your custom RAG code
    chunks = retrieve(question)  # Auto-traced if also @traceable
    context = assemble_context(chunks)
    answer = generate(question, context)
    return answer

# Or manual spans
from langsmith import Client
from langsmith.run_trees import RunTree

client = Client()

with RunTree(name="rag_query", run_type="chain") as rt:
    rt.add_metadata({"query": question})
    
    with rt.create_child(name="retrieve", run_type="retriever") as child:
        chunks = retrieve(question)
        child.end(outputs={"chunks": len(chunks)})
    
    # ... more spans
```

### LangSmith Strengths

- Zero-config if using LangChain
- Built-in eval framework
- Production-to-eval workflow (turn traces into test cases)
- Managed service (no infra to run)

### LangSmith Limitations

- SaaS only (no self-hosting for main product)
- Pricing scales with trace volume
- Tightest integration is LangChain-specific
- Data leaves your environment

---

## Langfuse Overview

Langfuse is an open-source LLM observability platform. Self-hostable, framework-agnostic.

### What It Does

- **Tracing**: Hierarchical traces with spans
- **Scoring**: Attach quality scores (human feedback, LLM-as-judge)
- **Prompt Management**: Version and manage prompts
- **Analytics**: Cost tracking, latency dashboards
- **Datasets**: Build eval datasets from traces

### Integration

```python
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

# Initialize client
langfuse = Langfuse(
    public_key="pk-...",
    secret_key="sk-...",
    host="https://cloud.langfuse.com"  # Or your self-hosted URL
)

# Decorator-based tracing
@observe()
def query_rag(question: str) -> str:
    chunks = retrieve(question)
    context = assemble_context(chunks)
    answer = generate(question, context)
    return answer

@observe()
def retrieve(question: str) -> list:
    # Automatically creates a span under parent trace
    results = vector_store.search(question)
    
    # Add metadata to current span
    langfuse_context.update_current_observation(
        metadata={"num_results": len(results)}
    )
    
    return results

@observe()
def generate(question: str, context: str) -> str:
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Context: {context}"},
            {"role": "user", "content": question}
        ]
    )
    
    # Track token usage
    langfuse_context.update_current_observation(
        usage={
            "input": response.usage.prompt_tokens,
            "output": response.usage.completion_tokens
        }
    )
    
    return response.choices[0].message.content
```

### Manual Span Creation

```python
# More control with manual spans
trace = langfuse.trace(
    name="rag_query",
    user_id="user_123",
    metadata={"source": "api"}
)

retrieval_span = trace.span(
    name="retrieve",
    metadata={"query": question}
)
chunks = retrieve(question)
retrieval_span.end(output={"num_chunks": len(chunks)})

generation_span = trace.span(name="generate")
answer = generate(question, context)
generation_span.end(output={"answer": answer})

# Add score (user feedback)
trace.score(
    name="user_feedback",
    value=1,  # thumbs up
    comment="Helpful answer"
)
```

### LlamaIndex Integration

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from langfuse.llama_index import LlamaIndexCallbackHandler

# One-line integration
langfuse_handler = LlamaIndexCallbackHandler()
Settings.callback_manager = CallbackManager([langfuse_handler])

# All LlamaIndex operations now traced
index = VectorStoreIndex.from_documents(documents)
response = index.as_query_engine().query("What is RAG?")
```

### Langfuse Strengths

- Open source (MIT license)
- Self-hostable (Docker, Kubernetes)
- Framework-agnostic (works with anything)
- No vendor lock-in
- Data stays in your environment (if self-hosted)

### Langfuse Limitations

- Self-hosting requires infrastructure management
- Smaller ecosystem than LangSmith
- Fewer built-in integrations
- Community support (vs. enterprise support)

---

## Choosing Between Them

Decision framework:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LangSmith vs. Langfuse Decision                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Are you using LangChain/LangGraph heavily?                        │
│       │                                                             │
│       ├── YES ──► LangSmith (tightest integration)                  │
│       │                                                             │
│       └── NO ──► Continue below                                     │
│                                                                     │
│   Do you need to self-host (data residency, compliance)?            │
│       │                                                             │
│       ├── YES ──► Langfuse (self-hostable)                          │
│       │                                                             │
│       └── NO ──► Continue below                                     │
│                                                                     │
│   Budget constraints?                                               │
│       │                                                             │
│       ├── Tight ──► Langfuse Cloud (generous free tier)             │
│       │             or self-hosted Langfuse                         │
│       │                                                             │
│       └── Flexible ──► Either works, choose by preference           │
│                                                                     │
│   Already have OpenTelemetry infrastructure?                        │
│       │                                                             │
│       ├── YES ──► Langfuse (OTel-native)                            │
│       │                                                             │
│       └── NO ──► Either works                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Quick Comparison

|Factor|LangSmith|Langfuse|
|---|---|---|
|**Best for**|LangChain users|Framework-agnostic needs|
|**Hosting**|SaaS only|SaaS or self-hosted|
|**Open source**|No|Yes (MIT)|
|**LangChain integration**|Native, zero-config|Good, requires setup|
|**LlamaIndex integration**|Manual|Native callback handler|
|**Custom code integration**|`@traceable` decorator|`@observe` decorator|
|**Pricing model**|Per-trace|Per-trace (generous free tier)|
|**Data residency**|US/EU cloud|Your choice (self-host)|

### Other Options

- **Arize Phoenix**: Open-source, strong on evals and embeddings analysis
- **Weights & Biases**: ML-focused, good for experiment tracking
- **Datadog/New Relic**: Enterprise APM with LLM add-ons (2025)
- **OpenTelemetry + Jaeger**: Roll your own with standards

---

## Sampling Strategies

You can't trace every request at full detail in production. Sampling controls the tradeoff between visibility and overhead.

### Head-Based Sampling

Decide at request start whether to trace:

```python
import random

SAMPLE_RATE = 0.01  # Trace 1% of requests

def should_trace() -> bool:
    return random.random() < SAMPLE_RATE

@observe(enabled=should_trace)
def query_rag(question: str) -> str:
    # Only traced 1% of the time
    ...
```

**Pros**: Simple, predictable overhead **Cons**: May miss rare errors (they're in the 99% not sampled)

### Tail-Based Sampling

Decide after request completes, based on outcome:

```python
class TailSampler:
    def __init__(
        self,
        base_rate: float = 0.01,      # Sample 1% normally
        error_rate: float = 1.0,       # Sample 100% of errors
        slow_rate: float = 0.5,        # Sample 50% of slow requests
        slow_threshold_ms: float = 5000
    ):
        self.base_rate = base_rate
        self.error_rate = error_rate
        self.slow_rate = slow_rate
        self.slow_threshold_ms = slow_threshold_ms
    
    def should_export(
        self,
        trace: DebugTrace,
        error: Exception | None
    ) -> bool:
        # Always sample errors
        if error is not None:
            return random.random() < self.error_rate
        
        # Sample slow requests more
        if trace.total_time_ms > self.slow_threshold_ms:
            return random.random() < self.slow_rate
        
        # Base rate for normal requests
        return random.random() < self.base_rate


# Usage
sampler = TailSampler()

def query_rag(question: str) -> str:
    trace = DebugTrace()
    error = None
    
    try:
        answer = run_pipeline(question, trace)
    except Exception as e:
        error = e
        raise
    finally:
        if sampler.should_export(trace, error):
            export_to_observability(trace)
    
    return answer
```

**Pros**: Captures interesting cases (errors, slow requests) **Cons**: More complex, requires buffering trace until completion

### Error-Triggered Full Capture

Normal requests get metrics only. Errors get full trace:

```python
class AdaptiveTracer:
    def __init__(self, observability_client):
        self.client = observability_client
    
    def trace_request(self, question: str) -> str:
        trace_id = generate_trace_id()
        start = time.perf_counter()
        
        # Always capture lightweight metrics
        metrics = {"trace_id": trace_id, "query_length": len(question)}
        
        # Buffer for potential full trace
        trace_buffer = DebugTrace()
        
        try:
            answer = run_pipeline(question, trace_buffer)
            
            # Success — just send metrics
            metrics["latency_ms"] = (time.perf_counter() - start) * 1000
            metrics["status"] = "success"
            self.client.send_metrics(metrics)
            
        except Exception as e:
            # Error — send full trace
            metrics["latency_ms"] = (time.perf_counter() - start) * 1000
            metrics["status"] = "error"
            metrics["error"] = str(e)
            
            self.client.send_metrics(metrics)
            self.client.send_full_trace(trace_buffer)  # Full details
            
            raise
        
        return answer
```

### Sampling Rate Guidelines

|Traffic Level|Recommended Sampling|
|---|---|
|< 100 req/day|100% (trace everything)|
|100 - 1K req/day|10-50% base, 100% errors|
|1K - 10K req/day|1-10% base, 100% errors|
|10K - 100K req/day|0.1-1% base, 100% errors, 10% slow|
|> 100K req/day|0.01-0.1% base, sample errors too|

---

## Performance Budget

Observability should be invisible to users. Set a strict overhead budget.

### Overhead Targets

|Component|Target Overhead|Actual (Typical)|
|---|---|---|
|Creating trace context|< 0.1ms|0.05ms|
|Recording span timing|< 0.1ms per span|0.02ms|
|Buffering trace data|< 1ms|0.5ms|
|Async export|0ms (background)|0ms|
|**Total request overhead**|**< 5ms**|**1-3ms**|

### Async Export Pattern

Never block the response on trace export:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AsyncTraceExporter:
    def __init__(self, client, max_workers: int = 4):
        self.client = client
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.queue = asyncio.Queue(maxsize=1000)
    
    def export(self, trace: dict):
        """Non-blocking export — returns immediately."""
        try:
            # Submit to background thread
            self.executor.submit(self._do_export, trace)
        except Exception:
            # Queue full or executor problem — drop trace
            # Better to drop observability than slow user
            pass
    
    def _do_export(self, trace: dict):
        """Actual export in background thread."""
        try:
            self.client.send(trace)
        except Exception as e:
            # Log but don't propagate
            logging.warning(f"Failed to export trace: {e}")


# Usage
exporter = AsyncTraceExporter(langfuse_client)

def query_rag(question: str) -> str:
    trace = capture_trace(question)
    answer = run_pipeline(question)
    
    exporter.export(trace)  # Returns immediately
    
    return answer  # Response not blocked
```

### What NOT to Log

Avoid capturing these in production traces:

|Don't Log|Why|
|---|---|
|Full embeddings|1536+ floats per query = huge|
|Full document text|Megabytes per request|
|Complete prompts (always)|Token-heavy, sample instead|
|PII without scrubbing|Compliance risk|
|Raw API keys/secrets|Security risk|

### Lightweight Production Trace

```python
@dataclass
class ProductionTrace:
    """Minimal trace for production — metrics only."""
    trace_id: str
    timestamp: str
    
    # Query (truncated)
    query_preview: str  # First 100 chars
    query_hash: str     # For dedup without storing full query
    
    # Counts only
    retrieved_count: int
    context_chunks: int
    context_tokens: int
    
    # Timing
    retrieval_ms: float
    rerank_ms: float
    generation_ms: float
    total_ms: float
    
    # Outcome
    status: str  # "success", "error", "timeout"
    error_type: str | None
    
    # User signals (if available)
    user_id: str | None
    feedback: int | None  # 1 = positive, -1 = negative


def to_production_trace(full_trace: DebugTrace) -> ProductionTrace:
    """Convert full trace to lightweight production format."""
    return ProductionTrace(
        trace_id=full_trace.trace_id,
        timestamp=full_trace.timestamp,
        query_preview=full_trace.original_query[:100],
        query_hash=hashlib.md5(full_trace.original_query.encode()).hexdigest(),
        retrieved_count=len(full_trace.retrieval.fused_results),
        context_chunks=len(full_trace.context.selected_chunks),
        context_tokens=full_trace.context.token_count,
        retrieval_ms=full_trace.retrieval.dense_time_ms,
        rerank_ms=full_trace.context.reranker_time_ms,
        generation_ms=full_trace.generation.generation_time_ms,
        total_ms=full_trace.total_time_ms,
        status="success" if not full_trace.error else "error",
        error_type=type(full_trace.error).__name__ if full_trace.error else None,
        user_id=None,
        feedback=None
    )
```

---

## Alerting on RAG Failures

Good alerts catch problems early. Bad alerts create noise that gets ignored.

### What to Alert On

|Alert|Condition|Severity|Action|
|---|---|---|---|
|**Error rate spike**|> 5% errors in 5 min|High|Investigate immediately|
|**Latency degradation**|p99 > 2x baseline for 10 min|High|Check infra, model provider|
|**Cost anomaly**|Daily spend > 150% of 7-day avg|Medium|Review traffic, check for abuse|
|**Empty retrieval spike**|> 20% queries find nothing|Medium|Check index health|
|**Feedback drop**|Thumbs-up rate < 50% for 1 hour|Medium|Review recent changes|
|**Provider errors**|OpenAI/Anthropic 5xx > 1%|High|Check status page, consider fallback|

### What NOT to Alert On

|Don't Alert|Why|
|---|---|
|Every single error|Noise — some errors are expected|
|Low-traffic anomalies|1 error in 10 requests = 10% but meaningless|
|Brief latency spikes|< 1 min spikes are often transient|
|Individual user complaints|Handle via support, not alerts|

### Alert Configuration Example

```python
# Prometheus/Alertmanager style rules

alert_rules = [
    {
        "name": "RAGHighErrorRate",
        "expr": "rate(rag_errors_total[5m]) / rate(rag_requests_total[5m]) > 0.05",
        "for": "5m",
        "severity": "critical",
        "annotations": {
            "summary": "RAG error rate above 5%",
            "description": "Error rate is {{ $value | humanizePercentage }}"
        }
    },
    {
        "name": "RAGLatencyHigh",
        "expr": "histogram_quantile(0.99, rate(rag_latency_seconds_bucket[5m])) > 10",
        "for": "10m",
        "severity": "warning",
        "annotations": {
            "summary": "RAG p99 latency above 10s",
            "description": "p99 latency is {{ $value | humanizeDuration }}"
        }
    },
    {
        "name": "RAGCostAnomaly",
        "expr": "sum(increase(rag_token_cost_dollars[1d])) > 1.5 * avg_over_time(sum(increase(rag_token_cost_dollars[1d]))[7d:1d])",
        "for": "1h",
        "severity": "warning",
        "annotations": {
            "summary": "RAG daily cost 50% above weekly average"
        }
    }
]
```

### Metrics to Export

```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
rag_requests_total = Counter(
    "rag_requests_total",
    "Total RAG requests",
    ["status"]  # success, error
)

rag_errors_total = Counter(
    "rag_errors_total",
    "Total RAG errors",
    ["error_type"]  # retrieval_error, generation_error, timeout
)

# Histograms
rag_latency_seconds = Histogram(
    "rag_latency_seconds",
    "RAG request latency",
    ["stage"],  # retrieval, rerank, generation, total
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
)

rag_tokens_used = Histogram(
    "rag_tokens_used",
    "Tokens used per request",
    ["type"],  # input, output
    buckets=[100, 500, 1000, 2000, 4000, 8000, 16000]
)

# Gauges
rag_active_requests = Gauge(
    "rag_active_requests",
    "Currently processing RAG requests"
)


# Instrument your pipeline
def query_rag(question: str) -> str:
    rag_active_requests.inc()
    
    try:
        with rag_latency_seconds.labels(stage="total").time():
            
            with rag_latency_seconds.labels(stage="retrieval").time():
                chunks = retrieve(question)
            
            with rag_latency_seconds.labels(stage="rerank").time():
                reranked = rerank(chunks)
            
            with rag_latency_seconds.labels(stage="generation").time():
                answer, usage = generate(question, reranked)
        
        rag_tokens_used.labels(type="input").observe(usage.prompt_tokens)
        rag_tokens_used.labels(type="output").observe(usage.completion_tokens)
        rag_requests_total.labels(status="success").inc()
        
        return answer
        
    except Exception as e:
        rag_requests_total.labels(status="error").inc()
        rag_errors_total.labels(error_type=type(e).__name__).inc()
        raise
        
    finally:
        rag_active_requests.dec()
```

---

## Putting It Together

A production-ready observability setup:

```python
from langfuse.decorators import observe, langfuse_context
from prometheus_client import Counter, Histogram
import logging

# Metrics
request_counter = Counter("rag_requests", "Total requests", ["status"])
latency_histogram = Histogram("rag_latency_seconds", "Latency", ["stage"])

# Logger
logger = logging.getLogger("rag")


class ProductionRAG:
    def __init__(self, pipeline, sample_rate: float = 0.01):
        self.pipeline = pipeline
        self.sample_rate = sample_rate
    
    def query(self, question: str, user_id: str = None) -> str:
        """
        Production query with full observability.
        """
        trace_id = generate_trace_id()
        should_trace = random.random() < self.sample_rate
        
        # Structured log for every request
        logger.info(
            "rag_request_start",
            extra={
                "trace_id": trace_id,
                "user_id": user_id,
                "query_length": len(question)
            }
        )
        
        start = time.perf_counter()
        
        try:
            # Run with optional detailed tracing
            if should_trace:
                answer = self._query_with_trace(question, trace_id, user_id)
            else:
                answer = self._query_minimal(question)
            
            # Record success
            latency = time.perf_counter() - start
            latency_histogram.labels(stage="total").observe(latency)
            request_counter.labels(status="success").inc()
            
            logger.info(
                "rag_request_complete",
                extra={
                    "trace_id": trace_id,
                    "latency_ms": latency * 1000,
                    "status": "success"
                }
            )
            
            return answer
            
        except Exception as e:
            latency = time.perf_counter() - start
            request_counter.labels(status="error").inc()
            
            logger.error(
                "rag_request_error",
                extra={
                    "trace_id": trace_id,
                    "latency_ms": latency * 1000,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            # Always trace errors fully
            self._export_error_trace(question, e, trace_id)
            
            raise
    
    @observe(name="rag_query")
    def _query_with_trace(
        self,
        question: str,
        trace_id: str,
        user_id: str
    ) -> str:
        """Query with full Langfuse tracing."""
        langfuse_context.update_current_trace(
            user_id=user_id,
            session_id=trace_id,
            metadata={"sampled": True}
        )
        
        return self.pipeline.query(question)
    
    def _query_minimal(self, question: str) -> str:
        """Query with metrics only, no detailed trace."""
        return self.pipeline.query(question)
    
    def _export_error_trace(
        self,
        question: str,
        error: Exception,
        trace_id: str
    ):
        """Capture full trace for errors."""
        # Full trace capture for debugging
        trace = DebugTrace()
        try:
            self.pipeline.query(question, trace=trace)
        except:
            pass  # Expected to fail again
        
        # Export to observability platform
        langfuse.trace(
            name="error_trace",
            id=trace_id,
            metadata={
                "error": str(error),
                "error_type": type(error).__name__,
                "full_trace": trace.__dict__
            }
        )
```

---

## Key Takeaways

1. **Debug tooling ≠ production observability** — Debug is deep/narrow for investigation. Observability is shallow/wide for monitoring. You need both.
    
2. **Observe latency, cost, errors, quality** — These four categories cover what matters. Set baselines, alert on deviations.
    
3. **LangSmith for LangChain shops, Langfuse for flexibility** — LangSmith has tighter LangChain integration. Langfuse is open-source and self-hostable.
    
4. **Sample aggressively in production** — 1% sampling is often enough for trends. Use tail-based sampling to capture 100% of errors and slow requests.
    
5. **Performance budget: < 5ms overhead** — Use async export, lightweight trace formats, and never block responses on observability.
    
6. **Alert on patterns, not individuals** — Error rate spikes, latency degradation, cost anomalies. Not individual errors.
    
7. **Structured logging complements tracing** — Traces for request flow, logs for searchable events, metrics for dashboards. Each layer serves a purpose.
    
8. **Errors get full traces, always** — Normal requests can be sampled or minimal. Errors should capture everything for debugging.