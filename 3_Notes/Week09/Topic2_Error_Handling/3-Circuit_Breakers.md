# Circuit Breakers for LLM APIs

## The Problem Retries Don't Solve

Retries handle transient failures—brief hiccups where the next attempt might succeed. But what happens when OpenAI's API is down for 10 minutes?

```
Request 1: Try → Fail → Retry → Fail → Retry → Fail (15 seconds wasted)
Request 2: Try → Fail → Retry → Fail → Retry → Fail (15 seconds wasted)
Request 3: Try → Fail → Retry → Fail → Retry → Fail (15 seconds wasted)
...
Request 1000: Try → Fail → Retry → Fail → Retry → Fail (15 seconds wasted)
```

Every request goes through the full retry cycle, burning:

- **Time**: 15+ seconds per request, guaranteed to fail
- **Money**: Tokens for partial responses, compute for retries
- **User patience**: They're waiting for something that can't succeed
- **Downstream capacity**: Your servers are tied up waiting on a dead service

Retries assume the problem is temporary and local. When the problem is systemic—the service is genuinely down—retries make everything worse.

### The Cascade Failure Risk

It gets worse. If your LLM service is down and every request is spending 15 seconds retrying:

1. Request threads pile up waiting
2. Your connection pool exhausts
3. Requests to _other_ services start timing out
4. Your entire system degrades because one dependency is down

This is a **cascade failure**. One broken service takes down everything that depends on it, and potentially everything that depends on _those_ services.

---

## The Circuit Breaker Pattern

The circuit breaker is a pattern from electrical engineering, applied to distributed systems. When current exceeds safe levels, the breaker trips and stops the flow—preventing fire.

In software: when a service fails too often, the circuit breaker trips and stops calling it—preventing cascade failures.

### The Three States

```
                    ┌─────────────────────────────────────────────┐
                    │                                             │
                    │  ┌─────────┐    failures     ┌─────────┐   │
                    │  │ CLOSED  │───exceed────────▶│  OPEN   │   │
                    │  │(normal) │   threshold      │ (fail   │   │
                    │  └────┬────┘                  │  fast)  │   │
                    │       │                       └────┬────┘   │
                    │       │                            │        │
                    │  success                     recovery       │
                    │  resets                      timeout        │
                    │  counter                     expires        │
                    │       │                            │        │
                    │       │      ┌───────────┐         │        │
                    │       └──────│ HALF-OPEN │◀────────┘        │
                    │              │  (test)   │                  │
                    │              └─────┬─────┘                  │
                    │                    │                        │
                    │         ┌──────────┼──────────┐             │
                    │         │          │          │             │
                    │    test fails   test succeeds               │
                    │         │          │                        │
                    │         ▼          ▼                        │
                    │      (back      (back to                    │
                    │      to OPEN)   CLOSED)                     │
                    │                                             │
                    └─────────────────────────────────────────────┘
```

**CLOSED (Normal Operation)**

- All requests go through to the service
- Failures are tracked in a sliding window
- If failures exceed threshold → transition to OPEN

**OPEN (Failing Fast)**

- Requests are rejected immediately without calling the service
- No waiting, no retries, instant failure
- After recovery timeout expires → transition to HALF-OPEN

**HALF-OPEN (Testing Recovery)**

- Limited requests are allowed through to test if service recovered
- If test requests succeed → transition to CLOSED
- If test requests fail → transition back to OPEN

### Why This Works

The circuit breaker provides **fast failure** and **automatic recovery**:

1. **Fast failure**: When the service is down, fail in milliseconds instead of seconds
2. **Load shedding**: Stop hammering a struggling service, give it time to recover
3. **Automatic recovery**: Periodically test if the service is back
4. **Isolation**: One bad service doesn't cascade to others

---

## State Transitions in Detail

### CLOSED → OPEN: Detecting Persistent Failure

The circuit trips when failures in a sliding window exceed a threshold.

