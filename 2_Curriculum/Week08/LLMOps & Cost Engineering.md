# Week 8: Combined Phase — LLMOps & Cost Engineering

> **Track:** Combined (LLMOps focus) **Time:** 2 hours/day **Goal:** Make your Research Assistant production-viable with proper ops: logging, monitoring, caching, cost controls, and rate limiting.

---

## Overview

| Days | Topic                             | Output                         |
| ---- | --------------------------------- | ------------------------------ |
| 1-2  | Production Logging & Monitoring   | Monitoring infrastructure      |
| 3-4  | Caching Strategies                | Caching layer implemented      |
| 5-6  | Cost Optimization & Rate Limiting | Cost controls + quotas         |
| 7    | Mini Build                        | Research Assistant with LLMOps |

---

## Days 1-2: Production Logging & Monitoring

### Why This Matters

Week 7 gave you observability (tracing individual requests). Production monitoring is different:

- **Tracing**: "What happened in this specific request?"
- **Monitoring**: "How is the system behaving overall? Is something wrong?"

You need both. Tracing helps debug individual failures. Monitoring catches systemic issues before users complain:

- Latency creeping up over time
- Error rate spiking after a deployment
- Costs exceeding budget
- One user consuming 80% of resources

### What to Learn

**Core Concepts:**

**The Three Pillars of Observability:**

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│      LOGS       │  │     METRICS     │  │     TRACES      │
│                 │  │                 │  │                 │
│ What happened   │  │ Aggregate       │  │ Request flow    │
│ (events)        │  │ measurements    │  │ (spans)         │
│                 │  │                 │  │                 │
│ "Error at 14:32"│  │ "p95 = 850ms"   │  │ "A → B → C"     │
│ "User X query"  │  │ "Error rate 2%" │  │ "Step B slow"   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                    Combined = Full Picture
```

**What to Log in LLM Systems:**

```python
# Structured log entry for an LLM request
log_entry = {
    "timestamp": "2024-01-15T14:32:05Z",
    "request_id": "req_abc123",
    "user_id": "user_456",
    
    # Request details
    "query": "What is our refund policy?",  # Or hash if sensitive
    "query_type": "internal_docs",
    
    # Execution details
    "tools_used": ["rag", "none"],
    "rag_chunks_retrieved": 5,
    "model": "gpt-4o-mini",
    "input_tokens": 1500,
    "output_tokens": 350,
    
    # Performance
    "latency_ms": 850,
    "latency_breakdown": {
        "retrieval_ms": 200,
        "rerank_ms": 50,
        "generation_ms": 580
    },
    
    # Cost
    "estimated_cost_usd": 0.0032,
    
    # Outcome
    "status": "success",  # or "error", "timeout", "rate_limited"
    "error_type": None,
    "error_message": None
}
```

**Key Metrics to Track:**

```
LATENCY METRICS
├── p50_latency_ms (median)
├── p95_latency_ms (95th percentile - what most users experience)
├── p99_latency_ms (99th percentile - worst case)
└── latency_by_step (retrieval, rerank, generation)

THROUGHPUT METRICS
├── requests_per_minute
├── tokens_per_minute
└── concurrent_requests

ERROR METRICS
├── error_rate (% of requests failing)
├── errors_by_type (timeout, rate_limit, model_error, retrieval_empty)
└── errors_by_user (is one user causing issues?)

COST METRICS
├── cost_per_request_avg
├── cost_per_user
├── daily_cost
├── cost_by_model
└── cost_by_feature (RAG vs web search vs generation)

BUSINESS METRICS
├── queries_per_user
├── query_types_distribution
└── cache_hit_rate (once caching is added)
```

**Alerting Rules:**

```yaml
alerts:
  - name: high_error_rate
    condition: error_rate > 5% for 5 minutes
    severity: critical
    
  - name: latency_degradation
    condition: p95_latency > 3000ms for 10 minutes
    severity: warning
    
  - name: cost_spike
    condition: hourly_cost > 2x average
    severity: warning
    
  - name: single_user_abuse
    condition: user_requests_per_hour > 500
    severity: warning
