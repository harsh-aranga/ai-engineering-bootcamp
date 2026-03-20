# Note 5: Capacity Planning and Scaling Patterns

## The Capacity Planning Problem

Load testing tells you what your system _can_ handle. Capacity planning answers a different question: what _should_ your system handle, and how do you ensure it can?

```
┌─────────────────────────────────────────────────────────────────┐
│              LOAD TESTING vs CAPACITY PLANNING                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   LOAD TESTING (Note 4)                                         │
│   "What are my system's limits?"                                │
│   • Run tests to find breaking points                           │
│   • Measure latency, throughput, error rates                    │
│   • Identify bottlenecks                                        │
│                                                                 │
│   CAPACITY PLANNING (This Note)                                 │
│   "How much capacity do I need, and how do I get it?"           │
│   • Model expected traffic                                      │
│   • Ensure capacity > expected load + buffer                    │
│   • Plan for growth and spikes                                  │
│   • Balance cost vs headroom                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

For LLM applications, capacity planning has a unique constraint: **the LLM API is often the bottleneck, and you can't scale it yourself**.

---

## Understanding Your Bottlenecks

An LLM application has multiple components, each with its own capacity limits.

```
┌─────────────────────────────────────────────────────────────────┐
│                    REQUEST FLOW & BOTTLENECKS                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   User Request                                                  │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────────────────────────────────────┐                   │
│   │ YOUR SERVER                             │                   │
│   │ Bottleneck: CPU, memory, connections    │                   │
│   │ You control: Yes                        │                   │
│   │ Can scale: Yes (horizontal/vertical)    │                   │
│   └─────────────────────────────────────────┘                   │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────────────────────────────────────┐                   │
│   │ EMBEDDING API                           │                   │
│   │ Bottleneck: Rate limits (req/min)       │                   │
│   │ You control: No                         │                   │
│   │ Can scale: Multiple keys, caching       │                   │
│   └─────────────────────────────────────────┘                   │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────────────────────────────────────┐                   │
│   │ VECTOR DATABASE                         │                   │
│   │ Bottleneck: Query throughput, latency   │                   │
│   │ You control: Partially (managed vs self)│                   │
│   │ Can scale: Yes (index sharding, replicas)│                  │
│   └─────────────────────────────────────────┘                   │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────────────────────────────────────┐                   │
│   │ LLM API                                 │ ← Often the       │
│   │ Bottleneck: Rate limits, latency        │   bottleneck      │
│   │ You control: No                         │                   │
│   │ Can scale: Multiple keys, providers     │                   │
│   └─────────────────────────────────────────┘                   │
│       │                                                         │
│       ▼                                                         │
│   Response to User                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Bottleneck Characteristics

|Component|Typical Bottleneck|You Control?|Scaling Options|
|---|---|---|---|
|Your server|CPU, memory, connections|Yes|Vertical, horizontal|
|Embedding API|Rate limits (3k-10k req/min)|No|Caching, multiple keys|
|Vector DB|Query throughput|Partial|Indexing, sharding, replicas|
|LLM API|Rate limits, latency|No|Caching, multiple keys/providers|

---

## Finding the Bottleneck

Before you can scale, you need to know what to scale.

### Step 1: Profile End-to-End

Instrument your code to measure time spent in each component.