```python
# Sliding window approach
# Track failures in the last N seconds (e.g., 60 seconds)
# If failures > threshold (e.g., 5), trip the circuit

failures_in_window = [
    {"time": 100.1, "error": "timeout"},
    {"time": 100.5, "error": "timeout"},
    {"time": 101.2, "error": "503"},
    {"time": 102.0, "error": "timeout"},
    {"time": 102.5, "error": "timeout"},  # 5th failure → TRIP
]
```

**Why sliding window, not simple counter?**

A simple counter ("trip after 5 failures") doesn't account for time. If you had 4 failures yesterday and 1 today, you probably shouldn't trip. The sliding window only counts recent failures.

### OPEN: Rejecting Requests

When open, the circuit immediately rejects requests:

```python
def call_service(request):
    if circuit.state == CircuitState.OPEN:
        raise CircuitOpenError(
            "Circuit is OPEN, service unavailable",
            time_until_retry=circuit.time_until_half_open()
        )
    # ... otherwise proceed with actual call
```

The caller gets an immediate, clear error. They can handle it (show error, use fallback) instead of waiting.

### OPEN → HALF-OPEN: Testing Recovery

After the recovery timeout (e.g., 30 seconds), the circuit transitions to HALF-OPEN:

```python
def can_execute(self) -> bool:
    if self.state == CircuitState.OPEN:
        # Check if recovery timeout has passed
        time_since_failure = time.time() - self.last_failure_time
        if time_since_failure > self.recovery_timeout:
            self.state = CircuitState.HALF_OPEN
            self.half_open_calls = 0
            return True  # Allow this request through
        return False  # Still in recovery period
    # ...
```

### HALF-OPEN: Limited Testing

In HALF-OPEN, we allow a limited number of requests through:

```python
def can_execute(self) -> bool:
    if self.state == CircuitState.HALF_OPEN:
        # Only allow N test requests
        if self.half_open_calls < self.half_open_max_calls:
            return True
        return False  # Too many test calls already in flight
    # ...
```

### HALF-OPEN → CLOSED: Recovery Confirmed

If test requests succeed, the service is back:

```python
def record_success(self):
    if self.state == CircuitState.HALF_OPEN:
        self.half_open_successes += 1
        # Require all test calls to succeed before closing
        if self.half_open_successes >= self.half_open_max_calls:
            self.state = CircuitState.CLOSED
            self.failures.clear()
            self.half_open_calls = 0
            self.half_open_successes = 0
```

### HALF-OPEN → OPEN: Still Failing

If any test request fails, back to OPEN with a fresh recovery timeout:

```python
def record_failure(self, error: Exception):
    if self.state == CircuitState.HALF_OPEN:
        # Single failure in half-open → back to open
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        self.half_open_calls = 0
        self.half_open_successes = 0
```

---

## Configuration Parameters

### Core Parameters

|Parameter|Description|Typical Value|Considerations|
|---|---|---|---|
|`failure_threshold`|Failures to trip circuit|5|Higher = more tolerant, slower to trip|
|`recovery_timeout`|Seconds before testing recovery|30|Lower = faster recovery detection, but more load on recovering service|
|`half_open_max_calls`|Test requests in half-open|3|Higher = more confidence before closing, but slower recovery|
|`window_size`|Sliding window duration (seconds)|60|Longer = more context, but slower to react|

### Tuning Guidelines

**For LLM APIs (external, shared):**

```python
LLM_CIRCUIT_CONFIG = {
    "failure_threshold": 5,      # Tolerate some failures (APIs can be flaky)
    "recovery_timeout": 30,      # Don't hammer, give time to recover
    "half_open_max_calls": 3,    # Test carefully before full load
    "window_size": 60            # 1-minute window
}
```

**For Vector Database (internal, critical):**

```python
VECTOR_DB_CIRCUIT_CONFIG = {
    "failure_threshold": 3,      # Less tolerant, DB should be reliable
    "recovery_timeout": 10,      # Check more frequently, it's internal
    "half_open_max_calls": 2,    # Quick verification
    "window_size": 30            # Shorter window, faster reaction
}
```