```

**Practical Skills:**

- Implement structured logging
- Set up metrics collection
- Create monitoring dashboards
- Configure alerts for anomalies

### Resources

**Primary:**

- Python structlog: https://www.structlog.org/
- Prometheus Python Client: https://prometheus.github.io/client_python/
- Grafana Dashboards: https://grafana.com/docs/grafana/latest/dashboards/

**Secondary:**

- Search: "structured logging python best practices"
- Search: "prometheus metrics LLM applications"
- Search: "grafana dashboard tutorial"

### Day 1 Tasks (2 hours)

**Hour 1 — Learn + Design:**

1. Understand the difference between logs, metrics, and traces (15 min)
2. Review the log schema above — what would you add for your Research Assistant? (15 min)
3. Design your metrics:
    
    ```python
    # What metrics do you need?METRICS = {    # Latency    "request_latency_seconds": "Histogram",  # Distribution of latencies    "step_latency_seconds": "Histogram",  # Per step (retrieval, generation)        # Throughput    "requests_total": "Counter",  # Total requests (with labels: status, type)    "tokens_total": "Counter",  # Total tokens (with labels: model, direction)        # Cost    "cost_usd_total": "Counter",  # Running cost total        # Gauges (current values)    "active_requests": "Gauge",  # Currently processing    "cache_size": "Gauge",  # Cache entries}
    ```
    
4. Think: What labels/dimensions do you need? (by user, by model, by query type?) (15 min)

**Hour 2 — Implement Structured Logging:**

1. Set up structured logging:
    
    ```python
    import structlogimport loggingfrom datetime import datetime# Configure structlogstructlog.configure(    processors=[        structlog.stdlib.filter_by_level,        structlog.stdlib.add_logger_name,        structlog.stdlib.add_log_level,        structlog.processors.TimeStamper(fmt="iso"),        structlog.processors.JSONRenderer()    ],    wrapper_class=structlog.stdlib.BoundLogger,    context_class=dict,    logger_factory=structlog.stdlib.LoggerFactory(),)logger = structlog.get_logger()# Usage in your codedef process_query(query: str, user_id: str):    request_id = generate_request_id()    log = logger.bind(request_id=request_id, user_id=user_id)        log.info("request_started", query_length=len(query))        try:        start = time.time()        result = do_work(query)        latency = time.time() - start                log.info(            "request_completed",            latency_ms=latency * 1000,            tokens_used=result.tokens,            status="success"        )        return result            except Exception as e:        log.error(            "request_failed",            error_type=type(e).__name__,            error_message=str(e)        )        raise
    ```
    
2. Add structured logging to your Research Assistant
3. Run 10 queries, examine the JSON logs
4. Can you answer: "What was the average latency? Which queries failed?"

### Day 2 Tasks (2 hours)

**Hour 1 — Implement Metrics:**

1. Set up Prometheus metrics:
    
    ```python
    from prometheus_client import (    Counter, Histogram, Gauge,     start_http_server, REGISTRY)# Define metricsREQUEST_LATENCY = Histogram(    'research_assistant_request_latency_seconds',    'Request latency in seconds',    ['query_type', 'status'],    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0])REQUEST_COUNT = Counter(    'research_assistant_requests_total',    'Total requests',    ['query_type', 'status'])TOKENS_USED = Counter(    'research_assistant_tokens_total',    'Total tokens used',    ['model', 'direction']  # direction: input/output)COST_USD = Counter(    'research_assistant_cost_usd_total',    'Total cost in USD',    ['model'])ACTIVE_REQUESTS = Gauge(    'research_assistant_active_requests',    'Currently processing requests')# Instrument your codedef process_query(query: str):    ACTIVE_REQUESTS.inc()    query_type = classify_query(query)        try:        with REQUEST_LATENCY.labels(            query_type=query_type,             status="success"        ).time():            result = do_work(query)                REQUEST_COUNT.labels(            query_type=query_type,             status="success"        ).inc()                TOKENS_USED.labels(            model=result.model,             direction="input"        ).inc(result.input_tokens)                TOKENS_USED.labels(            model=result.model,             direction="output"        ).inc(result.output_tokens)                COST_USD.labels(model=result.model).inc(result.cost)                return result            except Exception as e:        REQUEST_COUNT.labels(            query_type=query_type,             status="error"        ).inc()        raise            finally:        ACTIVE_REQUESTS.dec()# Start metrics serverstart_http_server(8000)  # Metrics at http://localhost:8000/metrics
    ```
    
2. Add metrics to your Research Assistant
3. Run queries, check http://localhost:8000/metrics

**Hour 2 — Mini Challenge: Monitoring Dashboard**

Create a `MonitoringSystem` class:

```python
class MonitoringSystem:
    def __init__(self, metrics_port: int = 8000):
        """
        Production monitoring for Research Assistant.
        """
        self.logger = self._setup_logging()
        self._setup_metrics()
        self.alerts = []
    
    def log_request(
        self,
        request_id: str,
        user_id: str,
        query: str,
        result: dict,
        latency_ms: float,
        tokens: dict,
        cost_usd: float,
        status: str,
        error: str = None
    ) -> None:
        """Log a request with full context."""
        pass
    
    def record_metrics(
        self,
        query_type: str,
        status: str,
        latency_seconds: float,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float
    ) -> None:
        """Record Prometheus metrics."""
        pass
    
    def check_alerts(self) -> list[dict]:
        """
        Check alert conditions and return triggered alerts.
        
        Returns:
            [
                {
                    "name": "high_error_rate",
                    "severity": "critical",
                    "message": "Error rate 8.5% exceeds threshold 5%",
                    "triggered_at": "2024-01-15T14:32:00Z"
                }
            ]
        """
        pass
    
    def get_dashboard_data(self, last_n_minutes: int = 60) -> dict:
        """
        Get data for a monitoring dashboard.
        
        Returns:
            {
                "summary": {
                    "total_requests": 150,
                    "success_rate": 0.97,
                    "avg_latency_ms": 650,
                    "p95_latency_ms": 1200,
                    "total_cost_usd": 1.25
                },
                "time_series": {
                    "requests_per_minute": [...],
                    "latency_p95_per_minute": [...],
                    "error_rate_per_minute": [...]
                },
                "breakdowns": {
                    "by_query_type": {...},
                    "by_model": {...},
                    "by_user": {...}  # Top users
                },
                "alerts": [...]
            }
        """
        pass
