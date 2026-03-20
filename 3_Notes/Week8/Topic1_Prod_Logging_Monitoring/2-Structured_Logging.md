# Note 2: Structured Logging for LLM Systems

## Why Structured Logging Beats Plain Text

Traditional logging looks like this:

```
2024-01-15 14:32:05 INFO Processing query for user 456: "What is our refund policy?"
2024-01-15 14:32:06 INFO Query completed in 850ms, used 1500 input tokens, 350 output tokens
2024-01-15 14:32:07 ERROR Request failed for user 789: timeout after 30s
```

Human-readable, but try answering:

- What's the average latency for queries that succeeded?
- How many tokens did user 456 consume today?
- Which query types have the highest error rate?

You'd need to parse these strings with regex, hope the format is consistent, and pray no one logs a colon in their query text.

**Structured logging** outputs machine-parseable records — typically JSON:

```json
{"timestamp": "2024-01-15T14:32:05Z", "level": "info", "event": "query_completed", "user_id": "456", "query_type": "internal_docs", "latency_ms": 850, "input_tokens": 1500, "output_tokens": 350, "status": "success"}
{"timestamp": "2024-01-15T14:32:07Z", "level": "error", "event": "query_failed", "user_id": "789", "error_type": "timeout", "latency_ms": 30000, "status": "error"}
```

Now your log aggregator (Elasticsearch, Loki, CloudWatch) can:

- **Filter**: `user_id = "456" AND status = "error"`
- **Aggregate**: `AVG(latency_ms) WHERE status = "success"`
- **Visualize**: Latency percentiles over time, grouped by `query_type`

The tradeoffs:

|Aspect|Plain Text|Structured (JSON)|
|---|---|---|
|Human readability|✓ Better in terminal|Harder to scan raw|
|Machine parseable|Requires regex|✓ Native parsing|
|Queryable at scale|Expensive full-text search|✓ Field-level indexing|
|Schema enforcement|None|Optional but possible|
|Log size|Smaller|Larger (field names repeated)|

For production LLM systems, structured logging is non-negotiable. You'll be debugging issues across thousands of requests — you need to filter and aggregate, not grep.

---

## What to Log for LLM Requests

A comprehensive LLM request log entry should capture:

```python
# Complete log schema for an LLM request
llm_request_log = {
    # === Identity & Timing ===
    "timestamp": "2024-01-15T14:32:05.123Z",  # ISO 8601, with milliseconds
    "request_id": "req_abc123def456",          # Unique per request, for correlation
    "user_id": "user_789",                      # Who made the request
    
    # === Query Details ===
    "query_hash": "sha256:a1b2c3...",          # Hash if PII concerns (see below)
    # OR
    "query": "What is our refund policy?",     # Raw query (dev/internal only)
    "query_type": "internal_docs",              # Classification: internal_docs, web_search, general
    "query_length_chars": 28,
    
    # === Execution Details ===
    "tools_used": ["rag_retrieval", "none"],   # Which tools/paths were invoked
    "rag_chunks_retrieved": 5,                  # RAG-specific: how many chunks
    "rag_top_score": 0.87,                      # RAG-specific: best relevance score
    "model": "gpt-4o-mini",                     # Which model was used
    "model_temperature": 0.7,                   # Model parameters that affect output
    
    # === Token Economics ===
    "input_tokens": 1500,
    "output_tokens": 350,
    "total_tokens": 1850,
    
    # === Cost ===
    "estimated_cost_usd": 0.0032,              # Calculated from token counts + pricing
    
    # === Performance ===
    "latency_ms": 850,
    "latency_breakdown": {                      # Where time was spent
        "retrieval_ms": 200,
        "rerank_ms": 50,
        "prompt_assembly_ms": 20,
        "generation_ms": 560,
        "guardrail_ms": 20
    },
    
    # === Outcome ===
    "status": "success",                        # success | error | timeout | rate_limited
    "error_type": None,                         # If failed: TimeoutError, RateLimitError, etc.
    "error_message": None,                      # If failed: human-readable message
    
    # === Quality Signals (optional) ===
    "response_length_chars": 450,
    "guardrail_triggered": False,
    "cache_hit": False
}
```

### Why Each Field Matters

**Identity fields** (`request_id`, `user_id`, `timestamp`):