**For Embedding API (external, usually stable):**

```python
EMBEDDING_CIRCUIT_CONFIG = {
    "failure_threshold": 5,
    "recovery_timeout": 20,      # Usually recovers quickly
    "half_open_max_calls": 3,
    "window_size": 60
}
```

---

## Implementation

### Complete Circuit Breaker Class

```python
"""
Circuit Breaker implementation for LLM systems.

No external dependencies required—this is a pure Python implementation.
For production, consider thread safety and persistence requirements.
"""

import time
import threading
from enum import Enum
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Callable, Any


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5          # Failures to trip
    recovery_timeout: float = 30.0      # Seconds before testing recovery
    half_open_max_calls: int = 3        # Test calls in half-open
    window_size: float = 60.0           # Sliding window in seconds
    
    # Optional: different handling for different error types
    count_timeouts: bool = True
    count_rate_limits: bool = True      # Rate limits might not indicate "down"
    count_server_errors: bool = True


@dataclass
class CircuitStats:
    """Statistics for monitoring."""
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[float]
    last_state_change: float
    time_in_current_state: float
    calls_rejected: int


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascade failures.
    
    Usage:
        circuit = CircuitBreaker(name="openai-api")
        
        if circuit.can_execute():
            try:
                result = call_openai_api()
                circuit.record_success()
                return result
            except Exception as e:
                circuit.record_failure(e)
                raise
        else:
            raise CircuitOpenError("OpenAI circuit is open")
    """
    
    def __init__(
        self, 
        name: str,
        config: CircuitBreakerConfig = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State
        self._state = CircuitState.CLOSED
        self._last_state_change = time.time()
        
        # Failure tracking (sliding window)
        self._failures: deque = deque()  # timestamps of failures
        self._last_failure_time: Optional[float] = None
        
        # Half-open tracking
        self._half_open_calls = 0
        self._half_open_successes = 0
        
        # Statistics
        self._total_successes = 0
        self._total_failures = 0
        self._calls_rejected = 0
        
        # Thread safety
        self._lock = threading.RLock()
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        with self._lock:
            return self._state
    
    def can_execute(self) -> bool:
        """
        Check if a request should be allowed through.
        
        Returns:
            True if request can proceed, False if circuit is blocking
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._should_attempt_recovery():
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                
                self._calls_rejected += 1
                return False
            
            if self._state == CircuitState.HALF_OPEN:
                # Allow limited test calls
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            
            return False
    
    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._total_successes += 1
            
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                
                # Check if we've had enough successes to close
                if self._half_open_successes >= self.config.half_open_max_calls:
                    self._transition_to(CircuitState.CLOSED)
            
            elif self._state == CircuitState.CLOSED:
                # Prune old failures from window
                self._prune_old_failures()
    
    def record_failure(self, error: Exception = None) -> None:
        """Record a failed call."""
        with self._lock:
            now = time.time()
            self._total_failures += 1
            self._last_failure_time = now
            
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open → back to open
                self._transition_to(CircuitState.OPEN)
            
            elif self._state == CircuitState.CLOSED:
                # Record failure in sliding window
                self._failures.append(now)
                self._prune_old_failures()
                
                # Check if we should trip
                if len(self._failures) >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
    
    def _prune_old_failures(self) -> None:
        """Remove failures outside the sliding window."""
        cutoff = time.time() - self.config.window_size
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()
    
    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to test recovery."""
        if self._last_failure_time is None:
            return True
        time_since_failure = time.time() - self._last_failure_time
        return time_since_failure >= self.config.recovery_timeout
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        
        # Reset state-specific counters
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._half_open_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._failures.clear()
            self._half_open_calls = 0
            self._half_open_successes = 0
        
        # Log the transition (you'd want real logging here)
        self._log_transition(old_state, new_state)
    
    def _log_transition(
        self, 
        old_state: CircuitState, 
        new_state: CircuitState
    ) -> None:
        """Log state transitions for monitoring."""
        # In production, use proper logging
        print(f"[CircuitBreaker:{self.name}] {old_state.value} → {new_state.value}")
    
    def get_stats(self) -> CircuitStats:
        """Get current statistics for monitoring."""
        with self._lock:
            return CircuitStats(
                state=self._state,
                failure_count=len(self._failures),
                success_count=self._total_successes,
                last_failure_time=self._last_failure_time,
                last_state_change=self._last_state_change,
                time_in_current_state=time.time() - self._last_state_change,
                calls_rejected=self._calls_rejected
            )
    
    def time_until_half_open(self) -> Optional[float]:
        """Seconds until circuit will attempt recovery (if OPEN)."""
        with self._lock:
            if self._state != CircuitState.OPEN:
                return None
            if self._last_failure_time is None:
                return 0
            
            elapsed = time.time() - self._last_failure_time
            remaining = self.config.recovery_timeout - elapsed
            return max(0, remaining)
    
    def force_open(self) -> None:
        """Manually trip the circuit (for testing or manual intervention)."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            self._last_failure_time = time.time()
    
    def force_close(self) -> None:
        """Manually close the circuit (for testing or manual intervention)."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    
    def __init__(
        self, 
        message: str, 
        circuit_name: str = None,
        time_until_retry: float = None
    ):
        super().__init__(message)
        self.circuit_name = circuit_name
        self.time_until_retry = time_until_retry
```

