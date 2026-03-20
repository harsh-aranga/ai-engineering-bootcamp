# Retry Strategies: Exponential Backoff, Jitter, and Idempotency

## When to Retry

The first question isn't "how" to retry—it's "should" you retry at all. Retrying the wrong kind of error wastes time, burns tokens, and can make problems worse.

### The Fundamental Split: Transient vs Persistent

**Transient errors** are temporary. The same request that failed now might succeed in a few seconds:

- Network timeouts (connection dropped, slow response)
- Rate limits (you're going too fast, slow down)
- Server overload (503 Service Unavailable)
- Temporary resource contention

**Persistent errors** won't fix themselves with time:

- Authentication failures (401/403—your API key is wrong)
- Invalid request (400—your input is malformed)
- Resource not found (404—that endpoint doesn't exist)
- Validation errors (your data doesn't match the schema)

Retrying a persistent error is worse than useless—it delays failure, wastes resources, and might get you rate-limited on top of the original problem.

### Error Classification for LLM Systems

```python
from enum import Enum
from typing import Type

class ErrorCategory(Enum):
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    RETRYABLE_WITH_BACKOFF = "retryable_with_backoff"

# Map specific errors to categories
# Note: These exception types are provider-specific. 
# Check your provider's SDK for exact exception classes.

LLM_ERROR_CLASSIFICATION = {
    # Transient - retry immediately or with short delay
    "timeout": ErrorCategory.RETRYABLE,
    "connection_error": ErrorCategory.RETRYABLE,
    "server_error_500": ErrorCategory.RETRYABLE,
    "server_error_502": ErrorCategory.RETRYABLE,
    "server_error_503": ErrorCategory.RETRYABLE,
    
    # Rate limit - retry with backoff (provider is telling you to slow down)
    "rate_limit_429": ErrorCategory.RETRYABLE_WITH_BACKOFF,
    
    # Persistent - don't retry
    "authentication_401": ErrorCategory.NON_RETRYABLE,
    "forbidden_403": ErrorCategory.NON_RETRYABLE,
    "bad_request_400": ErrorCategory.NON_RETRYABLE,
    "not_found_404": ErrorCategory.NON_RETRYABLE,
    "content_filter": ErrorCategory.NON_RETRYABLE,
    "context_length_exceeded": ErrorCategory.NON_RETRYABLE,
    "invalid_api_key": ErrorCategory.NON_RETRYABLE,
}

def classify_error(error: Exception) -> ErrorCategory:
    """
    Classify an error for retry decision.
    
    Provider SDKs expose different exception hierarchies.
    This is a simplified example—adapt to your specific providers.
    """
    error_type = type(error).__name__.lower()
    error_message = str(error).lower()
    
    # Check for rate limits (common pattern across providers)
    if "rate" in error_message and "limit" in error_message:
        return ErrorCategory.RETRYABLE_WITH_BACKOFF
    if "429" in error_message:
        return ErrorCategory.RETRYABLE_WITH_BACKOFF
    
    # Check for authentication issues
    if "auth" in error_type or "401" in error_message or "403" in error_message:
        return ErrorCategory.NON_RETRYABLE
    
    # Check for timeouts and connection issues
    if "timeout" in error_type or "connection" in error_type:
        return ErrorCategory.RETRYABLE
    
    # Check for server errors (5xx)
    if any(code in error_message for code in ["500", "502", "503", "504"]):
        return ErrorCategory.RETRYABLE
    
    # Check for client errors (4xx) - generally not retryable
    if "400" in error_message or "bad request" in error_message:
        return ErrorCategory.NON_RETRYABLE
    
    # Default: assume retryable (fail open)
    return ErrorCategory.RETRYABLE
```

### Decision Tree

```
Error Occurred
     │
     ▼
Is it a client error (4xx)?
     │
     ├── Yes → Is it 429 (Rate Limit)?
     │           │
     │           ├── Yes → RETRY WITH BACKOFF
     │           └── No → DON'T RETRY (fix your request)
     │
     └── No → Is it a server error (5xx) or timeout?
               │
               ├── Yes → RETRY
               └── No → Is it a network error?
                         │
                         ├── Yes → RETRY
                         └── No → DON'T RETRY (unknown error)
```

---

## Exponential Backoff

### Why Not Just Retry Immediately?

Imagine 100 requests hit a rate limit at the same time. If they all retry after 1 second, you just created another spike of 100 requests. The server rejects them again. They all retry after 1 second. Repeat forever.

This is the **thundering herd** problem. The solution is to spread retries over time.

### The Formula

```
delay = min(base * (exp_base ^ attempt), max_delay)
```

Where:

- `base` = initial delay (e.g., 1 second)
- `exp_base` = exponential base (typically 2)
- `attempt` = attempt number (0-indexed)
- `max_delay` = cap on how long to wait

**Example with base=1, exp_base=2, max_delay=60:**

|Attempt|Calculation|Delay|
|---|---|---|
|0|1 × 2⁰ = 1|1s|
|1|1 × 2¹ = 2|2s|
|2|1 × 2² = 4|4s|
|3|1 × 2³ = 8|8s|
|4|1 × 2⁴ = 16|16s|
|5|1 × 2⁵ = 32|32s|
|6|1 × 2⁶ = 64|60s (capped)|

### Why It Works

1. **First retries are fast**: If it was just a brief hiccup, you recover quickly
2. **Later retries back off**: If the problem persists, you give the system time to recover
3. **Cap prevents absurdity**: You don't wait 17 minutes for the 10th retry

### Simple Implementation

```python
import time
import random

def exponential_backoff(
    attempt: int,
    base: float = 1.0,
    exp_base: float = 2.0,
    max_delay: float = 60.0
) -> float:
    """Calculate exponential backoff delay."""
    delay = base * (exp_base ** attempt)
    return min(delay, max_delay)

# Usage
for attempt in range(5):
    delay = exponential_backoff(attempt)
    print(f"Attempt {attempt}: wait {delay}s")
    time.sleep(delay)
    # ... try the operation
```

---

## Jitter: Solving the Remaining Problem

Exponential backoff helps, but it doesn't fully solve thundering herd. If 100 requests all start at the same time, they'll all calculate the same backoff delays and retry at the same times.

**Jitter** adds randomness to the delay, spreading retries across time.

### Types of Jitter

**1. Full Jitter (Recommended for Shared Resources)**

```
delay = random(0, base * 2^attempt)
```

The delay is a random value between 0 and the exponential backoff value. This provides maximum spread.

```python
import random

def full_jitter(
    attempt: int,
    base: float = 1.0,
    exp_base: float = 2.0,
    max_delay: float = 60.0
) -> float:
    """Full jitter: random delay up to exponential cap."""
    max_for_attempt = min(base * (exp_base ** attempt), max_delay)
    return random.uniform(0, max_for_attempt)
```

**2. Equal Jitter**

```
delay = (base * 2^attempt) / 2 + random(0, (base * 2^attempt) / 2)
```

The delay is half the exponential value plus a random component up to the other half. This guarantees at least some delay while still adding randomness.

```python
def equal_jitter(
    attempt: int,
    base: float = 1.0,
    exp_base: float = 2.0,
    max_delay: float = 60.0
) -> float:
    """Equal jitter: half fixed, half random."""
    exponential = min(base * (exp_base ** attempt), max_delay)
    half = exponential / 2
    return half + random.uniform(0, half)
```

**3. Decorrelated Jitter**

```
delay = random(base, previous_delay * 3)
```

Each delay is based on the previous delay, creating more variation across the retry sequence.

```python
def decorrelated_jitter(
    previous_delay: float,
    base: float = 1.0,
    max_delay: float = 60.0
) -> float:
    """Decorrelated jitter: each delay based on previous."""
    delay = random.uniform(base, previous_delay * 3)
    return min(delay, max_delay)
```

### Which Jitter Strategy to Use?

|Scenario|Strategy|Why|
|---|---|---|
|Shared resource contention (rate limits)|Full jitter|Maximum spread|
|External API that's temporarily down|Equal jitter|Guaranteed minimum wait|
|Mixed workload|Full jitter|Generally best default|

AWS's research (see their "Exponential Backoff and Jitter" blog post) found that **full jitter** performs best for shared resource contention, which is exactly what rate limits are.

---

## Retry Limits

Unbounded retries are dangerous. You need to stop at some point.

### Types of Limits

**1. Max Attempts**

Stop after N tries (including the initial attempt).

```python
MAX_ATTEMPTS = 5  # Initial + 4 retries

for attempt in range(MAX_ATTEMPTS):
    try:
        result = call_llm(prompt)
        break
    except RetryableError:
        if attempt == MAX_ATTEMPTS - 1:
            raise  # Final attempt failed
        time.sleep(exponential_backoff(attempt))
```

**2. Max Total Time**

Stop if total elapsed time exceeds a threshold.

```python
import time

MAX_TOTAL_SECONDS = 30
start_time = time.monotonic()

while True:
    try:
        result = call_llm(prompt)
        break
    except RetryableError:
        elapsed = time.monotonic() - start_time
        if elapsed >= MAX_TOTAL_SECONDS:
            raise TimeoutError(f"Operation timed out after {elapsed:.1f}s")
        
        # Don't sleep longer than remaining time
        delay = min(
            exponential_backoff(attempt),
            MAX_TOTAL_SECONDS - elapsed
        )
        time.sleep(delay)
```

**3. Budget-Aware Retry**

Stop if cost (tokens, money) would exceed budget.

```python
class BudgetAwareRetry:
    def __init__(self, max_tokens: int, cost_per_1k_tokens: float):
        self.max_tokens = max_tokens
        self.cost_per_1k = cost_per_1k_tokens
        self.tokens_used = 0
        self.max_cost = (max_tokens / 1000) * cost_per_1k_tokens
    
    def can_retry(self, estimated_tokens: int) -> bool:
        """Check if we have budget for another attempt."""
        projected_total = self.tokens_used + estimated_tokens
        return projected_total <= self.max_tokens
    
    def record_usage(self, tokens: int):
        """Record actual token usage."""
        self.tokens_used += tokens
    
    def remaining_budget(self) -> dict:
        return {
            "tokens": self.max_tokens - self.tokens_used,
            "cost": ((self.max_tokens - self.tokens_used) / 1000) * self.cost_per_1k
        }
```

### Recommended Defaults

|Context|Max Attempts|Max Time|Notes|
|---|---|---|---|
|User-facing request|3|10s|Users won't wait long|
|Background job|5|60s|Can be more patient|
|Critical operation|7|120s|Must succeed if possible|
|Fire-and-forget|3|5s|Best effort only|

---

## Idempotency: The Hidden Danger

Retries assume the operation can be safely repeated. This is called **idempotency**—doing something twice has the same effect as doing it once.

### LLM Calls Are Mostly Idempotent

Calling an LLM with the same prompt twice doesn't cause problems. You might get different outputs (non-determinism), but there are no side effects.

```python
# Safe to retry - no side effects
response = llm.invoke("Summarize this document...")

# If it times out and we retry, nothing bad happens
# We just get another summary attempt
```

### Tool Calls Might NOT Be Idempotent

When your agent uses tools, those tools might have side effects:

```python
# NOT SAFE to blindly retry!
# If this succeeds but we don't get the response, retrying sends two emails
send_email(to="user@example.com", subject="Your Order", body="...")

# NOT SAFE - might create duplicate records
create_user(name="John", email="john@example.com")

# NOT SAFE - might charge twice
charge_credit_card(amount=100.00, card_token="...")
```

### Idempotency Keys

The solution is **idempotency keys**—unique identifiers that let the system recognize duplicate requests.

```python
import uuid
from dataclasses import dataclass
from typing import Optional

@dataclass
class ToolCall:
    name: str
    arguments: dict
    idempotency_key: str  # Unique identifier for this specific call
    
    @classmethod
    def create(cls, name: str, arguments: dict, 
               key: Optional[str] = None) -> "ToolCall":
        return cls(
            name=name,
            arguments=arguments,
            idempotency_key=key or str(uuid.uuid4())
        )

class IdempotentToolExecutor:
    def __init__(self):
        self.executed_keys: dict[str, any] = {}  # key -> result
    
    def execute(self, tool_call: ToolCall) -> any:
        """Execute tool call with idempotency protection."""
        key = tool_call.idempotency_key
        
        # Check if we've already executed this exact call
        if key in self.executed_keys:
            return self.executed_keys[key]
        
        # Execute and cache result
        result = self._actually_execute(tool_call)
        self.executed_keys[key] = result
        return result
    
    def _actually_execute(self, tool_call: ToolCall) -> any:
        """Actually run the tool."""
        # ... tool execution logic
        pass
```

### Practical Pattern: Idempotency in Agent Tool Use

```python
class AgentToolHandler:
    def __init__(self):
        self.execution_cache: dict[str, any] = {}
    
    def generate_idempotency_key(
        self, 
        tool_name: str, 
        arguments: dict,
        conversation_id: str,
        turn_number: int
    ) -> str:
        """
        Generate deterministic key from tool call context.
        
        Same tool + same args + same conversation position = same key
        This means retries of the same logical operation are deduplicated.
        """
        import hashlib
        import json
        
        # Canonical representation
        key_data = {
            "tool": tool_name,
            "args": arguments,
            "conversation": conversation_id,
            "turn": turn_number
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    def execute_with_idempotency(
        self,
        tool_name: str,
        arguments: dict,
        conversation_id: str,
        turn_number: int
    ) -> any:
        key = self.generate_idempotency_key(
            tool_name, arguments, conversation_id, turn_number
        )
        
        if key in self.execution_cache:
            return {
                "result": self.execution_cache[key],
                "cached": True,
                "idempotency_key": key
            }
        
        result = self._execute_tool(tool_name, arguments)
        self.execution_cache[key] = result
        
        return {
            "result": result,
            "cached": False,
            "idempotency_key": key
        }
```

---

## Implementation with Tenacity

Tenacity is the standard Python library for retry logic. It's declarative, composable, and handles all the patterns we've discussed.

> **Doc reference**: Examples based on tenacity v9.x documentation (https://tenacity.readthedocs.io/ and https://github.com/jd/tenacity)

### Basic Retry

```python
from tenacity import retry

@retry
def unreliable_operation():
    """Retries forever until success. Don't do this in production!"""
    return call_external_api()
```

### Bounded Retries (What You Actually Want)

```python
from tenacity import (
    retry,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging

logger = logging.getLogger(__name__)

# Basic: Stop after 3 attempts
@retry(stop=stop_after_attempt(3))
def bounded_operation():
    return call_api()

# Time-bounded: Stop after 30 seconds total
@retry(stop=stop_after_delay(30))
def time_bounded_operation():
    return call_api()

# Combined: Stop after 5 attempts OR 30 seconds, whichever comes first
@retry(stop=(stop_after_attempt(5) | stop_after_delay(30)))
def combined_bounds():
    return call_api()
```

### Exponential Backoff

```python
from tenacity import retry, stop_after_attempt, wait_exponential

# wait_exponential parameters:
# - multiplier: base delay in seconds (default 1)
# - min: minimum delay (default 0)
# - max: maximum delay cap (default very large)
# - exp_base: exponential base (default 2)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=60)
)
def with_backoff():
    """
    Delays: ~1s, ~2s, ~4s, ~8s, capped at 60s
    
    Note: wait_exponential uses the formula:
    delay = multiplier * (exp_base ** attempt)
    clamped to [min, max]
    """
    return call_api()
```

### Full Jitter (Recommended for Shared Resources)

```python
from tenacity import retry, stop_after_attempt, wait_random_exponential

# wait_random_exponential implements AWS's "Full Jitter" algorithm
# Each retry waits a random time in [0, min(max, multiplier * 2^attempt)]

@retry(
    stop=stop_after_attempt(5),
    wait=wait_random_exponential(multiplier=1, max=60)
)
def with_full_jitter():
    """
    Random delay up to exponentially growing cap.
    Best for rate limit scenarios where many clients retry simultaneously.
    """
    return call_api()
```

### Combined Wait Strategies

```python
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random

# Fixed delay plus random jitter
# Guarantees at least 3s wait, plus up to 2s random
@retry(
    stop=stop_after_attempt(5),
    wait=wait_fixed(3) + wait_random(0, 2)
)
def fixed_plus_jitter():
    return call_api()
```

### Retry Only Specific Exceptions

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

# Define your retryable exceptions
class RetryableError(Exception):
    """Base class for errors that should trigger retry."""
    pass

class RateLimitError(RetryableError):
    pass

class TimeoutError(RetryableError):
    pass

class AuthenticationError(Exception):
    """Should NOT be retried."""
    pass

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, max=60),
    retry=retry_if_exception_type(RetryableError)
)
def selective_retry():
    """
    Only retries if a RetryableError (or subclass) is raised.
    AuthenticationError will propagate immediately.
    """
    try:
        response = requests.get("https://api.example.com/data", timeout=10)
        if response.status_code == 429:
            raise RateLimitError("Rate limited")
        elif response.status_code == 401:
            raise AuthenticationError("Invalid credentials")
        elif response.status_code >= 500:
            raise RetryableError(f"Server error: {response.status_code}")
        return response.json()
    except requests.Timeout:
        raise TimeoutError("Request timed out")
```

### Combining Multiple Retry Conditions

```python
from tenacity import (
    retry, 
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential
)

# Retry on exceptions OR on bad results
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, max=30),
    retry=(
        retry_if_exception_type((TimeoutError, ConnectionError)) |
        retry_if_result(lambda r: r is None or r.get("status") == "pending")
    )
)
def retry_on_exception_or_result():
    """
    Retries if:
    - TimeoutError or ConnectionError is raised, OR
    - Result is None, OR
    - Result has status "pending"
    """
    return call_api()