```python
import time
from dataclasses import dataclass, field
from contextlib import contextmanager
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RequestProfile:
    """Timing breakdown for a single request."""
    request_id: str
    start_time: float = field(default_factory=time.perf_counter)
    
    # Component timings (milliseconds)
    input_validation_ms: float = 0
    embedding_ms: float = 0
    vector_search_ms: float = 0
    prompt_construction_ms: float = 0
    llm_call_ms: float = 0
    output_processing_ms: float = 0
    total_ms: float = 0
    
    _current_component: Optional[str] = None
    _component_start: float = 0
    
    @contextmanager
    def measure(self, component: str):
        """Context manager to measure component timing."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            setattr(self, f"{component}_ms", elapsed_ms)
    
    def finish(self) -> None:
        """Mark request complete and calculate total."""
        self.total_ms = (time.perf_counter() - self.start_time) * 1000
    
    def breakdown(self) -> dict:
        """Return timing breakdown with percentages."""
        components = {
            "input_validation": self.input_validation_ms,
            "embedding": self.embedding_ms,
            "vector_search": self.vector_search_ms,
            "prompt_construction": self.prompt_construction_ms,
            "llm_call": self.llm_call_ms,
            "output_processing": self.output_processing_ms,
        }
        
        accounted = sum(components.values())
        components["other"] = max(0, self.total_ms - accounted)
        
        return {
            "total_ms": self.total_ms,
            "breakdown_ms": components,
            "breakdown_pct": {
                k: (v / self.total_ms * 100) if self.total_ms > 0 else 0
                for k, v in components.items()
            },
        }


# Usage in your application
async def research_with_profiling(query: str) -> dict:
    profile = RequestProfile(request_id="req_123")
    
    with profile.measure("input_validation"):
        validated = validate_input(query)
    
    with profile.measure("embedding"):
        embedding = await generate_embedding(validated)
    
    with profile.measure("vector_search"):
        chunks = await search_vectors(embedding)
    
    with profile.measure("prompt_construction"):
        prompt = build_prompt(query, chunks)
    
    with profile.measure("llm_call"):
        response = await call_llm(prompt)
    
    with profile.measure("output_processing"):
        result = process_output(response)
    
    profile.finish()
    
    # Log the breakdown
    breakdown = profile.breakdown()
    logger.info(f"Request timing: {breakdown}")
    
    return {"result": result, "profile": breakdown}
```

### Step 2: Aggregate and Identify

Collect profiling data across many requests to see patterns.

```python
from collections import defaultdict
from statistics import mean, median
from typing import Optional


class BottleneckAnalyzer:
    """
    Aggregate request profiles to identify bottlenecks.
    """
    
    def __init__(self):
        self.profiles: list[dict] = []
    
    def add_profile(self, breakdown: dict) -> None:
        """Add a request profile."""
        self.profiles.append(breakdown)
    
    def analyze(self) -> dict:
        """
        Analyze collected profiles to identify bottlenecks.
        
        Returns:
            {
                "sample_size": 150,
                "average_total_ms": 2500,
                "component_analysis": {
                    "llm_call": {
                        "avg_ms": 2100,
                        "avg_pct": 84.0,
                        "is_bottleneck": True
                    },
                    ...
                },
                "primary_bottleneck": "llm_call",
                "recommendations": [...]
            }
        """
        if not self.profiles:
            return {"error": "No profiles collected"}
        
        components = ["input_validation", "embedding", "vector_search", 
                      "prompt_construction", "llm_call", "output_processing", "other"]
        
        component_analysis = {}
        for component in components:
            times = [p["breakdown_ms"].get(component, 0) for p in self.profiles]
            pcts = [p["breakdown_pct"].get(component, 0) for p in self.profiles]
            
            avg_pct = mean(pcts)
            component_analysis[component] = {
                "avg_ms": mean(times),
                "median_ms": median(times),
                "avg_pct": avg_pct,
                "is_bottleneck": avg_pct > 50,  # >50% of time = bottleneck
            }
        
        # Find primary bottleneck
        primary = max(component_analysis.items(), key=lambda x: x[1]["avg_pct"])
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            primary[0], 
            component_analysis
        )
        
        return {
            "sample_size": len(self.profiles),
            "average_total_ms": mean(p["total_ms"] for p in self.profiles),
            "component_analysis": component_analysis,
            "primary_bottleneck": primary[0],
            "recommendations": recommendations,
        }
    
    def _generate_recommendations(
        self, 
        bottleneck: str, 
        analysis: dict
    ) -> list[str]:
        """Generate scaling recommendations based on bottleneck."""
        recommendations = {
            "llm_call": [
                "LLM API is the bottleneck (expected for most LLM apps)",
                "Consider: response caching for common queries",
                "Consider: shorter prompts to reduce latency",
                "Consider: multiple API keys to increase rate limits",
                "Consider: smaller/faster models for simple queries",
            ],
            "embedding": [
                "Embedding generation is a bottleneck",
                "Consider: caching embeddings for repeated queries",
                "Consider: batching embedding requests",
                "Consider: local embedding model (if latency-sensitive)",
            ],
            "vector_search": [
                "Vector search is a bottleneck",
                "Consider: optimizing vector index (HNSW parameters)",
                "Consider: reducing search scope (filters, smaller k)",
                "Consider: vector DB with better query performance",
                "Consider: adding replicas for read scaling",
            ],
            "input_validation": [
                "Input validation is taking significant time",
                "Consider: simplifying validation logic",
                "Consider: async validation where possible",
            ],
            "output_processing": [
                "Output processing is taking significant time",
                "Consider: optimizing PII detection/filtering",
                "Consider: streaming responses to reduce perceived latency",
            ],
        }
        
        return recommendations.get(bottleneck, ["No specific recommendations"])
```