```

**Success Criteria:**

- [ ] Structured JSON logging implemented
- [ ] Prometheus metrics exposed at /metrics endpoint
- [ ] Request latency tracked as histogram (with percentiles)
- [ ] Tokens and cost tracked as counters
- [ ] Error rate calculable from metrics
- [ ] At least 3 alert conditions defined
- [ ] Dashboard data aggregation working
- [ ] Tested: Run 20 queries, verify logs and metrics are accurate

### 5 Things to Ponder

1. You log every query for debugging. But queries contain user data — potentially sensitive. GDPR requires data minimization. How do you balance debuggability with privacy? Hash queries? Redact PII? Separate storage with access controls?
    
2. Your p95 latency is 1200ms, p99 is 3500ms. The p99 users have a terrible experience. Do you optimize for p99 (expensive, helps few) or accept that some requests are slow? How do you decide what latency is "acceptable"?
    
3. You alert on "error rate > 5% for 5 minutes." But what's an "error"? Timeout is clear. What about "retrieval returned no results"? What about "answer was low quality"? How do you define errors operationally?
    
4. Your monitoring shows costs are 2x budget. You need to cut costs. But you don't know _where_ the cost is going — is it a few expensive queries? Many cheap ones? Bad caching? How does monitoring data inform cost optimization?
    
5. You're collecting metrics. But nobody's looking at the dashboard. An alert fires, but it's the 10th alert today, so it's ignored. How do you make monitoring _actionable_? How do you avoid alert fatigue?
    

---

## Days 3-4: Caching Strategies

### Why This Matters

LLM calls are:

- Slow (hundreds of milliseconds to seconds)
- Expensive ($0.001 - $0.01+ per call)
- Often redundant (same or similar questions asked repeatedly)

Caching addresses all three:

- Return cached response instantly (latency: ~1ms vs ~500ms)
- No API cost for cache hits
- Handle repeated queries effortlessly

A good caching strategy can reduce costs and latency by 50-90% in many applications.

### What to Learn

**Core Concepts:**

**Types of Caching in LLM Systems:**

```
1. EXACT MATCH CACHE
   "What is our refund policy?" → cached answer
   Same exact query returns cached result
   Simple, fast, limited hit rate

2. SEMANTIC CACHE
   "What is our refund policy?" → cached
   "Tell me about refunds" → CACHE HIT (semantically similar)
   Uses embeddings to find similar queries
   Higher hit rate, more complex

3. EMBEDDING CACHE
   Don't recompute embeddings for seen text
   Useful when same chunks are retrieved repeatedly

4. RETRIEVAL CACHE
   Cache retrieval results (not just final answers)
   "refund policy" query → cached chunks
   Faster even if generation differs

5. LLM RESPONSE CACHE
   Cache raw LLM API responses
   Keyed by prompt hash
   Works across different user sessions
```

**Cache Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                         User Query                          │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Semantic Cache    │
                    │ Check             │
                    └─────────┬─────────┘
                              │
               ┌──────────────┴──────────────┐
               │                             │
          Cache Hit                     Cache Miss
               │                             │
               ▼                             ▼
        Return Cached              ┌─────────────────┐
        Response                   │ Embedding Cache │
                                   │ Check           │
                                   └────────┬────────┘
                                            │
                              ┌─────────────┴─────────────┐
                              │                           │
                         Cache Hit                   Cache Miss
                              │                           │
                              ▼                           ▼
                       Use Cached                  Compute Embedding
                       Embedding                   (cache result)
                              │                           │
                              └─────────────┬─────────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │ Retrieval Cache │
                                   │ Check           │
                                   └────────┬────────┘
                                            │
                              ┌─────────────┴─────────────┐
                              │                           │
                         Cache Hit                   Cache Miss
                              │                           │
                              ▼                           ▼
                       Use Cached                    Run Retrieval
                       Chunks                        (cache result)
                              │                           │
                              └─────────────┬─────────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │   Generation    │
                                   │   (LLM Call)    │
                                   └────────┬────────┘
                                            │
                                            ▼
                                   Cache Final Answer
                                   (semantic cache)
                                            │
                                            ▼
                                      Return Response
```

**Cache Invalidation:**

```python
# When to invalidate cache:

# 1. TTL (Time To Live)
cache.set(key, value, ttl=3600)  # Expire after 1 hour

# 2. Document updates
def on_document_update(doc_id):
    # Invalidate any cached queries that used this doc
    cache.invalidate_by_tag(f"doc:{doc_id}")

# 3. Version-based
cache_key = f"{query_hash}:v{model_version}:{config_hash}"

# 4. Manual purge
cache.clear()  # Nuclear option
```

**Practical Skills:**

- Implement exact-match caching
- Implement semantic caching with embeddings
- Design cache keys and invalidation strategies
- Measure cache hit rates and savings

### Resources

**Primary:**

- Redis Python: https://redis.io/docs/clients/python/
- GPTCache: https://github.com/zilliztech/GPTCache
- LangChain Caching: https://python.langchain.com/docs/how_to/llm_caching/

**Secondary:**

- Search: "semantic caching LLM"
- Search: "GPTCache tutorial"
- Search: "redis caching best practices"

### Day 3 Tasks (2 hours)

**Hour 1 — Learn + Design:**

1. Understand the different cache types above (20 min)
2. Think through: Which caches would help your Research Assistant most?
    - Are queries often repeated exactly? → Exact match
    - Are queries often similar but not identical? → Semantic
    - Is embedding computation a bottleneck? → Embedding cache
    - Is retrieval slow? → Retrieval cache
3. Design your caching strategy:
    
    ```python
    # For Research Assistant, likely priority:# 1. Semantic cache (highest value - similar questions common)# 2. Retrieval cache (retrieval is slow, reused across similar queries)# 3. Embedding cache (cheaper computation savings)
    ```
    