- `request_id` correlates logs across your entire stack (frontend, API, worker, vector store)
- `user_id` identifies abuse patterns and per-user debugging
- ISO timestamps with milliseconds enable precise ordering

**Query details** (`query`, `query_type`, `query_hash`):

- Query type enables analysis by category (which types are slow? expensive? failing?)
- Raw query vs. hash depends on PII policy (discussed below)

**Execution details** (`tools_used`, `model`, `rag_chunks_retrieved`):

- Essential for debugging "why did this request behave differently?"
- `rag_top_score` reveals retrieval quality issues before they manifest as bad answers

**Token economics** (`input_tokens`, `output_tokens`):

- The fundamental cost driver — you must track this
- Input vs. output matters because pricing differs (output tokens often 3-4x more expensive)

**Cost** (`estimated_cost_usd`):

- Calculated at log time: `(input_tokens * input_price) + (output_tokens * output_price)`
- Enables real-time cost tracking without post-processing

**Performance** (`latency_ms`, `latency_breakdown`):

- Total latency is essential; breakdown is invaluable for optimization
- If retrieval is 80% of latency, you know where to focus

**Outcome** (`status`, `error_type`, `error_message`):

- `status` enables error rate calculations
- Structured `error_type` enables grouping ("how many timeouts vs. rate limits?")

---

## Python `structlog` Setup

`structlog` is the production standard for structured logging in Python. It's composable, async-safe, and integrates cleanly with both standalone scripts and web frameworks.

**Installation:**

```bash
pip install structlog
```

**Basic production configuration:**

```python
# logging_config.py
# Reference: structlog 25.5.0 documentation
# https://www.structlog.org/en/stable/getting-started.html

import logging
import structlog

def configure_logging(json_output: bool = True, log_level: int = logging.INFO):
    """
    Configure structlog for production use.
    
    Args:
        json_output: True for production (JSON), False for development (colored console)
        log_level: Minimum log level to output
    """
    
    # Shared processors for both modes
    shared_processors = [
        # Merge context variables (request_id, user_id bound elsewhere)
        structlog.contextvars.merge_contextvars,
        # Add log level to event dict
        structlog.processors.add_log_level,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Handle exceptions
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]
    
    if json_output:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
        logger_factory = structlog.WriteLoggerFactory()
    else:
        # Development: colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
        logger_factory = structlog.PrintLoggerFactory()
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=logger_factory,
        cache_logger_on_first_use=True,
    )

# Call at application startup
configure_logging(json_output=True)  # Production
# configure_logging(json_output=False)  # Development
```

**Using the configured logger:**

```python
import structlog

logger = structlog.get_logger()

# Simple logging
logger.info("application_started", version="1.0.0")

# With additional context
logger.info(
    "query_completed",
    user_id="user_123",
    latency_ms=850,
    tokens=1500,
    status="success"
)

# Errors with exception info
try:
    risky_operation()
except Exception as e:
    logger.error(
        "operation_failed",
        error_type=type(e).__name__,
        error_message=str(e),
        exc_info=True  # Includes stack trace
    )
```

**Output (JSON mode):**

```json
{"event": "query_completed", "user_id": "user_123", "latency_ms": 850, "tokens": 1500, "status": "success", "level": "info", "timestamp": "2024-01-15T14:32:05.123456Z"}
```

---

## Binding Context: request_id Flows Through All Logs

The killer feature of `structlog` is **context binding**. Instead of passing `request_id` to every log call, you bind it once at the start of a request, and it appears in all subsequent logs.

```python
# Reference: structlog contextvars documentation
# https://www.structlog.org/en/stable/contextvars.html

import uuid
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger()

def handle_request(user_id: str, query: str):
    """
    Main request handler. Binds context that flows to all downstream logs.
    """
    # Generate unique request ID
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
    # Clear any stale context from previous requests (important in web servers)
    clear_contextvars()
    
    # Bind context — these fields appear in ALL subsequent logs
    bind_contextvars(
        request_id=request_id,
        user_id=user_id
    )
    
    logger.info("request_started", query_length=len(query))
    
    # Call downstream functions — they don't need to know about request_id
    chunks = retrieve_documents(query)
    response = generate_response(query, chunks)
    
    logger.info("request_completed", status="success")
    
    return response


def retrieve_documents(query: str) -> list:
    """
    Downstream function. Logs automatically include request_id and user_id.
    """
    logger.info("retrieval_started")
    
    # ... do retrieval ...
    chunks = ["chunk1", "chunk2"]
    
    logger.info("retrieval_completed", chunks_found=len(chunks))
    return chunks


def generate_response(query: str, chunks: list) -> str:
    """
    Another downstream function. Still has context.
    """
    logger.info("generation_started", model="gpt-4o-mini")
    
    # ... call LLM ...
    response = "The refund policy is..."
    
    logger.info("generation_completed", output_tokens=350)
    return response
```