### Step 3: Load Test Each Component

Test components in isolation to find their individual limits.

```python
async def test_component_limits():
    """Test each component's capacity in isolation."""
    
    results = {}
    
    # Test embedding API limits
    print("Testing embedding API...")
    embedding_results = await load_test_embedding(
        num_requests=100,
        concurrency=20,
    )
    results["embedding"] = {
        "max_rps": embedding_results.requests_per_second,
        "p99_latency_ms": embedding_results.p99_ms,
        "error_rate": embedding_results.error_rate,
    }
    
    # Test vector DB limits
    print("Testing vector DB...")
    vector_results = await load_test_vector_db(
        num_requests=500,
        concurrency=50,
    )
    results["vector_db"] = {
        "max_rps": vector_results.requests_per_second,
        "p99_latency_ms": vector_results.p99_ms,
        "error_rate": vector_results.error_rate,
    }
    
    # Test LLM API limits (careful with cost!)
    print("Testing LLM API (limited)...")
    llm_results = await load_test_llm(
        num_requests=50,  # Keep small due to cost
        concurrency=10,
    )
    results["llm_api"] = {
        "max_rps": llm_results.requests_per_second,
        "p99_latency_ms": llm_results.p99_ms,
        "error_rate": llm_results.error_rate,
    }
    
    # Find the limiting component
    min_rps_component = min(results.items(), key=lambda x: x[1]["max_rps"])
    
    print(f"\nBottleneck: {min_rps_component[0]}")
    print(f"System limited to ~{min_rps_component[1]['max_rps']:.1f} RPS")
    
    return results
```

---

## LLM API as the Bottleneck

In most LLM applications, the LLM API is the bottleneck. This is a different kind of problem because **you can't scale it directly**.

### Provider Rate Limits

|Provider|Tier|Requests/min|Tokens/min|
|---|---|---|---|
|OpenAI|Free|3|40,000|
|OpenAI|Tier 1|500|200,000|
|OpenAI|Tier 5|10,000|30,000,000|
|Anthropic|Build|50|40,000|
|Anthropic|Scale|4,000|400,000|

_(These limits change frequently — always check current documentation)_

### Solutions When LLM API Is the Bottleneck

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCALING PAST LLM API LIMITS                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. CACHING                                                    │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ • Cache responses for identical/similar queries         │   │
│   │ • Semantic caching: similar meaning → same response     │   │
│   │ • Reduces LLM calls, not just latency                   │   │
│   │ • Savings: 20-60% reduction in LLM calls (typical)      │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   2. MULTIPLE API KEYS                                          │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ • Rate limits are per-key                               │   │
│   │ • Round-robin across multiple keys                      │   │
│   │ • Each key = another quota bucket                       │   │
│   │ • Caution: may violate ToS if used to circumvent limits │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   3. MULTIPLE PROVIDERS                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ • Route to OpenAI, Anthropic, or others based on load   │   │
│   │ • Each provider = separate rate limit pool              │   │
│   │ • Requires handling model differences                   │   │
│   │ • Good for redundancy too                               │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   4. TIERED MODELS                                              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ • Route simple queries to faster/cheaper models         │   │
│   │ • Reserve expensive models for complex queries          │   │
│   │ • gpt-4o-mini for FAQ, gpt-4o for analysis             │   │
│   │ • Reduces load on expensive model quota                 │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   5. REQUEST QUEUING                                            │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ • Smooth out request spikes                             │   │
│   │ • Process at sustainable rate                           │   │
│   │ • Accept immediately, respond asynchronously            │   │
│   │ • Better than rejecting during spikes                   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Scaling Patterns

