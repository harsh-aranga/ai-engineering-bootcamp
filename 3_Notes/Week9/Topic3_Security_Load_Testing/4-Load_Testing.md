# Note 4: Load Testing LLM Applications — Methodology and Tools

## Why Load Testing LLM Apps Is Different

Load testing a traditional web application is straightforward: send requests, measure latency, find the breaking point. LLM applications introduce complications that make standard approaches misleading or expensive.

```
┌─────────────────────────────────────────────────────────────────┐
│              TRADITIONAL APP vs LLM APP LOAD TESTING            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   TRADITIONAL WEB APP                                           │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ • Response time: 10-100ms typical                       │   │
│   │ • Deterministic: same request → same timing             │   │
│   │ • Cost per request: ~$0 (compute only)                  │   │
│   │ • Bottleneck: your code, DB, network                    │   │
│   │ • Strategy: blast 10k requests, find limits             │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   LLM APPLICATION                                               │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ • Response time: 500ms-5000ms+ typical                  │   │
│   │ • Non-deterministic: same request → variable timing     │   │
│   │ • Cost per request: $0.001-$0.10+ per request           │   │
│   │ • Bottleneck: often the LLM API, not your code          │   │
│   │ • Strategy: thoughtful testing, cost-aware              │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Differences

|Factor|Traditional App|LLM App|
|---|---|---|
|**Latency**|10-100ms|500-5000ms+|
|**Variance**|Low|High (depends on output length, model load)|
|**Cost**|Negligible|$0.001-$0.10+ per request|
|**Rate limits**|Your infrastructure|External API limits|
|**Bottleneck**|Your code|Often the LLM API|
|**Test volume**|10k-100k requests|100-1000 requests (cost-aware)|

### What This Means for Testing

1. **You can't just blast requests** — A 10k request test at $0.01/request = $100. Accidentally run that 10 times during development = $1000.
    
2. **External rate limits matter** — OpenAI, Anthropic, etc. have rate limits. Your test may hit their limits, not yours.
    
3. **High variance requires more samples** — With 10ms requests, 100 samples is enough. With 2000ms ± 500ms requests, you need more samples for statistical significance.
    
4. **The bottleneck is often not your code** — You might find your system handles 100 concurrent users easily... because the LLM API is the bottleneck.
    

---

## Key Metrics to Measure

### Throughput

**Requests per second (RPS)** your system can sustain.

```
Throughput = Total Successful Requests / Total Time (seconds)
```

**For LLM apps, throughput is often limited by:**

- LLM API rate limits (tokens/min, requests/min)
- Your API's concurrent connection handling
- Vector DB query capacity (for RAG)
- Memory (conversation history accumulation)

### Latency

Response time distribution. Single averages are misleading — use percentiles.

```
┌─────────────────────────────────────────────────────────────────┐
│                    LATENCY PERCENTILES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   p50 (median): 50% of requests faster than this                │
│   → What "typical" users experience                             │
│                                                                 │
│   p95: 95% of requests faster than this                         │
│   → What most users experience (SLA target)                     │
│                                                                 │
│   p99: 99% of requests faster than this                         │
│   → Worst case for almost all users                             │
│                                                                 │
│   Example:                                                      │
│   p50 = 1.2s, p95 = 2.5s, p99 = 8.0s                           │
│   → Most requests ~1.2s, but 1% take 8+ seconds                │
│   → The 8s outliers might indicate timeout issues               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**For LLM apps:**

- p50 tells you typical user experience
- p95 is your SLA target (what you promise users)
- p99 reveals timeout issues, retry storms, cold starts

### Error Rate

Percentage of requests that fail under load.

```
Error Rate = (Failed Requests / Total Requests) × 100%
```

**Types of errors to track:**

- **4xx errors:** Client-side issues (rate limiting, bad requests)
- **5xx errors:** Server-side issues (timeouts, crashes)
- **Timeout errors:** Request exceeded time limit
- **Connection errors:** Failed to connect

**For LLM apps, watch for:**

- Rate limit errors (429) from LLM APIs
- Context length errors (input too long)
- Timeout errors (LLM took too long)
- Memory errors (context accumulation)

### Resource Utilization

What your infrastructure is doing under load.

|Resource|What It Tells You|
|---|---|
|**CPU**|Processing bottleneck (rare for LLM apps — usually I/O bound)|
|**Memory**|Conversation history, embeddings, cached responses|
|**Network connections**|Connection pool exhaustion, socket limits|
|**Open file descriptors**|Can limit concurrent connections|