4. Choose your cache backend:
    - **In-memory dict**: Simplest, lost on restart, fine for dev
    - **Redis**: Production standard, persistent, fast
    - **SQLite**: Simple persistence, single-machine

**Hour 2 — Implement Exact Match Cache:**

1. Start simple — exact match:
    
    ```python
    import hashlibimport jsonfrom datetime import datetime, timedeltaclass ExactMatchCache:    def __init__(self, ttl_seconds: int = 3600):        self.cache = {}        self.ttl = ttl_seconds        def _hash_query(self, query: str, config: dict) -> str:        """Create cache key from query + config."""        key_data = json.dumps({            "query": query.lower().strip(),            "config": config        }, sort_keys=True)        return hashlib.sha256(key_data.encode()).hexdigest()        def get(self, query: str, config: dict = None) -> dict | None:        """Get cached result if exists and not expired."""        key = self._hash_query(query, config or {})                if key not in self.cache:            return None                entry = self.cache[key]        if datetime.now() > entry["expires_at"]:            del self.cache[key]            return None                return entry["value"]        def set(self, query: str, result: dict, config: dict = None) -> None:        """Cache a result."""        key = self._hash_query(query, config or {})        self.cache[key] = {            "value": result,            "created_at": datetime.now(),            "expires_at": datetime.now() + timedelta(seconds=self.ttl)        }        def stats(self) -> dict:        """Get cache statistics."""        return {            "size": len(self.cache),            "memory_mb": self._estimate_memory()        }
    ```
    
2. Integrate into your Research Assistant:
    
    ```python
    class CachedResearchAssistant:    def __init__(self, assistant, cache):        self.assistant = assistant        self.cache = cache        self.hits = 0        self.misses = 0        def research(self, query: str) -> dict:        # Check cache        cached = self.cache.get(query)        if cached:            self.hits += 1            return {**cached, "_cache": "hit"}                # Cache miss - do real work        self.misses += 1        result = self.assistant.research(query)                # Cache the result        self.cache.set(query, result)        return {**result, "_cache": "miss"}        def hit_rate(self) -> float:        total = self.hits + self.misses        return self.hits / total if total > 0 else 0.0
    ```
    
3. Test: Same query twice → second should be instant
4. Test: Slightly different query → cache miss (exact match limitation)

### Day 4 Tasks (2 hours)

**Hour 1 — Implement Semantic Cache:**

1. Semantic cache uses embeddings to find similar queries:
    
    ```python
    import numpy as npfrom typing import Optionalclass SemanticCache:    def __init__(        self,        embedding_model,        similarity_threshold: float = 0.95,        ttl_seconds: int = 3600,        max_entries: int = 10000    ):        self.embedding_model = embedding_model        self.threshold = similarity_threshold        self.ttl = ttl_seconds        self.max_entries = max_entries                # Storage        self.entries = []  # [{query, embedding, result, created_at}]        def _get_embedding(self, text: str) -> np.ndarray:        """Get embedding for text."""        return self.embedding_model.embed(text)        def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:        """Compute cosine similarity."""        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))        def get(self, query: str) -> Optional[dict]:        """Find semantically similar cached query."""        query_embedding = self._get_embedding(query)                best_match = None        best_similarity = 0.0                for entry in self.entries:            # Skip expired            if self._is_expired(entry):                continue                        similarity = self._cosine_similarity(                query_embedding,                 entry["embedding"]            )                        if similarity > self.threshold and similarity > best_similarity:                best_similarity = similarity                best_match = entry                if best_match:            return {                **best_match["result"],                "_cache_similarity": best_similarity,                "_cache_original_query": best_match["query"]            }                return None        def set(self, query: str, result: dict) -> None:        """Add to cache."""        # Evict oldest if at capacity        if len(self.entries) >= self.max_entries:            self.entries = self.entries[1:]                self.entries.append({            "query": query,            "embedding": self._get_embedding(query),            "result": result,            "created_at": datetime.now()        })
    ```
    
2. Test semantic similarity:
    - "What is the refund policy?" → cache
    - "Tell me about refunds" → should hit (similar)
    - "What is the vacation policy?" → should miss (different topic)
3. Tune the similarity threshold — what works for your queries?

**Hour 2 — Mini Challenge: Multi-Level Cache**

Build a `CacheSystem` that combines strategies:

```python
class CacheSystem:
    def __init__(
        self,
        embedding_model,
        exact_match_ttl: int = 3600,
        semantic_threshold: float = 0.92,
        semantic_ttl: int = 7200,
        retrieval_ttl: int = 1800,
        enable_exact: bool = True,
        enable_semantic: bool = True,
        enable_retrieval: bool = True
    ):
        """
        Multi-level caching for Research Assistant.
        
        Levels:
        1. Exact match (fastest, strictest)
        2. Semantic (slower, catches similar queries)
        3. Retrieval (cache chunks, skip retrieval step)
        """
        pass
    
    def get_answer(self, query: str, config: dict = None) -> dict | None:
        """
        Check all cache levels for answer.
        
        Returns:
            {
                "result": {...},
                "cache_level": "exact|semantic|none",
                "similarity": 0.95,  # if semantic
                "latency_ms": 5
            }
        """
        pass
    
    def get_retrieval(self, query: str) -> list | None:
        """Get cached retrieval results."""
        pass
    
    def set_answer(
        self, 
        query: str, 
        result: dict, 
        chunks_used: list = None,
        config: dict = None
    ) -> None:
        """Cache answer and optionally retrieval results."""
        pass
    
    def set_retrieval(self, query: str, chunks: list) -> None:
        """Cache retrieval results."""
        pass
    
    def invalidate_for_document(self, doc_id: str) -> int:
        """
        Invalidate cache entries that used a specific document.
        Returns number of entries invalidated.
        """
        pass
    
    def stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            {
                "exact_match": {"size": 100, "hits": 50, "misses": 200},
                "semantic": {"size": 500, "hits": 150, "misses": 100},
                "retrieval": {"size": 300, "hits": 80, "misses": 170},
                "overall_hit_rate": 0.42,
                "estimated_savings_usd": 2.50,
                "latency_reduction_ms": 15000  # Total ms saved
            }
        """
        pass
    
    def clear(self, level: str = None) -> None:
        """Clear cache. If level specified, clear only that level."""
        pass
```