### Pattern 1: Vertical Scaling

Add more resources to a single machine.

```
Before: 2 CPU, 4GB RAM
After:  8 CPU, 32GB RAM
```

**When it helps:**

- CPU-bound processing (rare for LLM apps)
- Memory-bound operations (large context, many concurrent conversations)
- Single-threaded bottlenecks

**When it doesn't help:**

- I/O-bound operations (waiting for LLM API)
- External rate limits

**For LLM apps:** Usually limited benefit because you're waiting on external APIs, not computing locally.

### Pattern 2: Horizontal Scaling

Add more instances behind a load balancer.

```
┌─────────────────────────────────────────────────────────────────┐
│                    HORIZONTAL SCALING                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                      Load Balancer                              │
│                           │                                     │
│            ┌──────────────┼──────────────┐                      │
│            │              │              │                      │
│            ▼              ▼              ▼                      │
│       ┌────────┐     ┌────────┐     ┌────────┐                  │
│       │ App 1  │     │ App 2  │     │ App 3  │                  │
│       └────────┘     └────────┘     └────────┘                  │
│            │              │              │                      │
│            └──────────────┼──────────────┘                      │
│                           │                                     │
│                      ┌────────┐                                 │
│                      │LLM API │ ← Still the same                │
│                      └────────┘   rate limits                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**When it helps:**

- Handling more concurrent connections
- Isolating failures (one instance crashes, others continue)
- Deploying updates (rolling deployment)

**When it doesn't help:**

- If the bottleneck is a shared resource (LLM API, single DB)

**For LLM apps:** Helps with connection handling, but doesn't increase LLM API capacity unless combined with multiple API keys.

### Pattern 3: Caching

Reduce load on expensive components by reusing results.

```python
import hashlib
import json
from typing import Optional
from datetime import datetime, timedelta


class LLMResponseCache:
    """
    Cache LLM responses to reduce API calls.
    
    Strategies:
    1. Exact match: identical query → cached response
    2. Semantic: similar queries → same response (requires embedding similarity)
    """
    
    def __init__(
        self,
        backend,  # Redis, in-memory, etc.
        ttl_seconds: int = 3600,
        max_entries: int = 10000,
    ):
        self.backend = backend
        self.ttl = timedelta(seconds=ttl_seconds)
        self.max_entries = max_entries
        
        # Stats
        self.hits = 0
        self.misses = 0
    
    def _cache_key(self, query: str, context_hash: str) -> str:
        """Generate cache key from query and context."""
        combined = f"{query}:{context_hash}"
        return f"llm_cache:{hashlib.sha256(combined.encode()).hexdigest()}"
    
    def _context_hash(self, context: list[str]) -> str:
        """Hash the retrieved context to include in cache key."""
        # Context affects response, so must be part of key
        return hashlib.sha256(
            json.dumps(sorted(context)).encode()
        ).hexdigest()[:16]
    
    async def get(
        self, 
        query: str, 
        context: list[str]
    ) -> Optional[str]:
        """Get cached response if available."""
        key = self._cache_key(query, self._context_hash(context))
        
        cached = await self.backend.get(key)
        if cached:
            self.hits += 1
            return json.loads(cached)["response"]
        
        self.misses += 1
        return None
    
    async def set(
        self, 
        query: str, 
        context: list[str], 
        response: str
    ) -> None:
        """Cache a response."""
        key = self._cache_key(query, self._context_hash(context))
        
        value = json.dumps({
            "response": response,
            "cached_at": datetime.now().isoformat(),
            "query": query,
        })
        
        await self.backend.set(key, value, ex=int(self.ttl.total_seconds()))
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0