**Output:**

```json
{"event": "request_started", "query_length": 28, "request_id": "req_abc123def456", "user_id": "user_789", "level": "info", "timestamp": "..."}
{"event": "retrieval_started", "request_id": "req_abc123def456", "user_id": "user_789", "level": "info", "timestamp": "..."}
{"event": "retrieval_completed", "chunks_found": 2, "request_id": "req_abc123def456", "user_id": "user_789", "level": "info", "timestamp": "..."}
{"event": "generation_started", "model": "gpt-4o-mini", "request_id": "req_abc123def456", "user_id": "user_789", "level": "info", "timestamp": "..."}
{"event": "generation_completed", "output_tokens": 350, "request_id": "req_abc123def456", "user_id": "user_789", "level": "info", "timestamp": "..."}
{"event": "request_completed", "status": "success", "request_id": "req_abc123def456", "user_id": "user_789", "level": "info", "timestamp": "..."}
```

Every log entry has `request_id` and `user_id` — without passing them through every function signature.

**How it works:** `structlog.contextvars` uses Python's `contextvars` module, which provides context-local storage that works correctly with async code. Each request/task gets its own context, so concurrent requests don't mix up their bound values.

---

## Log Levels for LLM Systems

Log levels filter what gets recorded. In production, you typically set the minimum level to INFO, suppressing DEBUG.

### Standard Levels (Python's logging convention)

|Level|When to Use|Examples|
|---|---|---|
|DEBUG|Development only. Verbose details.|Full prompts, full responses, intermediate states|
|INFO|Normal operations. What happened.|Request started, request completed, retrieval done|
|WARNING|Degraded but not failed.|Low relevance scores, retry triggered, cache miss|
|ERROR|Something failed.|Exceptions, timeouts, rate limits|
|CRITICAL|System-level failure.|Database down, model API unreachable, out of memory|

### LLM-Specific Log Level Guidelines

**INFO — Normal flow:**

```python
logger.info("request_started", query_type="internal_docs")
logger.info("retrieval_completed", chunks=5, top_score=0.85)
logger.info("generation_completed", tokens=350, latency_ms=560)
logger.info("request_completed", status="success", total_latency_ms=850)
```

**WARNING — Degraded but functional:**

```python
# Low retrieval quality — might produce bad answer
logger.warning(
    "low_relevance_retrieval",
    top_score=0.45,
    threshold=0.6,
    chunks_retrieved=5
)

# Retry was needed
logger.warning(
    "llm_retry_triggered",
    attempt=2,
    reason="rate_limit",
    backoff_seconds=2
)

# Unusual but not broken
logger.warning(
    "unusually_long_response",
    output_tokens=4000,
    typical_max=1000
)
```

**ERROR — Failures:**

```python
# Request failed
logger.error(
    "request_failed",
    error_type="TimeoutError",
    error_message="LLM call timed out after 30s",
    model="gpt-4o"
)

# Guardrail blocked response
logger.error(
    "guardrail_blocked",
    reason="pii_detected",
    action="response_suppressed"
)

# Empty retrieval (might be valid, but often indicates problem)
logger.error(
    "retrieval_empty",
    query_type="internal_docs",
    message="No chunks retrieved for query"
)
```

**DEBUG — Development/troubleshooting only:**

```python
# Full prompt (potentially sensitive, large)
logger.debug(
    "prompt_assembled",
    system_prompt=system_prompt,  # Could be 1000+ tokens
    user_query=query,
    context_chunks=chunks  # Could be very large
)

# Full LLM response
logger.debug(
    "llm_raw_response",
    response_text=response  # Potentially contains PII
)
```

**Why DEBUG is risky in production:**