```

### Logging Retries

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    after_log
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.ERROR)
)
def logged_operation():
    """
    Logs before each retry sleep (WARNING level)
    Logs after final failure (ERROR level)
    """
    return call_api()
```

### Accessing Retry State

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))
def operation_with_state():
    return call_api()

# Get retry statistics after execution
try:
    result = operation_with_state()
except Exception as e:
    # Access retry statistics from the RetryError
    if hasattr(e, 'last_attempt'):
        print(f"Failed after {e.last_attempt.attempt_number} attempts")
        print(f"Total time: {e.last_attempt.outcome_timestamp - e.last_attempt.start_time:.2f}s")
```

### Async Support

```python
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))
async def async_operation():
    """
    Tenacity automatically handles async functions.
    Sleeps use asyncio.sleep() instead of time.sleep().
    """
    return await async_call_api()
```

---

## Complete Production Example

Here's a complete retry wrapper for LLM calls that incorporates all the patterns:

```python
"""
Production-ready LLM client with retry logic.

Doc references:
- tenacity v9.x: https://tenacity.readthedocs.io/
- Error classification based on common provider patterns
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Any
from tenacity import (
    retry,
    stop_after_attempt,
    stop_after_delay,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError
)

logger = logging.getLogger(__name__)


# === Exception Hierarchy ===

class LLMError(Exception):
    """Base exception for LLM operations."""
    pass

class RetryableLLMError(LLMError):
    """Errors that should trigger retry."""
    pass

class RateLimitError(RetryableLLMError):
    """Rate limit exceeded."""
    pass

class ServiceUnavailableError(RetryableLLMError):
    """Provider temporarily unavailable."""
    pass

class TimeoutError(RetryableLLMError):
    """Request timed out."""
    pass

class NonRetryableLLMError(LLMError):
    """Errors that should NOT trigger retry."""
    pass

class AuthenticationError(NonRetryableLLMError):
    """Invalid credentials."""
    pass

class InvalidRequestError(NonRetryableLLMError):
    """Malformed request."""
    pass

class ContentFilterError(NonRetryableLLMError):
    """Content blocked by safety filter."""
    pass


# === Configuration ===

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 5
    max_delay_seconds: float = 60.0
    max_total_seconds: float = 120.0
    multiplier: float = 1.0
    
    # Budget limits (optional)
    max_tokens: Optional[int] = None
    cost_per_1k_tokens: Optional[float] = None


# === Retry Context ===

@dataclass
class RetryContext:
    """Tracks retry state across attempts."""
    attempts: int = 0
    total_delay_seconds: float = 0.0
    tokens_used: int = 0
    errors: list = field(default_factory=list)
    start_time: float = field(default_factory=time.monotonic)
    
    def record_attempt(self, error: Optional[Exception] = None, 
                       tokens: int = 0, delay: float = 0.0):
        self.attempts += 1
        self.total_delay_seconds += delay
        self.tokens_used += tokens
        if error:
            self.errors.append({
                "attempt": self.attempts,
                "error": str(error),
                "type": type(error).__name__,
                "elapsed": time.monotonic() - self.start_time
            })
    
    def to_dict(self) -> dict:
        return {
            "attempts": self.attempts,
            "total_delay_seconds": round(self.total_delay_seconds, 2),
            "tokens_used": self.tokens_used,
            "total_time_seconds": round(time.monotonic() - self.start_time, 2),
            "errors": self.errors
        }


# === Retry Wrapper ===

class RetryableLLMClient:
    """
    Wrapper that adds retry logic to any LLM client.
    
    Usage:
        client = RetryableLLMClient(
            llm_call_fn=lambda prompt: openai_client.chat.completions.create(...),
            config=RetryConfig(max_attempts=5, max_delay_seconds=60)
        )
        result = client.call("Summarize this document...")
    """
    
    def __init__(
        self,
        llm_call_fn: Callable[[str], Any],
        config: RetryConfig = None,
        error_classifier: Callable[[Exception], type] = None
    ):
        self.llm_call_fn = llm_call_fn
        self.config = config or RetryConfig()
        self.error_classifier = error_classifier or self._default_classifier
    
    def _default_classifier(self, error: Exception) -> Exception:
        """
        Convert provider-specific errors to our exception hierarchy.
        Adapt this to your specific LLM providers.
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Rate limits
        if "rate" in error_str or "429" in error_str:
            return RateLimitError(str(error))
        
        # Timeouts
        if "timeout" in error_type or "timeout" in error_str:
            return TimeoutError(str(error))
        
        # Server errors
        if any(code in error_str for code in ["500", "502", "503", "504"]):
            return ServiceUnavailableError(str(error))
        
        # Authentication
        if "auth" in error_type or "401" in error_str or "403" in error_str:
            return AuthenticationError(str(error))
        
        # Invalid request
        if "400" in error_str or "invalid" in error_str:
            return InvalidRequestError(str(error))
        
        # Content filter
        if "content" in error_str and "filter" in error_str:
            return ContentFilterError(str(error))
        
        # Default: assume retryable
        return RetryableLLMError(str(error))
    
    def call(self, prompt: str) -> dict:
        """
        Call the LLM with automatic retry on transient failures.
        
        Returns:
            {
                "result": <LLM response>,
                "retry_info": {
                    "attempts": int,
                    "total_delay_seconds": float,
                    "tokens_used": int,
                    "total_time_seconds": float,
                    "errors": [...]
                }
            }
        """
        context = RetryContext()
        
        @retry(
            stop=(
                stop_after_attempt(self.config.max_attempts) |
                stop_after_delay(self.config.max_total_seconds)
            ),
            wait=wait_random_exponential(
                multiplier=self.config.multiplier,
                max=self.config.max_delay_seconds
            ),
            retry=retry_if_exception_type(RetryableLLMError),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def _call_with_retry():
            try:
                result = self.llm_call_fn(prompt)
                context.record_attempt()
                return result
            except Exception as e:
                # Classify and potentially re-raise as our exception type
                classified = self.error_classifier(e)
                context.record_attempt(error=classified)
                raise classified from e
        
        try:
            result = _call_with_retry()
            return {
                "result": result,
                "retry_info": context.to_dict(),
                "success": True
            }
        except RetryError as e:
            # All retries exhausted
            return {
                "result": None,
                "retry_info": context.to_dict(),
                "success": False,
                "final_error": str(e.last_attempt.exception())
            }
        except NonRetryableLLMError as e:
            # Non-retryable error - fail immediately
            return {
                "result": None,
                "retry_info": context.to_dict(),
                "success": False,
                "final_error": str(e)
            }
```

---

## Retry Context Propagation

For observability, you want to track retry behavior across your system.

### Include Retry Info in Response Metadata

```python
@dataclass
class LLMResponse:
    """Response with full retry context."""
    content: str
    retry_metadata: dict
    
    @property
    def required_retries(self) -> bool:
        return self.retry_metadata.get("attempts", 1) > 1

# Usage
response = client.call(prompt)
if response.required_retries:
    logger.warning(
        "LLM call required retries",
        extra={
            "attempts": response.retry_metadata["attempts"],
            "errors": response.retry_metadata["errors"]
        }
    )
```

### Alert on High Retry Rates

```python
from collections import deque
from dataclasses import dataclass, field
import time

@dataclass
class RetryRateMonitor:
    """Track retry rates and alert when threshold exceeded."""
    window_seconds: int = 300  # 5 minute window
    alert_threshold: float = 0.25  # Alert if >25% of calls require retry
    
    calls: deque = field(default_factory=lambda: deque())
    
    def record(self, required_retry: bool):
        now = time.time()
        self.calls.append({"time": now, "retry": required_retry})
        self._prune_old()
    
    def _prune_old(self):
        cutoff = time.time() - self.window_seconds
        while self.calls and self.calls[0]["time"] < cutoff:
            self.calls.popleft()
    
    def retry_rate(self) -> float:
        if not self.calls:
            return 0.0
        retry_count = sum(1 for c in self.calls if c["retry"])
        return retry_count / len(self.calls)
    
    def should_alert(self) -> bool:
        return self.retry_rate() > self.alert_threshold
    
    def get_status(self) -> dict:
        return {
            "retry_rate": round(self.retry_rate() * 100, 1),
            "calls_in_window": len(self.calls),
            "window_seconds": self.window_seconds,
            "alert_active": self.should_alert()
        }
```

---

## Summary

**When to retry:**

- Transient errors (timeouts, rate limits, 5xx) → Yes
- Persistent errors (auth failures, invalid input) → No
- Classify errors explicitly in your code

**How to retry:**

- Exponential backoff: `delay = base * 2^attempt`
- Add jitter to prevent thundering herd
- Use `wait_random_exponential` for rate limit scenarios

**When to stop:**

- Max attempts (3-5 typical)
- Max total time (don't retry forever)
- Budget exhausted (optional)

**Idempotency:**

- LLM calls are generally safe to retry
- Tool calls may not be—use idempotency keys

**Implementation:**

- Use tenacity library for declarative retry logic
- Track retry metrics for observability
- Alert on high retry rates

---

## Connections

- **Note 1**: Failure taxonomy tells you which errors to retry
- **Note 3**: Circuit breakers prevent retrying a dead service forever
- **Note 4**: When retries exhaust, fallback hierarchies provide graceful degradation