### Using the Circuit Breaker

```python
# Create circuit breakers for each service
llm_circuit = CircuitBreaker(
    name="openai-api",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30,
        half_open_max_calls=3
    )
)

embedding_circuit = CircuitBreaker(
    name="embedding-api",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=20,
        half_open_max_calls=3
    )
)

vector_db_circuit = CircuitBreaker(
    name="vector-db",
    config=CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=10,
        half_open_max_calls=2
    )
)


def call_llm_with_circuit(prompt: str) -> str:
    """Call LLM with circuit breaker protection."""
    
    if not llm_circuit.can_execute():
        raise CircuitOpenError(
            f"LLM circuit is open, retry in {llm_circuit.time_until_half_open():.1f}s",
            circuit_name="openai-api",
            time_until_retry=llm_circuit.time_until_half_open()
        )
    
    try:
        response = call_openai_api(prompt)  # Your actual API call
        llm_circuit.record_success()
        return response
    except Exception as e:
        llm_circuit.record_failure(e)
        raise
```

### Decorator Pattern

For cleaner usage, wrap with a decorator:

```python
from functools import wraps
from typing import Callable

def with_circuit_breaker(circuit: CircuitBreaker):
    """Decorator that wraps a function with circuit breaker protection."""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not circuit.can_execute():
                raise CircuitOpenError(
                    f"Circuit '{circuit.name}' is open",
                    circuit_name=circuit.name,
                    time_until_retry=circuit.time_until_half_open()
                )
            
            try:
                result = func(*args, **kwargs)
                circuit.record_success()
                return result
            except Exception as e:
                circuit.record_failure(e)
                raise
        
        return wrapper
    return decorator


# Usage
@with_circuit_breaker(llm_circuit)
def generate_response(prompt: str) -> str:
    return call_openai_api(prompt)

@with_circuit_breaker(embedding_circuit)
def embed_text(text: str) -> list[float]:
    return call_embedding_api(text)

@with_circuit_breaker(vector_db_circuit)
def search_vectors(query_embedding: list[float]) -> list[dict]:
    return vector_db.search(query_embedding)
```

---

## Per-Service Circuit Breakers

A critical principle: **each service gets its own circuit breaker**.

### Why Separate Circuits?

If you have one global circuit breaker:

```
OpenAI API fails → Global circuit opens → 
  Embedding API blocked (even though it works!)
  Vector DB blocked (even though it works!)
  Everything fails!
```

With per-service circuits:

```
OpenAI API fails → OpenAI circuit opens →
  Embedding API still works (its circuit is closed)
  Vector DB still works (its circuit is closed)
  Partial functionality preserved!
```

### Service Registry Pattern