1. **Size**: Logging full prompts and responses can 10x your log volume
2. **Cost**: Log storage is priced by volume
3. **PII**: User queries and LLM responses often contain personal information
4. **Performance**: Writing large log entries has overhead

Rule of thumb: INFO for "what happened," WARNING for "something's off," ERROR for "something broke," DEBUG for "everything about what happened" (dev only).

---

## PII Considerations

LLM systems handle user queries — which often contain personal information. Logging raw queries creates compliance and security risks.

### The Problem

```python
# User query that might contain PII
query = "What's the refund policy for order #12345? My email is john@example.com and I paid with card ending 4242"

# If you log this...
logger.info("query_received", query=query)

# You've now stored:
# - Order number (potentially identifies user)
# - Email address (definitely PII)
# - Partial card number (sensitive)
```

This creates issues:

- **GDPR**: User has right to deletion — can you delete this query from all log backups?
- **PCI-DSS**: Card numbers (even partial) have strict storage requirements
- **Security**: Log files are often less protected than databases

### Strategies

**Option 1: Don't log queries in production**

```python
# Log metadata only
logger.info(
    "query_received",
    query_length=len(query),
    query_type=classify_query(query)
)
```

Simple and safe, but you lose debuggability.

**Option 2: Hash queries**

```python
import hashlib

def hash_query(query: str) -> str:
    return f"sha256:{hashlib.sha256(query.encode()).hexdigest()[:16]}"

logger.info(
    "query_received",
    query_hash=hash_query(query),  # "sha256:a1b2c3d4e5f6g7h8"
    query_length=len(query)
)
```

You can correlate logs for the same query, but can't see the content. Useful for pattern detection ("same hash appearing 1000 times = someone's looping").

**Option 3: Redact sensitive patterns**

```python
import re

def redact_pii(text: str) -> str:
    # Email
    text = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', '[EMAIL]', text)
    # Credit card (naive pattern)
    text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD]', text)
    # Partial card
    text = re.sub(r'\b(card|ending)\s*\d{4}\b', '[CARD_PARTIAL]', text, flags=re.I)
    # Order numbers (if you have a pattern)
    text = re.sub(r'order\s*#?\s*\d+', '[ORDER_ID]', text, flags=re.I)
    return text

logger.info(
    "query_received",
    query=redact_pii(query)
)
# "What's the refund policy for [ORDER_ID]? My email is [EMAIL] and I paid with [CARD_PARTIAL]"
```

Preserves some debuggability while removing obvious PII. But regex-based redaction is never complete — new PII patterns will slip through.

**Option 4: Tiered logging with access controls**

```python
# Public logs (INFO) — safe metadata only
public_logger = structlog.get_logger("app.public")
public_logger.info("query_received", query_length=len(query), query_type="support")

# Restricted logs (DEBUG) — full content, separate storage with access controls
restricted_logger = structlog.get_logger("app.restricted")
restricted_logger.debug("query_content", query=query, response=response)
```

Route restricted logs to a separate system with stricter access controls, shorter retention, and audit logging.

### Production Recommendation

For most LLM systems:

1. **INFO level (always logged)**: No raw queries, no raw responses. Log lengths, types, hashes, tokens, latencies, statuses.
    
2. **DEBUG level (never in production by default)**: Full queries and responses. Only enable temporarily for specific debugging, with a defined retention period.
    
3. **If you must log queries**: Use redaction + tiered storage. Accept that redaction is imperfect.
    
4. **Document your policy**: Your team needs to know what's logged where, and for how long.
    

---

## Putting It Together: LLM Request Logging

Here's a complete example integrating everything:

```python
# llm_logging.py
# Reference: structlog 25.5.0 documentation

import time
import uuid
import hashlib
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResult:
    """Result from an LLM call."""
    response: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LLMRequestLogger:
    """
    Structured logging for LLM requests.
    
    Handles context binding, latency tracking, and consistent log schemas.
    """
    
    # Pricing per 1M tokens (example rates, update as needed)
    PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    }
    
    def __init__(self, log_queries: bool = False):
        """
        Args:
            log_queries: If True, log query hashes. If False, log only metadata.
        """
        self.logger = structlog.get_logger()
        self.log_queries = log_queries
    
    def start_request(self, user_id: str, query: str, query_type: str) -> str:
        """
        Call at the start of each request. Returns request_id for correlation.
        """
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        # Clear stale context, bind new context
        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            user_id=user_id
        )
        
        # Build log entry
        log_data = {
            "query_type": query_type,
            "query_length_chars": len(query),
        }
        
        if self.log_queries:
            log_data["query_hash"] = self._hash_query(query)
        
        self.logger.info("request_started", **log_data)
        
        return request_id
    
    def log_retrieval(
        self,
        chunks_retrieved: int,
        top_score: Optional[float],
        latency_ms: float
    ):
        """Log RAG retrieval step."""
        log_data = {
            "chunks_retrieved": chunks_retrieved,
            "latency_ms": round(latency_ms, 2),
        }
        
        if top_score is not None:
            log_data["top_score"] = round(top_score, 3)
            
            # Warn on low relevance
            if top_score < 0.6:
                self.logger.warning(
                    "low_relevance_retrieval",
                    **log_data,
                    threshold=0.6
                )
                return
        
        self.logger.info("retrieval_completed", **log_data)
    
    def log_generation(self, result: LLMResult):
        """Log LLM generation step."""
        cost = self._calculate_cost(
            result.model,
            result.input_tokens,
            result.output_tokens
        )
        
        self.logger.info(
            "generation_completed",
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=round(result.latency_ms, 2),
            cost_usd=round(cost, 6)
        )
    
    def complete_request(
        self,
        status: str,
        total_latency_ms: float,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Log request completion."""
        log_data = {
            "status": status,
            "total_latency_ms": round(total_latency_ms, 2),
        }
        
        if status == "success":
            self.logger.info("request_completed", **log_data)
        else:
            log_data["error_type"] = error_type
            log_data["error_message"] = error_message
            self.logger.error("request_failed", **log_data)
    
    def _hash_query(self, query: str) -> str:
        """Hash query for logging without exposing content."""
        return f"sha256:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate request cost in USD."""
        pricing = self.PRICING.get(model, {"input": 0, "output": 0})
        cost = (
            (input_tokens / 1_000_000) * pricing["input"] +
            (output_tokens / 1_000_000) * pricing["output"]
        )
        return cost


# Usage example
def process_query(user_id: str, query: str) -> str:
    """Example request handler with full logging."""
    llm_logger = LLMRequestLogger(log_queries=True)
    start_time = time.time()
    
    try:
        # Start request
        request_id = llm_logger.start_request(
            user_id=user_id,
            query=query,
            query_type="internal_docs"
        )
        
        # Retrieval step
        retrieval_start = time.time()
        chunks = ["chunk1", "chunk2", "chunk3"]  # Simulated
        top_score = 0.85
        llm_logger.log_retrieval(
            chunks_retrieved=len(chunks),
            top_score=top_score,
            latency_ms=(time.time() - retrieval_start) * 1000
        )
        
        # Generation step
        generation_start = time.time()
        result = LLMResult(
            response="The refund policy states...",
            model="gpt-4o-mini",
            input_tokens=1500,
            output_tokens=350,
            latency_ms=(time.time() - generation_start) * 1000
        )
        llm_logger.log_generation(result)
        
        # Complete request
        llm_logger.complete_request(
            status="success",
            total_latency_ms=(time.time() - start_time) * 1000
        )
        
        return result.response
        
    except Exception as e:
        llm_logger.complete_request(
            status="error",
            total_latency_ms=(time.time() - start_time) * 1000,
            error_type=type(e).__name__,
            error_message=str(e)
        )
        raise
```

---

## Key Takeaways

1. **Structured logging (JSON) is essential for production.** Plain text doesn't scale when you need to query across thousands of requests.
    
2. **Log the right fields.** Request ID, user ID, query type, tokens, cost, latency breakdown, and status. These enable debugging and monitoring.
    
3. **Use `structlog` with context binding.** Bind `request_id` once at the start, and it flows to all downstream logs automatically via `contextvars`.
    
4. **Log levels matter.** INFO for normal flow, WARNING for degraded states, ERROR for failures. Keep DEBUG for development only.
    
5. **PII is a real concern.** Don't log raw queries in production. Use hashing, redaction, or tiered logging with access controls.
    
6. **Consistency beats perfection.** A simpler schema logged consistently is more valuable than a complex schema logged inconsistently.