**Success Criteria:**

- [ ] Exact match cache working (same query → instant hit)
- [ ] Semantic cache working (similar queries → hit)
- [ ] Similarity threshold tuned (not too loose, not too strict)
- [ ] Retrieval cache working (skip retrieval step on hit)
- [ ] Cache stats tracked (hits, misses, savings)
- [ ] Document invalidation working
- [ ] Tested: 20 queries including repeats and similar → measure hit rate
- [ ] Hit rate > 30% on realistic query mix

### 5 Things to Ponder

1. Semantic cache similarity threshold of 0.95 is strict — high precision, low recall. 0.85 catches more but might return wrong answers. How do you find the right threshold? Is it the same for all query types?
    
2. User asks "What's the refund policy?" (cached). Later, the refund policy document is updated. The cache returns stale information. How do you handle document updates? Invalidate all related cache? Version the cache?
    
3. Your cache has 10,000 entries. Semantic lookup requires comparing against all of them — O(n) per query. At scale, this is slow. How would you make semantic cache lookup faster? (Hint: Vector indexes like HNSW)
    
4. You cache final answers. But the answer depends on context from conversation history. User A asks "What about refunds?" in a conversation about Product X. User B asks the same in a conversation about Product Y. Same query, different correct answers. How do you handle context-dependent queries?
    
5. Cache hit rate is 60%. Great for cost savings. But what about the 40% cache misses? If semantic cache returns "no hit," you still paid for an embedding computation. At what hit rate does semantic caching stop being worth the embedding cost?
    

---

## Days 5-6: Cost Optimization & Rate Limiting

### Why This Matters

LLM costs can spiral quickly:

- Development: $10/day → "This is fine"
- Soft launch: $100/day → "Okay, need to watch this"
- Production: $1000/day → "We need controls NOW"
- Viral moment: $10,000/day → "We're shutting down"

Cost optimization and rate limiting are not optional for production. They're survival mechanisms.

### What to Learn

**Core Concepts:**

**Cost Optimization Strategies:**

```
1. MODEL SELECTION BY TASK
   ┌─────────────────────────┬─────────────────┬──────────────┐
   │ Task                    │ Model           │ Cost/1M tok  │
   ├─────────────────────────┼─────────────────┼──────────────┤
   │ Query classification    │ gpt-4o-mini     │ $0.15 input  │
   │ Simple generation       │ gpt-4o-mini     │ $0.60 output │
   │ Complex reasoning       │ gpt-4o          │ $2.50 input  │
   │ Embeddings             │ text-embed-3-sm │ $0.02 input  │
   └─────────────────────────┴─────────────────┴──────────────┘
   
   Strategy: Use cheap models for cheap tasks

2. TOKEN BUDGETING
   - Set max input/output tokens per request
   - Truncate context intelligently
   - Summarize instead of include

3. PROMPT OPTIMIZATION
   - Shorter prompts = lower cost
   - Remove redundant instructions
   - Use efficient formatting

4. BATCHING
   - Batch embedding requests
   - Batch similar LLM requests (where possible)

5. CACHING (covered Day 3-4)
   - Every cache hit = saved API call
```

**Rate Limiting Strategies:**

```
1. PER-USER LIMITS
   - 100 requests/hour per user
   - 10,000 tokens/hour per user
   - $1/day per user

2. GLOBAL LIMITS
   - 1000 requests/minute total
   - $100/hour max spend
   - Circuit breaker at $X

3. TIERED LIMITS
   - Free tier: 10 requests/day
   - Basic tier: 100 requests/day
   - Pro tier: 1000 requests/day

4. ADAPTIVE LIMITS
   - Normal: 100 req/min
   - High load: 50 req/min
   - Critical: 10 req/min

5. COST-BASED LIMITS
   - Per-request cost estimate before execution
   - Reject if would exceed budget
   - Warn if approaching limit
```

**Rate Limiting Implementation:**

```python
# Token bucket algorithm (common for rate limiting)
class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        """
        capacity: Max tokens in bucket
        refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Add tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_refill = now
```

**Practical Skills:**

- Implement model routing based on task complexity
- Set up per-user rate limiting
- Implement cost estimation and budgets
- Design graceful degradation when limits hit

### Resources

**Primary:**

- OpenAI Rate Limits: https://platform.openai.com/docs/guides/rate-limits
- Token Bucket Algorithm: https://en.wikipedia.org/wiki/Token_bucket

**Secondary:**

- Search: "LLM cost optimization strategies"
- Search: "API rate limiting best practices"

### Day 5 Tasks (2 hours)

**Hour 1 — Learn + Design:**