```python
from dataclasses import dataclass
from typing import Dict

@dataclass
class ServiceCircuits:
    """Registry of circuit breakers for all services."""
    
    circuits: Dict[str, CircuitBreaker] = None
    
    def __post_init__(self):
        if self.circuits is None:
            self.circuits = {}
    
    def register(
        self, 
        name: str, 
        config: CircuitBreakerConfig = None
    ) -> CircuitBreaker:
        """Register a new service circuit."""
        circuit = CircuitBreaker(name=name, config=config)
        self.circuits[name] = circuit
        return circuit
    
    def get(self, name: str) -> CircuitBreaker:
        """Get circuit by name."""
        if name not in self.circuits:
            raise KeyError(f"No circuit registered for service: {name}")
        return self.circuits[name]
    
    def get_all_stats(self) -> Dict[str, CircuitStats]:
        """Get stats for all circuits."""
        return {
            name: circuit.get_stats()
            for name, circuit in self.circuits.items()
        }
    
    def get_health_summary(self) -> Dict[str, str]:
        """Get simple health status for all services."""
        return {
            name: circuit.state.value
            for name, circuit in self.circuits.items()
        }
    
    def any_open(self) -> bool:
        """Check if any circuits are open."""
        return any(
            c.state == CircuitState.OPEN 
            for c in self.circuits.values()
        )


# Initialize service registry
service_circuits = ServiceCircuits()

# Register services with appropriate configs
service_circuits.register(
    "llm-primary",
    CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30)
)
service_circuits.register(
    "llm-fallback",
    CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30)
)
service_circuits.register(
    "embedding",
    CircuitBreakerConfig(failure_threshold=5, recovery_timeout=20)
)
service_circuits.register(
    "vector-db",
    CircuitBreakerConfig(failure_threshold=3, recovery_timeout=10)
)
service_circuits.register(
    "reranker",
    CircuitBreakerConfig(failure_threshold=5, recovery_timeout=15)
)


# Usage
def rag_query(query: str) -> dict:
    """Execute RAG query with per-service circuit breakers."""
    
    # Check health before starting
    health = service_circuits.get_health_summary()
    
    # Embedding
    embedding_circuit = service_circuits.get("embedding")
    if not embedding_circuit.can_execute():
        return {"error": "Embedding service unavailable", "health": health}
    
    try:
        query_embedding = embed(query)
        embedding_circuit.record_success()
    except Exception as e:
        embedding_circuit.record_failure(e)
        return {"error": f"Embedding failed: {e}", "health": health}
    
    # Vector search
    vector_circuit = service_circuits.get("vector-db")
    if not vector_circuit.can_execute():
        return {"error": "Vector DB unavailable", "health": health}
    
    try:
        results = search(query_embedding)
        vector_circuit.record_success()
    except Exception as e:
        vector_circuit.record_failure(e)
        return {"error": f"Search failed: {e}", "health": health}
    
    # LLM generation (with fallback)
    llm_primary = service_circuits.get("llm-primary")
    llm_fallback = service_circuits.get("llm-fallback")
    
    if llm_primary.can_execute():
        try:
            response = generate_primary(query, results)
            llm_primary.record_success()
            return {"response": response, "source": "primary", "health": health}
        except Exception as e:
            llm_primary.record_failure(e)
            # Fall through to fallback
    
    if llm_fallback.can_execute():
        try:
            response = generate_fallback(query, results)
            llm_fallback.record_success()
            return {"response": response, "source": "fallback", "health": health}
        except Exception as e:
            llm_fallback.record_failure(e)
    
    return {"error": "All LLM services unavailable", "health": health}
```

---

## Circuit Breaker + Retry Interaction

Two valid patterns exist. Choose based on your needs.

### Pattern 1: Retry Inside Circuit

Retries happen, then circuit evaluates the final result.

```
Request → Circuit Check → [Retry 1 → Retry 2 → Retry 3] → Success/Failure → Record
```