---

## Load Patterns to Test

### Pattern 1: Steady Load

Constant request rate to establish baseline performance.

```
    RPS
    ▲
 10 │ ████████████████████████████████████
    │ ████████████████████████████████████
  5 │ ████████████████████████████████████
    │ ████████████████████████████████████
    └──────────────────────────────────────▶ Time
         Constant 10 RPS for 5 minutes
```

**Purpose:** Find baseline metrics (latency, error rate) at a sustainable load.

**What you learn:**

- Baseline p50, p95, p99 latency
- Error rate at normal load (should be ~0%)
- Resource utilization baseline

### Pattern 2: Ramp Up

Gradually increase load to find the breaking point.

```
    RPS
    ▲
 50 │                              ████████
 40 │                         █████████████
 30 │                    ██████████████████
 20 │               █████████████████████████
 10 │          ██████████████████████████████
  5 │     ███████████████████████████████████
    └──────────────────────────────────────▶ Time
         Increase 5 RPS every 30 seconds
```

**Purpose:** Find maximum sustainable throughput and identify bottlenecks.

**What you learn:**

- At what load does latency degrade?
- At what load do errors start appearing?
- What's the bottleneck? (LLM API, vector DB, your code)

### Pattern 3: Spike

Sudden burst of traffic to test resilience.

```
    RPS
    ▲
100 │          ████████
 50 │          ████████
 10 │ █████████████████████████████████████
  5 │ █████████████████████████████████████
    └──────────────────────────────────────▶ Time
         10 RPS baseline, spike to 100 RPS for 1 minute
```

**Purpose:** Test how system handles sudden traffic bursts (marketing campaign, viral content).

**What you learn:**

- Does the system recover after the spike?
- Do queues build up and cause cascading delays?
- Does rate limiting work correctly?

### Pattern 4: Soak Test

Sustained load over hours to find slow leaks.

```
    RPS
    ▲
 10 │ ████████████████████████████████████...
    │ ████████████████████████████████████...
  5 │ ████████████████████████████████████...
    │ ████████████████████████████████████...
    └──────────────────────────────────────▶ Time
         10 RPS for 4-8 hours
```

**Purpose:** Find memory leaks, connection pool exhaustion, log file growth.

**What you learn:**

- Does memory grow over time? (conversation history not cleaned)
- Do connections leak? (connection pool exhaustion)
- Do logs fill disk?
- Does performance degrade over time?

---

## What You're Actually Measuring

### Your Code's Capacity, Not the LLM API's

When load testing an LLM application, you're primarily testing **your system's ability to handle concurrent requests** — not the LLM API's capacity.

```
┌─────────────────────────────────────────────────────────────────┐
│                    WHAT YOU'RE TESTING                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   YOUR SYSTEM (what you control)                                │
│   ├── Request handling and queuing                              │
│   ├── Input validation and sanitization                         │
│   ├── RAG pipeline (embedding, retrieval)                       │
│   ├── Prompt construction                                       │
│   ├── Response parsing and post-processing                      │
│   ├── Error handling under load                                 │
│   ├── Connection pool management                                │
│   └── Memory management                                         │
│                                                                 │
│   LLM API (what you DON'T control)                              │
│   ├── Model inference time (variable)                           │
│   ├── Rate limits (requests/min, tokens/min)                    │
│   ├── Queue depth on their side                                 │
│   └── Regional capacity                                         │
│                                                                 │
│   Your test results reflect BOTH, but you can only fix yours.   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Finding Your Bottlenecks

A well-instrumented load test reveals where time is spent:

```python
# Breakdown of request time
{
    "total_time_ms": 2500,
    "breakdown": {
        "input_validation_ms": 5,
        "embedding_generation_ms": 50,
        "vector_search_ms": 30,
        "prompt_construction_ms": 2,
        "llm_api_call_ms": 2350,  # ← The bottleneck (usually)
        "response_parsing_ms": 8,
        "output_filtering_ms": 55,
    }
}
```

**Common bottlenecks in LLM apps:**

|Bottleneck|Symptom|Solution|
|---|---|---|
|LLM API latency|90%+ of time in LLM call|Caching, smaller models, shorter prompts|
|LLM API rate limits|429 errors|Request queuing, multiple API keys, batching|
|Vector DB|High embedding/search time|Index optimization, caching, sharding|
|Memory|OOM errors, growing memory|Conversation pruning, streaming|
|Connection pool|Connection timeouts|Increase pool size, connection reuse|

---

## Locust for Load Testing

Locust is a Python-based load testing framework that defines user behavior as code. It's ideal for LLM applications because you can write complex, realistic user scenarios.

### Installation

```bash
pip install locust
# Current version: 2.43.x (as of 2025)
```

### Basic Locust Structure

```python
# locustfile.py
# Docs: https://docs.locust.io/en/stable/