# Usage
async def research_with_cache(query: str, context: list[str]) -> str:
    # Check cache first
    cached = await cache.get(query, context)
    if cached:
        return cached
    
    # Cache miss — call LLM
    response = await call_llm(query, context)
    
    # Store in cache
    await cache.set(query, context, response)
    
    return response
```

**Cache effectiveness depends on:**

- Query repetition rate (FAQ systems cache well)
- Context stability (same docs = more cache hits)
- TTL appropriateness (stale data tolerance)

**Typical cache hit rates:**

- FAQ/support bots: 40-60%
- Research assistants: 10-20%
- Creative applications: <5%

### Pattern 4: Queue-Based Architecture

Decouple request acceptance from processing.

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUEUE-BASED ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   SYNCHRONOUS (Without Queue)                                   │
│                                                                 │
│   User ──Request──▶ Server ──LLM call──▶ LLM API               │
│         ◀─Response─         ◀──────────                        │
│                                                                 │
│   Problem: User waits entire duration. Spikes cause failures.   │
│                                                                 │
│   ─────────────────────────────────────────────────────────────│
│                                                                 │
│   ASYNCHRONOUS (With Queue)                                     │
│                                                                 │
│   User ──Request──▶ API Server ──Enqueue──▶ Queue              │
│         ◀─Job ID──                            │                 │
│                                               │                 │
│                                    Worker ◀───┘                 │
│                                       │                         │
│                                       ▼                         │
│                                    LLM API                      │
│                                       │                         │
│                                       ▼                         │
│   User ──Poll/WS──▶ API Server ◀──Result──                     │
│         ◀─Result──                                              │
│                                                                 │
│   Benefits:                                                     │
│   • Accept requests instantly (never reject due to load)        │
│   • Process at sustainable rate (respect rate limits)           │
│   • Handle spikes gracefully (queue absorbs burst)              │
│   • Scale workers independently                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

```python
# Simplified queue-based architecture example
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import uuid


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    query: str
    user_id: str
    status: JobStatus = JobStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = 0
    completed_at: Optional[float] = None


class SimpleJobQueue:
    """
    Simple in-memory job queue for demonstration.
    
    Production: Use Redis Queue (RQ), Celery, or cloud queues (SQS, Cloud Tasks)
    """
    
    def __init__(self, max_queue_size: int = 1000):
        self.queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=max_queue_size)
        self.jobs: dict[str, Job] = {}
    
    async def enqueue(self, query: str, user_id: str) -> str:
        """
        Add job to queue. Returns immediately with job ID.
        """
        job = Job(
            id=str(uuid.uuid4()),
            query=query,
            user_id=user_id,
            created_at=asyncio.get_event_loop().time(),
        )
        
        self.jobs[job.id] = job
        await self.queue.put(job)
        
        return job.id
    
    async def dequeue(self) -> Job:
        """Get next job from queue (blocks if empty)."""
        return await self.queue.get()
    
    def get_status(self, job_id: str) -> Optional[Job]:
        """Get job status."""
        return self.jobs.get(job_id)
    
    def update_job(
        self, 
        job_id: str, 
        status: JobStatus, 
        result: str = None,
        error: str = None,
    ) -> None:
        """Update job status."""
        if job_id in self.jobs:
            self.jobs[job_id].status = status
            self.jobs[job_id].result = result
            self.jobs[job_id].error = error
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                self.jobs[job_id].completed_at = asyncio.get_event_loop().time()
    
    @property
    def queue_depth(self) -> int:
        """Current number of pending jobs."""
        return self.queue.qsize()