```python
@with_circuit_breaker(llm_circuit)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception_type(RetryableError)
)
def call_llm_with_retry_inside(prompt: str) -> str:
    """
    Circuit wraps retry.
    
    - Retry handles transient failures
    - Circuit trips only after retries exhausted
    - One "failure" from circuit's perspective = all retries failed
    """
    return call_openai_api(prompt)
```

**When to use:**

- You want the circuit to trip only after retries are exhausted
- Transient errors (handled by retry) shouldn't count toward circuit threshold
- Most common pattern

### Pattern 2: Circuit Inside Retry

Each retry attempt checks the circuit first.

```
Retry 1 → Circuit Check → Try
Retry 2 → Circuit Check → Try (or fail fast if open)
Retry 3 → Circuit Check → Try (or fail fast if open)
```

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception_type((RetryableError, CircuitOpenError))
)
@with_circuit_breaker(llm_circuit)
def call_llm_with_circuit_inside(prompt: str) -> str:
    """
    Retry wraps circuit.
    
    - Each retry checks circuit first
    - If circuit opens mid-retry, subsequent attempts fail fast
    - Useful when circuit might open during retry sequence
    """
    return call_openai_api(prompt)
```

**When to use:**

- You want to stop retrying immediately if the circuit opens
- Useful for very slow failures where circuit might open during retry sequence

### Recommended: Retry Inside Circuit

For most LLM applications, **retry inside circuit** is the right choice:

```python
from tenacity import (
    retry, stop_after_attempt, wait_random_exponential,
    retry_if_exception_type
)

class ProtectedLLMClient:
    """LLM client with both retry and circuit breaker protection."""
    
    def __init__(self, circuit: CircuitBreaker):
        self.circuit = circuit
    
    def call(self, prompt: str) -> str:
        """
        Call with circuit breaker wrapping retry logic.
        
        Flow:
        1. Check circuit
        2. If open, fail fast
        3. If closed/half-open, attempt with retries
        4. Record final success/failure to circuit
        """
        if not self.circuit.can_execute():
            raise CircuitOpenError(
                f"Circuit '{self.circuit.name}' is open",
                circuit_name=self.circuit.name,
                time_until_retry=self.circuit.time_until_half_open()
            )
        
        try:
            result = self._call_with_retry(prompt)
            self.circuit.record_success()
            return result
        except Exception as e:
            self.circuit.record_failure(e)
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, max=30),
        retry=retry_if_exception_type(RetryableError),
        reraise=True
    )
    def _call_with_retry(self, prompt: str) -> str:
        """Internal method with retry logic."""
        return self._raw_call(prompt)
    
    def _raw_call(self, prompt: str) -> str:
        """Actual API call—implement based on your provider."""
        # Your OpenAI/Anthropic/etc call here
        pass
```

---

## Monitoring Circuit State

Circuits are only useful if you know what's happening. Monitor aggressively.

### Structured Logging

```python
import logging
import json
from datetime import datetime

logger = logging.getLogger("circuit_breaker")

class ObservableCircuitBreaker(CircuitBreaker):
    """Circuit breaker with enhanced observability."""
    
    def _log_transition(
        self, 
        old_state: CircuitState, 
        new_state: CircuitState
    ) -> None:
        """Log state transitions as structured events."""
        event = {
            "event": "circuit_state_change",
            "circuit": self.name,
            "old_state": old_state.value,
            "new_state": new_state.value,
            "timestamp": datetime.utcnow().isoformat(),
            "failure_count": len(self._failures),
            "time_in_old_state": time.time() - self._last_state_change
        }
        
        if new_state == CircuitState.OPEN:
            logger.warning(json.dumps(event))
            # Trigger alert!
            self._send_alert(event)
        else:
            logger.info(json.dumps(event))
    
    def _send_alert(self, event: dict) -> None:
        """Send alert when circuit opens."""
        # Integration with PagerDuty, Slack, etc.
        # In production, make this async/non-blocking
        pass
    
    def record_success(self) -> None:
        """Record success with metrics."""
        super().record_success()
        self._emit_metric("circuit_call_success", 1, {"circuit": self.name})
    
    def record_failure(self, error: Exception = None) -> None:
        """Record failure with metrics."""
        super().record_failure(error)
        self._emit_metric("circuit_call_failure", 1, {
            "circuit": self.name,
            "error_type": type(error).__name__ if error else "unknown"
        })
        
        if self._state == CircuitState.OPEN:
            self._emit_metric("circuit_open", 1, {"circuit": self.name})
    
    def _emit_metric(self, name: str, value: float, tags: dict) -> None:
        """Emit metric to your monitoring system."""
        # Integration with Prometheus, DataDog, etc.
        pass