1. Review your Research Assistant's cost breakdown (from monitoring):
    - Which models are you using?
    - Which operations cost most?
    - Where can you use cheaper models?
2. Design model routing:
    
    ```python
    # Task → Model mappingMODEL_ROUTING = {    # Cheap tasks → cheap model    "query_classification": "gpt-4o-mini",    "query_reformulation": "gpt-4o-mini",    "answer_extraction": "gpt-4o-mini",        # Complex tasks → capable model (but consider if needed)    "complex_synthesis": "gpt-4o",    "multi_step_reasoning": "gpt-4o",        # Embeddings → embedding model    "embedding": "text-embedding-3-small",}def select_model(task: str, complexity: str = "normal") -> str:    """Select model based on task and complexity."""    base_model = MODEL_ROUTING.get(task, "gpt-4o-mini")        # Upgrade for complex requests    if complexity == "high" and base_model == "gpt-4o-mini":        return "gpt-4o"        return base_model
    ```
    
3. Design your rate limits:
    - What's your budget? Daily/monthly?
    - How many users expected?
    - What limits per user are reasonable?

**Hour 2 — Implement Cost Estimation:**

1. Pre-request cost estimation:
    
    ```python
    class CostEstimator:    # Prices per 1M tokens (verify current rates!)    PRICES = {        "gpt-4o-mini": {"input": 0.15, "output": 0.60},        "gpt-4o": {"input": 2.50, "output": 10.00},        "text-embedding-3-small": {"input": 0.02, "output": 0.0},    }        def estimate_request_cost(        self,        model: str,        estimated_input_tokens: int,        estimated_output_tokens: int    ) -> float:        """Estimate cost in USD before making request."""        if model not in self.PRICES:            return 0.0                prices = self.PRICES[model]        input_cost = (estimated_input_tokens / 1_000_000) * prices["input"]        output_cost = (estimated_output_tokens / 1_000_000) * prices["output"]                return input_cost + output_cost        def estimate_query_cost(self, query: str, config: dict) -> float:        """Estimate total cost for a Research Assistant query."""        costs = 0.0                # Embedding cost (query + chunks)        costs += self.estimate_request_cost(            "text-embedding-3-small",            estimated_input_tokens=len(query.split()) * 2,  # Rough            estimated_output_tokens=0        )                # Classification (if doing it)        costs += self.estimate_request_cost(            "gpt-4o-mini",            estimated_input_tokens=100,            estimated_output_tokens=20        )                # Generation        costs += self.estimate_request_cost(            config.get("model", "gpt-4o-mini"),            estimated_input_tokens=2000,  # Context + query            estimated_output_tokens=500   # Estimated response        )                return costs
    ```
    
2. Add cost pre-check to your Research Assistant:
    
    ```python
    def research(self, query: str, user_id: str) -> dict:    # Estimate cost    estimated_cost = self.cost_estimator.estimate_query_cost(query, self.config)        # Check user's remaining budget    user_budget = self.get_user_remaining_budget(user_id)    if estimated_cost > user_budget:        raise BudgetExceededError(            f"Estimated cost ${estimated_cost:.4f} exceeds remaining budget ${user_budget:.4f}"        )        # Proceed with query...
    ```
    
3. Test: Set a low budget, verify it rejects expensive queries

### Day 6 Tasks (2 hours)

**Hour 1 — Implement Rate Limiting:**

1. Build rate limiter:
    
    ```python
    from collections import defaultdictimport timeclass RateLimiter:    def __init__(        self,        requests_per_minute: int = 60,        tokens_per_minute: int = 100000,        cost_per_day: float = 10.0    ):        self.rpm_limit = requests_per_minute        self.tpm_limit = tokens_per_minute        self.daily_cost_limit = cost_per_day                # Per-user tracking        self.user_requests = defaultdict(list)  # user_id -> [timestamps]        self.user_tokens = defaultdict(list)    # user_id -> [(timestamp, tokens)]        self.user_daily_cost = defaultdict(float)        self.daily_reset = self._get_day_start()        def check_rate_limit(        self,         user_id: str,         estimated_tokens: int = 0,        estimated_cost: float = 0.0    ) -> dict:        """        Check if request is allowed.                Returns:            {                "allowed": True/False,                "reason": "rate_limit|token_limit|cost_limit|None",                "retry_after_seconds": 30,                "limits": {                    "requests_remaining": 45,                    "tokens_remaining": 50000,                    "budget_remaining": 5.50                }            }        """        self._cleanup_old_entries(user_id)        self._reset_daily_if_needed()                # Check request rate        recent_requests = len(self.user_requests[user_id])        if recent_requests >= self.rpm_limit:            return {                "allowed": False,                "reason": "rate_limit",                "retry_after_seconds": 60,                "limits": self._get_limits(user_id)            }                # Check token rate        recent_tokens = sum(t for _, t in self.user_tokens[user_id])        if recent_tokens + estimated_tokens > self.tpm_limit:            return {                "allowed": False,                "reason": "token_limit",                "retry_after_seconds": 60,                "limits": self._get_limits(user_id)            }                # Check daily cost        if self.user_daily_cost[user_id] + estimated_cost > self.daily_cost_limit:            return {                "allowed": False,                "reason": "cost_limit",                "retry_after_seconds": self._seconds_until_reset(),                "limits": self._get_limits(user_id)            }                return {"allowed": True, "reason": None, "limits": self._get_limits(user_id)}        def record_usage(        self,         user_id: str,         tokens: int,         cost: float    ) -> None:        """Record actual usage after request completes."""        now = time.time()        self.user_requests[user_id].append(now)        self.user_tokens[user_id].append((now, tokens))        self.user_daily_cost[user_id] += cost
    ```
    