async def worker(queue: SimpleJobQueue, worker_id: int):
    """
    Worker that processes jobs from the queue.
    
    Run multiple workers to increase throughput (up to rate limits).
    """
    while True:
        job = await queue.dequeue()
        
        queue.update_job(job.id, JobStatus.PROCESSING)
        
        try:
            # Process the job (call LLM, etc.)
            result = await process_research_query(job.query)
            queue.update_job(job.id, JobStatus.COMPLETED, result=result)
            
        except Exception as e:
            queue.update_job(job.id, JobStatus.FAILED, error=str(e))


# API endpoints
async def submit_query(query: str, user_id: str) -> dict:
    """Submit query and return immediately with job ID."""
    job_id = await job_queue.enqueue(query, user_id)
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Query submitted. Poll /status/{job_id} for results.",
    }


async def get_query_status(job_id: str) -> dict:
    """Check job status."""
    job = job_queue.get_status(job_id)
    if not job:
        return {"error": "Job not found"}
    
    return {
        "job_id": job.id,
        "status": job.status.value,
        "result": job.result if job.status == JobStatus.COMPLETED else None,
        "error": job.error if job.status == JobStatus.FAILED else None,
    }
```

---

## Autoscaling Considerations

Traditional autoscaling triggers on CPU utilization. **This doesn't work well for LLM applications.**

### Why CPU-Based Autoscaling Fails

```
┌─────────────────────────────────────────────────────────────────┐
│                    CPU SCALING PROBLEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Traditional Web App:                                          │
│   • Request comes in                                            │
│   • CPU does work (database queries, computation)               │
│   • CPU usage correlates with load                              │
│   • Scale on CPU% works                                         │
│                                                                 │
│   LLM Application:                                              │
│   • Request comes in                                            │
│   • CPU sends request to LLM API                                │
│   • CPU waits (doing nothing) for 2-3 seconds                   │
│   • CPU usage is LOW even at high load                          │
│   • Scale on CPU% doesn't trigger                               │
│                                                                 │
│   Result: System overwhelmed while CPU sits at 10%              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Better Autoscaling Metrics for LLM Apps

|Metric|Why It Works|Threshold Example|
|---|---|---|
|**Queue depth**|Directly measures pending work|Scale up when > 100 jobs|
|**Request latency**|User experience indicator|Scale up when p95 > 5s|
|**Concurrent connections**|Measures active load|Scale up when > 80% of limit|
|**Rate limit headroom**|Prevents hitting limits|Scale down when < 20% used|

```python
# Example: Queue-depth based scaling decision
def should_scale(
    current_instances: int,
    queue_depth: int,
    avg_processing_time_seconds: float,
    target_wait_time_seconds: float = 30,
) -> tuple[str, int]:
    """
    Determine if we need to scale up or down.
    
    Logic:
    - Each worker processes 1 job per avg_processing_time
    - Queue depth / workers = estimated wait time
    - Scale to keep wait time under target
    
    Returns:
        ("scale_up" | "scale_down" | "no_change", target_instances)
    """
    if current_instances == 0:
        return ("scale_up", 1)
    
    # Estimated wait time for a new job
    jobs_per_worker_per_target = target_wait_time_seconds / avg_processing_time_seconds
    needed_workers = queue_depth / jobs_per_worker_per_target
    
    # Add buffer
    target_instances = max(1, int(needed_workers * 1.2))
    
    if target_instances > current_instances:
        return ("scale_up", target_instances)
    elif target_instances < current_instances * 0.5:  # Only scale down if significantly over
        return ("scale_down", max(1, target_instances))
    else:
        return ("no_change", current_instances)
```

---

## Capacity Planning Math

### The Basic Formula

```
Concurrent Requests Needed = Throughput (req/s) × Latency (s)
```

**Example:**

- Expected traffic: 10 requests/second
- Average LLM latency: 2 seconds
- Concurrent requests needed: 10 × 2 = 20 concurrent requests

Your system must handle 20 concurrent requests to sustain 10 req/s.