```

### Health Endpoint

Expose circuit health for monitoring systems:

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/health/circuits")
def circuit_health():
    """Health check endpoint for circuit breakers."""
    stats = {}
    overall_healthy = True
    
    for name, circuit in service_circuits.circuits.items():
        circuit_stats = circuit.get_stats()
        stats[name] = {
            "state": circuit_stats.state.value,
            "failures_in_window": circuit_stats.failure_count,
            "time_in_state_seconds": round(circuit_stats.time_in_current_state, 1),
            "calls_rejected": circuit_stats.calls_rejected
        }
        
        if circuit_stats.state == CircuitState.OPEN:
            overall_healthy = False
            stats[name]["time_until_retry"] = circuit.time_until_half_open()
    
    return jsonify({
        "healthy": overall_healthy,
        "circuits": stats,
        "timestamp": datetime.utcnow().isoformat()
    })
```

### Dashboard Metrics

Key metrics to track:

|Metric|Description|Alert Threshold|
|---|---|---|
|`circuit_state`|Current state (0=closed, 1=half-open, 2=open)|Alert if open|
|`circuit_failures_total`|Total failures recorded|Spike detection|
|`circuit_calls_rejected`|Calls rejected due to open circuit|Any non-zero|
|`circuit_recovery_time`|Time spent in open state before recovery|> 5 minutes|
|`circuit_trip_count`|Number of times circuit has tripped|High frequency = investigate|

```python
# Example Prometheus metrics (pseudo-code)
circuit_state_gauge = Gauge(
    'circuit_breaker_state',
    'Current state of circuit breaker',
    ['circuit_name']
)

circuit_failures_counter = Counter(
    'circuit_breaker_failures_total',
    'Total failures recorded by circuit',
    ['circuit_name', 'error_type']
)

circuit_rejections_counter = Counter(
    'circuit_breaker_rejections_total',
    'Calls rejected due to open circuit',
    ['circuit_name']
)

def update_metrics(circuit: CircuitBreaker):
    """Update Prometheus metrics for a circuit."""
    stats = circuit.get_stats()
    
    state_value = {
        CircuitState.CLOSED: 0,
        CircuitState.HALF_OPEN: 1,
        CircuitState.OPEN: 2
    }[stats.state]
    
    circuit_state_gauge.labels(circuit_name=circuit.name).set(state_value)
```

---

## Summary

**The problem:**

- Retries don't help when a service is persistently down
- Continued retries waste resources and can cause cascades

**The circuit breaker pattern:**

- CLOSED: Normal operation, track failures
- OPEN: Fail fast, don't call the failing service
- HALF-OPEN: Test if service has recovered

**Configuration:**

- `failure_threshold`: How many failures before tripping (5 typical)
- `recovery_timeout`: How long before testing recovery (30s typical)
- `half_open_max_calls`: Test requests before closing (3 typical)

**Key principles:**

- Separate circuit per service (isolation)
- Retry inside circuit (most common pattern)
- Monitor and alert on state changes

**Integration with retries:**

- Retries handle transient failures
- Circuit breaker handles persistent outages
- Together they provide comprehensive resilience

---

## Connections

- **Note 1**: Failure taxonomy defines which errors circuit breaker should count
- **Note 2**: Retry logic works inside the circuit breaker
- **Note 4**: When circuit is open, fallback hierarchy takes over
- **Week 8**: LLMOps will connect circuit metrics to broader observability