2. Integrate into Research Assistant
3. Test: Exceed rate limit, verify rejection with helpful message

**Hour 2 — Mini Challenge: Complete Cost Control System**

Build a `CostController` that combines everything:

```python
class CostController:
    def __init__(
        self,
        # Rate limits
        requests_per_minute: int = 60,
        tokens_per_minute: int = 100000,
        
        # Cost limits
        cost_per_request_max: float = 0.10,
        cost_per_user_daily: float = 5.00,
        cost_global_daily: float = 100.00,
        
        # Model routing
        model_routing: dict = None,
        
        # Degradation
        enable_graceful_degradation: bool = True
    ):
        """
        Complete cost control for production LLM systems.
        """
        pass
    
    def pre_request_check(
        self,
        user_id: str,
        query: str,
        config: dict
    ) -> dict:
        """
        Check before executing request.
        
        Returns:
            {
                "allowed": True/False,
                "reason": None or "rate_limit|budget|global_limit",
                "estimated_cost": 0.0032,
                "selected_model": "gpt-4o-mini",  # May downgrade for cost
                "warnings": ["Approaching daily limit (80%)"],
                "retry_after": None or seconds
            }
        """
        pass
    
    def select_model(
        self,
        task: str,
        user_id: str,
        prefer_quality: bool = False
    ) -> str:
        """
        Select model considering cost constraints.
        
        May downgrade model if:
        - User approaching budget
        - Global costs high
        - Graceful degradation enabled
        """
        pass
    
    def record_request(
        self,
        user_id: str,
        tokens_used: int,
        actual_cost: float,
        model: str
    ) -> None:
        """Record completed request."""
        pass
    
    def get_user_status(self, user_id: str) -> dict:
        """
        Get user's current limit status.
        
        Returns:
            {
                "requests_remaining": 45,
                "tokens_remaining": 80000,
                "budget_remaining": 3.50,
                "budget_used_today": 1.50,
                "reset_in_seconds": 3600
            }
        """
        pass
    
    def get_global_status(self) -> dict:
        """Get system-wide cost status."""
        pass
    
    def trigger_degradation(self, level: str) -> None:
        """
        Manually trigger graceful degradation.
        
        Levels:
        - "normal": Full functionality
        - "reduced": Cheaper models only
        - "minimal": Essential operations only
        - "emergency": Reject all non-critical
        """
        pass
```

**Success Criteria:**

- [ ] Pre-request cost estimation working
- [ ] Per-user rate limiting (requests/minute)
- [ ] Per-user token limiting (tokens/minute)
- [ ] Per-user daily cost budget
- [ ] Global daily cost limit
- [ ] Model downgrade when approaching limits
- [ ] Graceful degradation modes
- [ ] Clear error messages when limits hit
- [ ] User can query their remaining limits
- [ ] Tested: Simulate budget exhaustion, verify graceful handling

### 5 Things to Ponder

1. User hits their rate limit. They get an error. They're frustrated. How do you communicate limits proactively? Show remaining quota? Warn at 80%? What's the UX for rate limiting?
    
2. You set $5/user/day limit. Power user says "I'll pay more." Do you offer tiers? How do you handle users who want to exceed limits? Does your system support dynamic limits?
    
3. Global budget is $100/day. At 3 PM, you've spent $80. Do you: (a) continue normally and risk overage, (b) reduce all limits proportionally, (c) switch to cheaper models, (d) queue non-urgent requests? What's your strategy?
    
4. Cost estimation is based on _estimated_ output tokens. But you don't know output length until generation completes. A 500-token estimate could become 2000 tokens. How do you handle estimation errors? Set max_tokens strictly?
    
5. You downgrade from GPT-4o to GPT-4o-mini to save costs. Quality drops. Users notice. They complain. Was the cost saving worth the quality loss? How do you balance cost vs. quality? Who decides?
    

---

## Day 7: Mini Build — Research Assistant with LLMOps

### What to Build

Add the complete LLMOps layer to your Week 7 Research Assistant:

- Production logging and monitoring
- Multi-level caching
- Cost controls and rate limiting
- Graceful degradation

This transforms your prototype into something production-viable.

### Specifications

**Architecture with LLMOps:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Request                                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LLMOPS LAYER                                 │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │    Rate      │  │    Cost      │  │   Logging    │               │
│  │   Limiter    │──│  Controller  │──│   Metrics    │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│         │                  │                  │                      │
│         └──────────────────┼──────────────────┘                      │
│                            │                                         │
│                   ┌────────┴────────┐                                │
│                   │  Cache Layer    │                                │
│                   │  (Exact+Semantic)│                                │
│                   └────────┬────────┘                                │
│                            │                                         │
│              Cache Hit ────┤──── Cache Miss                          │
│                   │        │        │                                │
│                   ▼        │        ▼                                │
│            Return Cached   │   Continue to                           │
│                            │   Research Assistant                    │
└────────────────────────────┼────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RESEARCH ASSISTANT (Week 7)                       │
│                                                                      │
│  Orchestrator → Internal Researcher → External Researcher → Writer  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Core Interface:**