### Adding Safety Buffer

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAPACITY PLANNING                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Step 1: Calculate baseline                                    │
│   ─────────────────────────                                     │
│   Expected peak traffic:     20 req/s                           │
│   Average latency:           2.5 seconds                        │
│   Baseline concurrency:      20 × 2.5 = 50 concurrent requests  │
│                                                                 │
│   Step 2: Add spike buffer (2-3x)                               │
│   ───────────────────────────                                   │
│   Spike factor:              2.5x                               │
│   Target concurrency:        50 × 2.5 = 125 concurrent requests │
│                                                                 │
│   Step 3: Account for p99 latency                               │
│   ─────────────────────────────                                 │
│   p99 latency:               5 seconds (vs 2.5s average)        │
│   Worst-case concurrency:    20 × 5 × 2.5 = 250 concurrent      │
│                                                                 │
│   Step 4: Translate to infrastructure                           │
│   ───────────────────────────────────                           │
│   If each instance handles ~50 concurrent: need 5 instances     │
│   If using connection pools: size pools for 250 connections     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Capacity Planning Calculation

```python
from dataclasses import dataclass


@dataclass
class CapacityPlan:
    """Capacity planning calculations."""
    
    # Inputs
    expected_peak_rps: float
    average_latency_seconds: float
    p99_latency_seconds: float
    spike_factor: float = 2.5
    
    @property
    def baseline_concurrency(self) -> float:
        """Minimum concurrent requests for expected load."""
        return self.expected_peak_rps * self.average_latency_seconds
    
    @property
    def spike_concurrency(self) -> float:
        """Concurrency needed during traffic spikes."""
        return self.baseline_concurrency * self.spike_factor
    
    @property
    def worst_case_concurrency(self) -> float:
        """Concurrency when both spike and p99 latency hit."""
        return self.expected_peak_rps * self.p99_latency_seconds * self.spike_factor
    
    def instances_needed(self, concurrency_per_instance: int) -> dict:
        """Calculate instances needed for different scenarios."""
        return {
            "baseline": max(1, int(self.baseline_concurrency / concurrency_per_instance) + 1),
            "with_spike_buffer": max(1, int(self.spike_concurrency / concurrency_per_instance) + 1),
            "worst_case": max(1, int(self.worst_case_concurrency / concurrency_per_instance) + 1),
        }
    
    def summary(self) -> str:
        instances = self.instances_needed(concurrency_per_instance=50)
        return f"""
Capacity Plan
=============
Expected Peak Traffic:    {self.expected_peak_rps} req/s
Average Latency:          {self.average_latency_seconds}s
P99 Latency:              {self.p99_latency_seconds}s
Spike Factor:             {self.spike_factor}x

Concurrency Requirements:
  Baseline:               {self.baseline_concurrency:.0f} concurrent
  With Spike Buffer:      {self.spike_concurrency:.0f} concurrent
  Worst Case:             {self.worst_case_concurrency:.0f} concurrent

Instances Needed (assuming 50 concurrent/instance):
  Baseline:               {instances['baseline']}
  Recommended:            {instances['with_spike_buffer']}
  Worst Case:             {instances['worst_case']}
"""


# Example
plan = CapacityPlan(
    expected_peak_rps=20,
    average_latency_seconds=2.5,
    p99_latency_seconds=5.0,
    spike_factor=2.5,
)
print(plan.summary())
```

---

## Cost-Capacity Trade-off

More capacity costs more money. The goal is **right-sizing**: enough capacity for your needs, not more.