from locust import HttpUser, task, between, events
import random
import time


class ResearchAssistantUser(HttpUser):
    """
    Simulates a user interacting with a Research Assistant API.
    
    Key concepts:
    - HttpUser: Base class for HTTP-based load testing
    - wait_time: Delay between user actions (simulates think time)
    - @task: Methods that represent user actions
    - @task(weight): Higher weight = more frequent execution
    """
    
    # Wait 2-5 seconds between requests (simulates user thinking)
    wait_time = between(2, 5)
    
    # Sample queries for realistic testing
    QUERIES = [
        "What is the refund policy?",
        "How do I reset my password?",
        "What are the shipping options?",
        "Tell me about the return process",
        "What payment methods do you accept?",
        "How long does delivery take?",
        "Can I change my order after placing it?",
        "What is the warranty policy?",
    ]
    
    def on_start(self):
        """Called when a simulated user starts. Use for setup/login."""
        # Example: authenticate if needed
        # self.client.post("/login", json={"user": "test", "pass": "test"})
        self.user_id = f"load_test_user_{random.randint(1000, 9999)}"
    
    @task(3)  # Weight 3: most common action
    def ask_question(self):
        """Simulate asking a question to the research assistant."""
        query = random.choice(self.QUERIES)
        
        with self.client.post(
            "/research",
            json={
                "query": query,
                "user_id": self.user_id,
            },
            timeout=30,
            catch_response=True,  # Allows custom pass/fail logic
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Error: {response.status_code}")
    
    @task(1)  # Weight 1: less common action
    def ask_followup(self):
        """Simulate a follow-up question."""
        with self.client.post(
            "/research",
            json={
                "query": "Can you explain that in more detail?",
                "user_id": self.user_id,
            },
            timeout=30,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Error: {response.status_code}")


# Optional: Custom event handlers for additional metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log additional details for each request."""
    if exception:
        print(f"Request failed: {name} - {exception}")
```

### Running Locust

```bash
# Start with web UI (default)
locust -f locustfile.py --host=http://localhost:8000

# Open http://localhost:8089 in browser
# Configure: Number of users, Spawn rate, then Start

# Headless mode (for CI/CD)
locust -f locustfile.py \
    --host=http://localhost:8000 \
    --users 10 \
    --spawn-rate 2 \
    --run-time 5m \
    --headless \
    --csv=results  # Exports results to CSV
```

### Locust Web UI

The web UI at `http://localhost:8089` shows:

- **Total requests:** Count and RPS
- **Response times:** Median, p95, p99, max
- **Failures:** Count and percentage
- **Charts:** Real-time response time and RPS graphs

### Advanced Locust: Custom Scenarios

```python
from locust import HttpUser, task, between, SequentialTaskSet


class ConversationFlow(SequentialTaskSet):
    """
    Sequential task set for multi-turn conversation testing.
    
    Tasks execute in order, simulating a realistic conversation.
    """
    
    @task
    def initial_question(self):
        """First message in conversation."""
        response = self.client.post(
            "/research",
            json={"query": "What products do you sell?", "user_id": "test"},
            timeout=30,
        )
        # Store for follow-up
        self.last_response = response.json() if response.ok else None
    
    @task
    def followup_question(self):
        """Follow-up based on previous response."""
        self.client.post(
            "/research",
            json={"query": "Tell me more about the first one", "user_id": "test"},
            timeout=30,
        )
    
    @task
    def final_question(self):
        """Final question, then stop this user."""
        self.client.post(
            "/research",
            json={"query": "What's the price?", "user_id": "test"},
            timeout=30,
        )
        self.interrupt()  # Stop this task set


class ConversationUser(HttpUser):
    """User that runs conversation flows."""
    wait_time = between(1, 3)
    tasks = [ConversationFlow]
```

---

## Simple Async Load Test (Without Locust)

Sometimes you need a quick load test without installing Locust. Here's a minimal async implementation:

```python
# simple_load_test.py
# No external dependencies beyond aiohttp

import asyncio
import aiohttp
import time
import random
from dataclasses import dataclass, field
from statistics import mean, median, quantiles
from typing import Optional


@dataclass
class LoadTestResult:
    """Results from a load test run."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time_seconds: float
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    @property
    def requests_per_second(self) -> float:
        return self.total_requests / self.total_time_seconds if self.total_time_seconds > 0 else 0
    
    @property
    def error_rate(self) -> float:
        return (self.failed_requests / self.total_requests * 100) if self.total_requests > 0 else 0
    
    @property
    def p50_ms(self) -> float:
        return median(self.latencies_ms) if self.latencies_ms else 0
    
    @property
    def p95_ms(self) -> float:
        if len(self.latencies_ms) < 20:
            return max(self.latencies_ms) if self.latencies_ms else 0
        return quantiles(self.latencies_ms, n=20)[18]
    
    @property
    def p99_ms(self) -> float:
        if len(self.latencies_ms) < 100:
            return max(self.latencies_ms) if self.latencies_ms else 0
        return quantiles(self.latencies_ms, n=100)[98]
    
    def summary(self) -> str:
        return f"""
Load Test Results
=================
Total Requests:     {self.total_requests}
Successful:         {self.successful_requests}
Failed:             {self.failed_requests}
Error Rate:         {self.error_rate:.2f}%
Duration:           {self.total_time_seconds:.2f}s
Throughput:         {self.requests_per_second:.2f} req/s

Latency (ms):
  p50:              {self.p50_ms:.0f}
  p95:              {self.p95_ms:.0f}
  p99:              {self.p99_ms:.0f}
  min:              {min(self.latencies_ms):.0f}
  max:              {max(self.latencies_ms):.0f}
  mean:             {mean(self.latencies_ms):.0f}
"""


async def run_load_test(
    url: str,
    num_requests: int,
    concurrency: int,
    queries: list[str],
    timeout_seconds: int = 30,
) -> LoadTestResult:
    """
    Run a simple async load test.
    
    Args:
        url: Target endpoint URL
        num_requests: Total number of requests to send
        concurrency: Maximum concurrent requests
        queries: List of query strings to randomly select from
        timeout_seconds: Request timeout
        
    Returns:
        LoadTestResult with metrics
    """
    latencies = []
    errors = []
    successful = 0
    failed = 0
    
    semaphore = asyncio.Semaphore(concurrency)
    
    async def make_request(session: aiohttp.ClientSession, query: str) -> None:
        nonlocal successful, failed
        
        async with semaphore:
            start = time.perf_counter()
            try:
                async with session.post(
                    url,
                    json={"query": query, "user_id": "load_test"},
                    timeout=aiohttp.ClientTimeout(total=timeout_seconds),
                ) as response:
                    latency_ms = (time.perf_counter() - start) * 1000
                    latencies.append(latency_ms)
                    
                    if response.status == 200:
                        successful += 1
                    else:
                        failed += 1
                        errors.append(f"HTTP {response.status}")
                        
            except asyncio.TimeoutError:
                failed += 1
                errors.append("Timeout")
            except aiohttp.ClientError as e:
                failed += 1
                errors.append(str(e))
    
    # Create all request tasks
    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            make_request(session, random.choice(queries))
            for _ in range(num_requests)
        ]
        
        start_time = time.perf_counter()
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_time
    
    return LoadTestResult(
        total_requests=num_requests,
        successful_requests=successful,
        failed_requests=failed,
        total_time_seconds=total_time,
        latencies_ms=latencies,
        errors=errors[:10],  # Keep first 10 errors
    )


# Usage
async def main():
    SAMPLE_QUERIES = [
        "What is the refund policy?",
        "How do I reset my password?",
        "What are the shipping options?",
        "Tell me about your return process",
        "What payment methods do you accept?",
    ]
    
    print("Starting load test...")
    
    result = await run_load_test(
        url="http://localhost:8000/research",
        num_requests=100,
        concurrency=10,
        queries=SAMPLE_QUERIES,
        timeout_seconds=30,
    )
    
    print(result.summary())


if __name__ == "__main__":
    asyncio.run(main())
```

### When to Use Simple vs Locust

|Use Simple Async Test|Use Locust|
|---|---|
|Quick one-off tests|Ongoing load testing|
|CI/CD integration (minimal deps)|Complex user scenarios|
|Simple request patterns|Multi-step conversations|
|No web UI needed|Real-time monitoring|
|Single script, no setup|Distributed testing|

---

## Cost-Aware Load Testing

LLM calls cost money. A careless load test can burn through your budget.

### The Math

```
Cost = Requests × Cost per Request

Example (GPT-4):
- Input: ~500 tokens × $0.01/1k = $0.005
- Output: ~200 tokens × $0.03/1k = $0.006
- Total per request: ~$0.011

1,000 requests = $11
10,000 requests = $110
100,000 requests = $1,100
```

### Cost-Aware Testing Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    COST-AWARE TESTING LAYERS                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   LAYER 1: MOCK TESTING (Cost: $0)                              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ Purpose: Stress test YOUR infrastructure                │   │
│   │ • Mock LLM responses (instant, realistic latency)       │   │
│   │ • Test 10k+ requests                                    │   │
│   │ • Find connection limits, memory issues                 │   │
│   │ • Validate error handling                               │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   LAYER 2: CHEAP MODEL TESTING (Cost: Low)                      │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ Purpose: Test real LLM integration                      │   │
│   │ • Use gpt-4o-mini instead of gpt-4o                     │   │
│   │ • Test 100-500 requests                                 │   │
│   │ • Validate rate limiting, error handling                │   │
│   │ • Check response parsing with real outputs              │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   LAYER 3: PRODUCTION MODEL TESTING (Cost: High)                │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ Purpose: Final validation before release                │   │
│   │ • Use actual production model                           │   │
│   │ • Test 50-100 requests (statistical sample)             │   │
│   │ • Validate realistic latency                            │   │
│   │ • Final smoke test                                      │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementing Mock LLM for Load Testing

```python
import asyncio
import random
from typing import Optional


class MockLLMClient:
    """
    Mock LLM client for load testing infrastructure.
    
    Simulates realistic LLM behavior:
    - Variable latency (500ms-3000ms)
    - Occasional failures (rate limits, timeouts)
    - Realistic response sizes
    """
    
    def __init__(
        self,
        min_latency_ms: int = 500,
        max_latency_ms: int = 3000,
        failure_rate: float = 0.02,  # 2% failure rate
        rate_limit_rate: float = 0.01,  # 1% rate limit errors
    ):
        self.min_latency_ms = min_latency_ms
        self.max_latency_ms = max_latency_ms
        self.failure_rate = failure_rate
        self.rate_limit_rate = rate_limit_rate
        
        self._sample_responses = [
            "Based on the documentation, the refund policy allows returns within 30 days of purchase.",
            "To reset your password, click the 'Forgot Password' link on the login page.",
            "We offer standard shipping (5-7 days) and express shipping (2-3 days).",
            "The return process is simple: contact support, receive a return label, and ship the item back.",
            "We accept Visa, Mastercard, American Express, and PayPal.",
        ]
    
    async def generate(self, prompt: str) -> dict:
        """
        Simulate an LLM API call.
        
        Returns:
            {
                "response": str,
                "tokens_used": int,
                "latency_ms": float,
            }
            
        Raises:
            Exception on simulated failures
        """
        # Simulate latency (bimodal: most fast, some slow)
        if random.random() < 0.1:  # 10% slow requests
            latency_ms = random.uniform(2000, self.max_latency_ms)
        else:
            latency_ms = random.uniform(self.min_latency_ms, 1500)
        
        await asyncio.sleep(latency_ms / 1000)
        
        # Simulate failures
        if random.random() < self.rate_limit_rate:
            raise Exception("Rate limit exceeded (429)")
        
        if random.random() < self.failure_rate:
            raise Exception("Internal server error (500)")
        
        response = random.choice(self._sample_responses)
        tokens = len(response.split()) * 1.3  # Rough token estimate
        
        return {
            "response": response,
            "tokens_used": int(tokens),
            "latency_ms": latency_ms,
        }


class LLMClientWrapper:
    """
    Wrapper that can switch between real and mock LLM clients.
    
    Usage:
        # For load testing infrastructure
        client = LLMClientWrapper(use_mock=True)
        
        # For production
        client = LLMClientWrapper(use_mock=False, real_client=openai_client)
    """
    
    def __init__(
        self,
        use_mock: bool = False,
        real_client = None,
        mock_config: dict = None,
    ):
        self.use_mock = use_mock
        self.real_client = real_client
        
        if use_mock:
            self.mock_client = MockLLMClient(**(mock_config or {}))
    
    async def generate(self, prompt: str, **kwargs) -> dict:
        if self.use_mock:
            return await self.mock_client.generate(prompt)
        else:
            # Call real LLM client
            return await self._call_real_client(prompt, **kwargs)
    
    async def _call_real_client(self, prompt: str, **kwargs) -> dict:
        # Implementation depends on your LLM client
        raise NotImplementedError("Implement for your LLM client")
```

### Cost Safeguards

```python
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CostLimiter:
    """
    Prevent accidental cost overruns during load testing.
    """
    max_requests: int = 1000
    max_cost_dollars: float = 50.0
    cost_per_request: float = 0.01  # Estimate
    
    _request_count: int = 0
    _estimated_cost: float = 0.0
    _start_time: datetime = None
    
    def check_and_increment(self) -> bool:
        """
        Check if we can make another request.
        
        Returns:
            True if allowed, False if limit reached
        """
        if self._start_time is None:
            self._start_time = datetime.now()
        
        if self._request_count >= self.max_requests:
            print(f"⚠️  Request limit reached: {self.max_requests}")
            return False
        
        if self._estimated_cost >= self.max_cost_dollars:
            print(f"⚠️  Cost limit reached: ${self.max_cost_dollars}")
            return False
        
        self._request_count += 1
        self._estimated_cost += self.cost_per_request
        
        return True
    
    def summary(self) -> str:
        duration = datetime.now() - self._start_time if self._start_time else timedelta(0)
        return f"""
Cost Summary
============
Requests:       {self._request_count}
Estimated Cost: ${self._estimated_cost:.2f}
Duration:       {duration}
"""


# Usage in load test
cost_limiter = CostLimiter(max_requests=500, max_cost_dollars=10.0)

async def guarded_request():
    if not cost_limiter.check_and_increment():
        raise Exception("Cost limit reached, stopping test")
    
    # Make actual request
    ...
```

---

## Interpreting Results

### What Good Results Look Like

```
Load Test Results (100 requests, 10 concurrent)
===============================================
Throughput:     2.5 req/s         ✓ Expected for LLM app
Error Rate:     0%                ✓ No errors
p50 Latency:    1,200ms           ✓ Typical LLM response
p95 Latency:    2,500ms           ✓ Acceptable
p99 Latency:    3,800ms           ✓ Within timeout
```

### Warning Signs

|Symptom|Possible Cause|Investigation|
|---|---|---|
|p99 >> p95|Timeouts, retry storms|Check timeout settings, retry logic|
|Error rate > 5%|Rate limiting, crashes|Check error types (429? 500?)|
|Throughput plateau|Bottleneck reached|Identify bottleneck (CPU? Connections? API?)|
|Latency increases over time|Memory leak, queue buildup|Run soak test, check memory|
|High CPU but low throughput|Inefficient code|Profile your code|

---

## Key Takeaways

1. **LLM apps are different** — High latency, variable timing, real costs per request. Adjust your testing approach.
    
2. **Know what you're testing** — Usually your infrastructure's capacity, not the LLM API's. The LLM call is often the bottleneck.
    
3. **Use appropriate load patterns** — Steady for baseline, ramp for breaking point, spike for resilience, soak for leaks.
    
4. **Cost-aware testing is mandatory** — Use mocks for infrastructure stress testing, real calls for integration validation.
    
5. **Locust is the go-to tool** — Python-based, realistic user scenarios, real-time web UI. Current version: 2.43.x.
    
6. **Percentiles, not averages** — p50, p95, p99 tell the real story. Averages hide outliers.
    
7. **Simple async tests work too** — For quick checks or CI/CD, a simple asyncio script is often enough.
    

---

## What's Next

- **Note 5** covers the SecurityLayer integration — combining input validation, output filtering, PII handling, and load testing readiness into a cohesive wrapper for your Research Assistant

---

## References

- Locust Documentation: https://docs.locust.io/en/stable/
- Locust GitHub: https://github.com/locustio/locust
- Locust PyPI: https://pypi.org/project/locust/
- aiohttp Documentation: https://docs.aiohttp.org/