```python
from research_assistant import ProductionResearchAssistant

# Initialize with LLMOps config
assistant = ProductionResearchAssistant(
    # Core config
    rag_config="config/rag.yaml",
    llm_model="gpt-4o-mini",
    
    # Caching
    cache_config={
        "enable_exact": True,
        "enable_semantic": True,
        "semantic_threshold": 0.92,
        "ttl_seconds": 3600
    },
    
    # Rate limiting
    rate_limit_config={
        "requests_per_minute": 60,
        "tokens_per_minute": 100000,
        "cost_per_user_daily": 5.00
    },
    
    # Cost control
    cost_config={
        "global_daily_limit": 100.00,
        "enable_model_downgrade": True,
        "degradation_threshold": 0.8  # Degrade at 80% budget
    },
    
    # Monitoring
    monitoring_config={
        "enable_metrics": True,
        "metrics_port": 8000,
        "enable_tracing": True,
        "langsmith_project": "research-assistant-prod"
    }
)

# Query with full observability
result = assistant.research(
    query="What's our refund policy?",
    user_id="user_123"
)

print(result.answer)
print(result.sources)
print(result.metadata)
# {
#     "cache_status": "miss",  # or "hit_exact" or "hit_semantic"
#     "latency_ms": 650,
#     "tokens_used": 2500,
#     "cost_usd": 0.0032,
#     "model_used": "gpt-4o-mini",  # May differ from requested if downgraded
#     "trace_url": "https://smith.langchain.com/..."
# }

# Check user limits
status = assistant.get_user_status("user_123")
# {
#     "requests_remaining": 45,
#     "budget_remaining": 4.50,
#     "cache_hit_rate": 0.35,
#     "avg_latency_ms": 580
# }

# Admin dashboard data
dashboard = assistant.get_dashboard()
# {
#     "total_requests_today": 1500,
#     "cache_hit_rate": 0.42,
#     "total_cost_today": 45.30,
#     "budget_remaining": 54.70,
#     "degradation_status": "normal",
#     "error_rate": 0.02,
#     "p95_latency": 1200
# }

# Handle rate limit gracefully
try:
    result = assistant.research(query="...", user_id="heavy_user")
except RateLimitError as e:
    print(f"Rate limited: {e.reason}")
    print(f"Retry after: {e.retry_after_seconds}s")
    print(f"Remaining today: {e.limits}")
```

### Success Criteria

**Monitoring:**

- [ ] Structured JSON logging for all requests
- [ ] Prometheus metrics exposed
- [ ] Latency, tokens, cost tracked per request
- [ ] Error rate calculable
- [ ] Dashboard data endpoint working

**Caching:**

- [ ] Exact match cache working
- [ ] Semantic cache working
- [ ] Cache hit rate tracked
- [ ] Cost savings from cache calculated

**Cost Control:**

- [ ] Pre-request cost estimation
- [ ] Per-user rate limiting
- [ ] Per-user daily budget
- [ ] Global daily budget
- [ ] Model downgrade when approaching limits
- [ ] Clear errors when limits exceeded

**Graceful Degradation:**

- [ ] System continues operating under load
- [ ] Quality degrades gracefully (cheaper models, not failures)
- [ ] Users informed of degraded status

**Integration:**

- [ ] All components work together
- [ ] Metrics reflect actual behavior
- [ ] Tested: 50 queries including repeats, limit tests, error cases
- [ ] Can demonstrate cost savings vs. no-ops version

### Things to Ponder (Post-Build)

1. You've added caching, rate limiting, cost controls. The system is now more complex. More things can break. How do you test this? How do you verify the ops layer itself isn't causing issues?
    
2. Your cache hit rate is 40%. Your cache saves 40% of API costs. But the cache itself has costs (memory, compute for semantic matching). At what hit rate does caching become net-negative? How do you calculate ROI?
    
3. User complains: "The system was faster yesterday." You check metrics: latency is the same. But yesterday they had 50% cache hits. Today they're asking new questions — all misses. How do you explain performance variance to users?
    
4. Your global budget is $100/day. You've allocated $5/user/day for 20 users. But only 10 users are active. The other 10's budget is wasted. How do you handle budget allocation with variable usage patterns?
    
5. Looking at Week 9: You have monitoring, caching, cost controls. What's still missing for "production hardened"? What breaks under adversarial usage? What happens when the LLM API goes down? What security holes exist?
    

---

# WEEK 8 CHECKLIST

## Completion Criteria

- [ ] **Logging:** Structured JSON logs capturing all request details
- [ ] **Metrics:** Prometheus metrics for latency, tokens, costs, errors
- [ ] **Dashboards:** Can view aggregate system health
- [ ] **Caching:** Multi-level caching reducing costs and latency
- [ ] **Cost Estimation:** Pre-request cost checking
- [ ] **Rate Limiting:** Per-user and global limits enforced
- [ ] **Cost Budgets:** Daily budgets preventing runaway costs
- [ ] **Graceful Degradation:** System degrades gracefully under cost pressure
- [ ] **Mini Build:** Research Assistant with complete LLMOps layer

## What's Next

**Week 9: Production Hardening**

- Hallucination detection and mitigation
- Error handling and fallbacks
- Security (prompt injection, data leakage)
- Load testing and reliability
- Final Build: Production-Ready Research Assistant

---

# NOTES SECTION

### Days 1-2 Notes (Production Logging & Monitoring)

### Days 3-4 Notes (Caching Strategies)

### Days 5-6 Notes (Cost Optimization & Rate Limiting)

### Day 7 Notes (Research Assistant with LLMOps Mini Build)