```
┌─────────────────────────────────────────────────────────────────┐
│                    COST-CAPACITY TRADE-OFF                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   OVER-PROVISIONED                                              │
│   ├── Capacity: 100 req/s                                       │
│   ├── Actual traffic: 20 req/s                                  │
│   ├── Utilization: 20%                                          │
│   └── Problem: Paying 5x what you need                          │
│                                                                 │
│   UNDER-PROVISIONED                                             │
│   ├── Capacity: 15 req/s                                        │
│   ├── Actual traffic: 20 req/s                                  │
│   ├── Utilization: 133% (impossible)                            │
│   └── Problem: Failures, degraded experience, lost revenue      │
│                                                                 │
│   RIGHT-SIZED                                                   │
│   ├── Capacity: 50 req/s (with spike buffer)                    │
│   ├── Actual traffic: 20 req/s (peaks to 40)                    │
│   ├── Utilization: 40-80%                                       │
│   └── Sweet spot: Handles spikes, not wasteful                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Right-Sizing Strategy

1. **Measure actual traffic patterns** — Don't guess; use historical data
2. **Identify peak hours** — Provision for peaks, not averages
3. **Use autoscaling** — Scale down during low traffic
4. **Set alerts before limits** — Alert at 70% capacity, not 100%
5. **Review regularly** — Traffic patterns change

---

## Load Test → Capacity Plan Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLETE WORKFLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. LOAD TEST (Find Your Limits)                               │
│   ───────────────────────────────                               │
│   • Run ramp-up test to find breaking point                     │
│   • Record max RPS, p95/p99 latency at various loads            │
│   • Identify bottleneck component                               │
│                                                                 │
│   2. PROFILE (Understand Time Distribution)                     │
│   ──────────────────────────────────────────                    │
│   • Measure time in each component                              │
│   • Confirm bottleneck from load test                           │
│   • Identify optimization opportunities                         │
│                                                                 │
│   3. MODEL EXPECTED TRAFFIC                                     │
│   ──────────────────────────                                    │
│   • Historical traffic data                                     │
│   • Projected growth                                            │
│   • Seasonal patterns                                           │
│   • Marketing events / launches                                 │
│                                                                 │
│   4. CALCULATE CAPACITY NEEDS                                   │
│   ────────────────────────────                                  │
│   • Baseline: expected_rps × latency                            │
│   • Add spike buffer: 2-3x                                      │
│   • Consider p99 latency scenarios                              │
│                                                                 │
│   5. PLAN INFRASTRUCTURE                                        │
│   ──────────────────────                                        │
│   • Number of instances                                         │
│   • Connection pool sizes                                       │
│   • Queue capacity                                              │
│   • LLM API tier (rate limits)                                  │
│                                                                 │
│   6. SET ALERTS                                                 │
│   ────────────                                                  │
│   • Alert at 70% capacity (proactive)                           │
│   • Alert on error rate increase                                │
│   • Alert on latency degradation                                │
│                                                                 │
│   7. REVIEW & ITERATE                                           │
│   ────────────────────                                          │
│   • Monthly capacity review                                     │
│   • Adjust based on actual traffic                              │
│   • Re-test after major changes                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **Find your bottleneck first** — Profile end-to-end, test components in isolation. For most LLM apps, it's the LLM API.
    
2. **LLM API is often the limit** — You can't scale past provider rate limits. Solutions: caching, multiple keys, multiple providers, tiered models.
    
3. **Horizontal scaling has limits** — More instances don't help if the bottleneck is a shared resource (LLM API).
    
4. **Queue-based architecture handles spikes** — Accept immediately, process at sustainable rate. Better UX than rejecting requests.
    
5. **Don't autoscale on CPU** — LLM apps are I/O-bound. Scale on queue depth, latency, or connection count instead.
    
6. **Capacity = RPS × Latency** — With buffers for spikes and p99 latency scenarios.
    
7. **Right-size, don't over-provision** — Use autoscaling, review regularly, adjust based on actual traffic patterns.
    

---

## What's Next

Days 5-6 covered the security and reliability foundation:

- **Notes 1-2**: Prompt injection attacks and defenses
- **Note 3**: PII detection and privacy
- **Notes 4-5**: Load testing and capacity planning

The Week 9 capstone will integrate all of these into your Production-Ready Research Assistant.

---

## References

- Little's Law (queue theory): https://en.wikipedia.org/wiki/Little%27s_law
- OpenAI Rate Limits: https://platform.openai.com/docs/guides/rate-limits
- Anthropic Rate Limits: https://docs.anthropic.com/en/api/rate-limits
- AWS Auto Scaling: https://docs.aws.amazon.com/autoscaling/
- Kubernetes HPA: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/