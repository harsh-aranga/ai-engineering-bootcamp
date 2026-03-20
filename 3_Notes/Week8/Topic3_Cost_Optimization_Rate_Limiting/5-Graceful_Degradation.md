# Note 5: Graceful Degradation — Surviving Traffic Spikes and Budget Limits

## The Problem: Limits Hit, Now What?

You've implemented rate limiting (Note 4). A user hits their limit. What happens next?

**Option A: Hard Reject**

```
User: "Summarize this document for me"
System: "Error 429: Rate limit exceeded. Try again in 3600 seconds."
User: *closes app, never returns*
```

**Option B: Graceful Degradation**

```
User: "Summarize this document for me"
System: *uses cheaper model, shorter output*
System: "Here's a brief summary. We're experiencing high demand, 
        so I've provided a condensed version."
User: *gets value, understands the situation, continues using app*
```

Graceful degradation means: when you can't give users everything, give them something useful. Reduced functionality beats no functionality.

---

## Degradation Levels

Think of degradation as a spectrum, not a binary switch.

```
┌──────────────────────────────────────────────────────────────┐
│ NORMAL                                                       │
│ - All models available                                       │
│ - Full output lengths                                        │
│ - All features enabled                                       │
│ - No restrictions                                            │
└──────────────────────────────────────────────────────────────┘
                              ↓ (80% budget used)
┌──────────────────────────────────────────────────────────────┐
│ REDUCED                                                      │
│ - Cheaper models only (gpt-4o-mini, haiku)                   │
│ - Shorter max_output_tokens                                  │
│ - Fewer RAG chunks                                           │
│ - Features still work, just constrained                      │
└──────────────────────────────────────────────────────────────┘
                              ↓ (95% budget used)
┌──────────────────────────────────────────────────────────────┐
│ MINIMAL                                                      │
│ - Essential operations only                                  │
│ - Cache-first (prefer cached responses)                      │
│ - Very short outputs                                         │
│ - Some features disabled                                     │
└──────────────────────────────────────────────────────────────┘
                              ↓ (budget exhausted / emergency)
┌──────────────────────────────────────────────────────────────┐
│ EMERGENCY                                                    │
│ - Reject non-critical requests                               │
│ - Serve only cached responses                                │
│ - No new LLM calls                                           │
│ - System survival mode                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## Implementing Degradation Levels

```python
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List
import time

class DegradationLevel(Enum):
    """System degradation levels, from best to worst."""
    NORMAL = auto()      # Full functionality
    REDUCED = auto()     # Cheaper models, shorter outputs
    MINIMAL = auto()     # Essential only, cache-first
    EMERGENCY = auto()   # No new LLM calls, cached only


@dataclass
class DegradationConfig:
    """Configuration for a degradation level."""
    level: DegradationLevel
    
    # Model restrictions
    allowed_models: List[str]
    default_model: str
    
    # Output restrictions
    max_output_tokens: int
    max_rag_chunks: int
    
    # Behavior flags
    cache_first: bool = False          # Check cache before LLM
    cache_only: bool = False           # Never call LLM, cache or reject
    reject_non_critical: bool = False  # Reject non-essential requests
    
    # User messaging
    user_message: Optional[str] = None


# Define configurations for each level
DEGRADATION_CONFIGS = {
    DegradationLevel.NORMAL: DegradationConfig(
        level=DegradationLevel.NORMAL,
        allowed_models=["gpt-4o", "gpt-4o-mini", "claude-sonnet-4-6", "claude-haiku-4-5"],
        default_model="gpt-4o-mini",
        max_output_tokens=4000,
        max_rag_chunks=10,
        cache_first=False,
        user_message=None,
    ),
    
    DegradationLevel.REDUCED: DegradationConfig(
        level=DegradationLevel.REDUCED,
        allowed_models=["gpt-4o-mini", "claude-haiku-4-5"],  # Cheap models only
        default_model="gpt-4o-mini",
        max_output_tokens=1000,  # Shorter outputs
        max_rag_chunks=5,        # Fewer chunks
        cache_first=True,        # Check cache first
        user_message="We're experiencing high demand. Responses may be shorter than usual.",
    ),
    
    DegradationLevel.MINIMAL: DegradationConfig(
        level=DegradationLevel.MINIMAL,
        allowed_models=["gpt-4o-mini"],  # Single cheapest model
        default_model="gpt-4o-mini",
        max_output_tokens=300,   # Very short
        max_rag_chunks=3,        # Minimal context
        cache_first=True,
        reject_non_critical=True,  # Reject nice-to-have features
        user_message="System is under heavy load. Providing condensed responses only.",
    ),
    
    DegradationLevel.EMERGENCY: DegradationConfig(
        level=DegradationLevel.EMERGENCY,
        allowed_models=[],       # No models allowed
        default_model="",
        max_output_tokens=0,
        max_rag_chunks=0,
        cache_first=True,
        cache_only=True,         # Only serve cached responses
        reject_non_critical=True,
        user_message="System is in emergency mode. Only cached responses available.",
    ),
}


def get_config(level: DegradationLevel) -> DegradationConfig:
    """Get configuration for a degradation level."""
    return DEGRADATION_CONFIGS[level]
```

---

## The Degradation Manager

Central controller that tracks system state and enforces degradation.

```python
import threading
from datetime import datetime
from typing import Callable, Optional
from dataclasses import dataclass

@dataclass
class DegradationState:
    """Current state of the degradation system."""
    level: DegradationLevel
    reason: str
    triggered_at: float
    triggered_by: str  # "automatic" or "manual"
    

class DegradationManager:
    """
    Manages system degradation levels.
    
    Responsibilities:
    - Track current degradation level
    - Evaluate trigger conditions
    - Handle transitions between levels
    - Prevent flapping (hysteresis)
    """
    
    def __init__(
        self,
        # Cost thresholds (as fraction of daily limit)
        reduced_threshold: float = 0.80,   # 80% → REDUCED
        minimal_threshold: float = 0.95,   # 95% → MINIMAL
        emergency_threshold: float = 1.0,  # 100% → EMERGENCY
        
        # Recovery settings
        recovery_buffer: float = 0.10,     # Need 10% headroom to recover
        min_time_in_level: float = 60.0,   # Minimum 60s before changing
    ):
        self.reduced_threshold = reduced_threshold
        self.minimal_threshold = minimal_threshold
        self.emergency_threshold = emergency_threshold
        self.recovery_buffer = recovery_buffer
        self.min_time_in_level = min_time_in_level
        
        # Current state
        self._state = DegradationState(
            level=DegradationLevel.NORMAL,
            reason="System startup",
            triggered_at=time.time(),
            triggered_by="automatic",
        )
        
        self._lock = threading.Lock()
        self._manual_override: Optional[DegradationLevel] = None
    
    @property
    def current_level(self) -> DegradationLevel:
        """Get current degradation level."""
        with self._lock:
            if self._manual_override:
                return self._manual_override
            return self._state.level
    
    @property
    def config(self) -> DegradationConfig:
        """Get configuration for current level."""
        return get_config(self.current_level)
    
    def evaluate_conditions(
        self,
        cost_ratio: float,           # Current cost / daily limit
        error_rate: float = 0.0,     # Recent error rate (0-1)
        avg_latency_ms: float = 0.0, # Recent average latency
        latency_threshold_ms: float = 5000.0,
    ) -> DegradationLevel:
        """
        Evaluate current conditions and determine appropriate level.
        
        Does NOT change state—just returns what level should be.
        """
        # Emergency: budget exhausted or extreme conditions
        if cost_ratio >= self.emergency_threshold:
            return DegradationLevel.EMERGENCY
        
        if error_rate > 0.50:  # >50% errors
            return DegradationLevel.EMERGENCY
        
        # Minimal: near budget limit or high errors
        if cost_ratio >= self.minimal_threshold:
            return DegradationLevel.MINIMAL
        
        if error_rate > 0.20:  # >20% errors
            return DegradationLevel.MINIMAL
        
        if avg_latency_ms > latency_threshold_ms * 2:  # 2x threshold
            return DegradationLevel.MINIMAL
        
        # Reduced: approaching limits
        if cost_ratio >= self.reduced_threshold:
            return DegradationLevel.REDUCED
        
        if error_rate > 0.05:  # >5% errors
            return DegradationLevel.REDUCED
        
        if avg_latency_ms > latency_threshold_ms:
            return DegradationLevel.REDUCED
        
        # Normal: all good
        return DegradationLevel.NORMAL
    
    def update(
        self,
        cost_ratio: float,
        error_rate: float = 0.0,
        avg_latency_ms: float = 0.0,
    ) -> tuple[DegradationLevel, bool]:
        """
        Update degradation level based on current conditions.
        
        Returns:
            Tuple of (new_level, did_change)
        """
        with self._lock:
            # Don't change if manual override is active
            if self._manual_override:
                return self._manual_override, False
            
            # Determine target level
            target_level = self.evaluate_conditions(
                cost_ratio=cost_ratio,
                error_rate=error_rate,
                avg_latency_ms=avg_latency_ms,
            )
            
            current = self._state.level
            
            # No change needed
            if target_level == current:
                return current, False
            
            # Check minimum time in current level (prevent flapping)
            time_in_current = time.time() - self._state.triggered_at
            if time_in_current < self.min_time_in_level:
                return current, False
            
            # Degrading (getting worse) - allow immediately
            if target_level.value > current.value:
                self._transition_to(target_level, f"Automatic: conditions degraded")
                return target_level, True
            
            # Recovering (getting better) - apply hysteresis
            # Only recover if we have buffer room
            recovery_allowed = self._check_recovery_allowed(
                cost_ratio=cost_ratio,
                target_level=target_level,
            )
            
            if recovery_allowed:
                # Recover one level at a time, not all the way
                next_level = DegradationLevel(current.value - 1)
                self._transition_to(next_level, f"Automatic: conditions improved")
                return next_level, True
            
            return current, False
    
    def _check_recovery_allowed(
        self,
        cost_ratio: float,
        target_level: DegradationLevel,
    ) -> bool:
        """
        Check if recovery is allowed.
        
        Implements hysteresis: need buffer room to recover,
        preventing flapping at threshold boundaries.
        """
        if target_level == DegradationLevel.NORMAL:
            # To recover to NORMAL, need to be below reduced threshold minus buffer
            return cost_ratio < (self.reduced_threshold - self.recovery_buffer)
        
        if target_level == DegradationLevel.REDUCED:
            # To recover to REDUCED, need to be below minimal threshold minus buffer
            return cost_ratio < (self.minimal_threshold - self.recovery_buffer)
        
        if target_level == DegradationLevel.MINIMAL:
            # To recover to MINIMAL, need to be below emergency threshold minus buffer
            return cost_ratio < (self.emergency_threshold - self.recovery_buffer)
        
        return False
    
    def _transition_to(self, level: DegradationLevel, reason: str) -> None:
        """Transition to a new level."""
        old_level = self._state.level
        self._state = DegradationState(
            level=level,
            reason=reason,
            triggered_at=time.time(),
            triggered_by="automatic",
        )
        
        # Log the transition
        direction = "↓ DEGRADED" if level.value > old_level.value else "↑ RECOVERED"
        print(f"[DEGRADATION] {direction}: {old_level.name} → {level.name}")
        print(f"              Reason: {reason}")
    
    def set_manual_override(
        self,
        level: DegradationLevel,
        reason: str = "Manual override",
    ) -> None:
        """
        Manually set degradation level.
        
        Use for:
        - Known incidents
        - Scheduled degradation (end of billing period)
        - Testing
        """
        with self._lock:
            self._manual_override = level
            self._state = DegradationState(
                level=level,
                reason=reason,
                triggered_at=time.time(),
                triggered_by="manual",
            )
            print(f"[DEGRADATION] MANUAL OVERRIDE: {level.name}")
            print(f"              Reason: {reason}")
    
    def clear_manual_override(self) -> None:
        """Clear manual override, return to automatic control."""
        with self._lock:
            self._manual_override = None
            print("[DEGRADATION] Manual override cleared")
    
    def get_status(self) -> dict:
        """Get current degradation status."""
        with self._lock:
            return {
                "level": self._state.level.name,
                "reason": self._state.reason,
                "triggered_at": datetime.fromtimestamp(self._state.triggered_at).isoformat(),
                "triggered_by": self._state.triggered_by,
                "manual_override_active": self._manual_override is not None,
                "config": {
                    "allowed_models": self.config.allowed_models,
                    "max_output_tokens": self.config.max_output_tokens,
                    "cache_first": self.config.cache_first,
                    "cache_only": self.config.cache_only,
                },
            }
```

---

## Degradation-Aware Request Handler

Integrates degradation into the request flow.

```python
from typing import Optional, Tuple
from dataclasses import dataclass

@dataclass
class DegradedResponse:
    """Response that may be degraded."""
    content: str
    model_used: str
    degradation_level: DegradationLevel
    from_cache: bool
    user_notice: Optional[str]
    was_rejected: bool = False
    reject_reason: Optional[str] = None


class DegradationAwareHandler:
    """
    Request handler that respects degradation levels.
    
    Integrates:
    - Model selection based on degradation
    - Output token limits
    - Cache-first behavior
    - Request rejection for non-critical
    """
    
    def __init__(
        self,
        degradation_manager: DegradationManager,
        llm_client,  # Your LLM client
        cache,       # Your response cache
    ):
        self.degradation = degradation_manager
        self.client = llm_client
        self.cache = cache
    
    def handle_request(
        self,
        prompt: str,
        requested_model: str,
        is_critical: bool = False,
        cache_key: Optional[str] = None,
    ) -> DegradedResponse:
        """
        Handle a request with degradation awareness.
        
        Args:
            prompt: The user's prompt
            requested_model: Model the user/system requested
            is_critical: Whether this request is critical (not rejectable)
            cache_key: Key for caching (if cacheable)
        """
        config = self.degradation.config
        level = self.degradation.current_level
        
        # Step 1: Check if we should reject non-critical requests
        if config.reject_non_critical and not is_critical:
            return DegradedResponse(
                content="",
                model_used="",
                degradation_level=level,
                from_cache=False,
                user_notice=config.user_message,
                was_rejected=True,
                reject_reason="System is degraded. Non-critical requests are paused.",
            )
        
        # Step 2: Check cache first if configured
        if config.cache_first and cache_key:
            cached = self.cache.get(cache_key)
            if cached:
                return DegradedResponse(
                    content=cached,
                    model_used="cache",
                    degradation_level=level,
                    from_cache=True,
                    user_notice=config.user_message,
                )
        
        # Step 3: If cache-only mode, reject if not in cache
        if config.cache_only:
            return DegradedResponse(
                content="",
                model_used="",
                degradation_level=level,
                from_cache=False,
                user_notice=config.user_message,
                was_rejected=True,
                reject_reason="System is in emergency mode. Only cached responses available.",
            )
        
        # Step 4: Select model based on degradation
        model = self._select_model(requested_model, config)
        
        # Step 5: Apply output token limit
        max_tokens = config.max_output_tokens
        
        # Step 6: Make the LLM call
        response = self._call_llm(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
        )
        
        # Step 7: Cache the response if appropriate
        if cache_key and response:
            self.cache.set(cache_key, response)
        
        return DegradedResponse(
            content=response,
            model_used=model,
            degradation_level=level,
            from_cache=False,
            user_notice=config.user_message,
        )
    
    def _select_model(
        self,
        requested: str,
        config: DegradationConfig,
    ) -> str:
        """Select model based on degradation constraints."""
        # If requested model is allowed, use it
        if requested in config.allowed_models:
            return requested
        
        # Otherwise, use the default for this level
        if config.default_model:
            return config.default_model
        
        # Fallback: first allowed model
        if config.allowed_models:
            return config.allowed_models[0]
        
        raise ValueError("No models available at current degradation level")
    
    def _call_llm(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
    ) -> str:
        """Make the actual LLM call."""
        # This would use your actual LLM client
        # Using placeholder for illustration
        response = self.client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=max_tokens,
        )
        return response.output_text


# Usage example showing degradation in action
"""
# Normal operation
handler.handle_request(
    prompt="Explain quantum computing in detail",
    requested_model="gpt-4o",
    is_critical=False,
)
# → Uses gpt-4o, 4000 max tokens, no notice

# System enters REDUCED mode (80% budget used)
handler.handle_request(
    prompt="Explain quantum computing in detail",
    requested_model="gpt-4o",  # User requests expensive model
    is_critical=False,
)
# → Uses gpt-4o-mini (downgraded), 1000 max tokens
# → User notice: "We're experiencing high demand..."

# System enters MINIMAL mode (95% budget used)
handler.handle_request(
    prompt="Check my order status",
    requested_model="gpt-4o",
    is_critical=False,
)
# → Rejected: "System is under heavy load"

handler.handle_request(
    prompt="Check my order status",
    requested_model="gpt-4o",
    is_critical=True,  # Critical request
)
# → Uses gpt-4o-mini, 300 max tokens, serves despite degradation

# System enters EMERGENCY mode (budget exhausted)
handler.handle_request(
    prompt="Anything",
    requested_model="gpt-4o",
    is_critical=True,
)
# → Only serves from cache, no LLM calls
"""
```

---

## Automatic Degradation Triggers

The degradation manager needs metrics to make decisions. Here's how to feed them.

```python
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque
import threading

@dataclass
class MetricsWindow:
    """Sliding window for metrics."""
    window_seconds: int = 300  # 5-minute window
    timestamps: Deque[float] = field(default_factory=deque)
    values: Deque[float] = field(default_factory=deque)
    
    def add(self, value: float) -> None:
        now = time.time()
        self.timestamps.append(now)
        self.values.append(value)
        self._cleanup()
    
    def _cleanup(self) -> None:
        cutoff = time.time() - self.window_seconds
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()
            self.values.popleft()
    
    def average(self) -> float:
        self._cleanup()
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)
    
    def rate(self) -> float:
        """Get rate of events with value=1 (for error rate, etc.)"""
        self._cleanup()
        if not self.values:
            return 0.0
        return sum(1 for v in self.values if v > 0) / len(self.values)


class DegradationMetrics:
    """
    Collect metrics that trigger degradation.
    
    Tracks:
    - Cost accumulation
    - Error rates
    - Latency
    """
    
    def __init__(
        self,
        daily_budget: float = 100.0,
        window_seconds: int = 300,  # 5-minute windows
    ):
        self.daily_budget = daily_budget
        
        # Cost tracking
        self.daily_cost = 0.0
        self.cost_reset_date = self._get_date_key()
        
        # Error tracking (1 = error, 0 = success)
        self.errors = MetricsWindow(window_seconds)
        
        # Latency tracking (milliseconds)
        self.latencies = MetricsWindow(window_seconds)
        
        self._lock = threading.Lock()
    
    def _get_date_key(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
    
    def _maybe_reset_daily(self) -> None:
        """Reset daily counters if new day."""
        today = self._get_date_key()
        if today != self.cost_reset_date:
            self.daily_cost = 0.0
            self.cost_reset_date = today
    
    def record_request(
        self,
        cost: float,
        latency_ms: float,
        success: bool,
    ) -> None:
        """Record metrics for a completed request."""
        with self._lock:
            self._maybe_reset_daily()
            
            self.daily_cost += cost
            self.latencies.add(latency_ms)
            self.errors.add(0.0 if success else 1.0)
    
    def get_cost_ratio(self) -> float:
        """Get current cost as ratio of daily budget."""
        with self._lock:
            self._maybe_reset_daily()
            return self.daily_cost / self.daily_budget
    
    def get_error_rate(self) -> float:
        """Get recent error rate (0-1)."""
        with self._lock:
            return self.errors.rate()
    
    def get_avg_latency(self) -> float:
        """Get recent average latency in ms."""
        with self._lock:
            return self.latencies.average()
    
    def get_all_metrics(self) -> dict:
        """Get all current metrics."""
        with self._lock:
            self._maybe_reset_daily()
            return {
                "cost": {
                    "daily_spent": self.daily_cost,
                    "daily_budget": self.daily_budget,
                    "ratio": self.daily_cost / self.daily_budget,
                },
                "error_rate": self.errors.rate(),
                "avg_latency_ms": self.latencies.average(),
            }


class DegradationController:
    """
    Controller that ties metrics to degradation.
    
    Runs periodic checks and updates degradation level.
    """
    
    def __init__(
        self,
        manager: DegradationManager,
        metrics: DegradationMetrics,
        check_interval: float = 10.0,  # Check every 10 seconds
    ):
        self.manager = manager
        self.metrics = metrics
        self.check_interval = check_interval
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the degradation monitoring loop."""
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[DEGRADATION] Controller started")
    
    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        print("[DEGRADATION] Controller stopped")
    
    def _monitor_loop(self) -> None:
        """Periodic check loop."""
        while self._running:
            self._check_and_update()
            time.sleep(self.check_interval)
    
    def _check_and_update(self) -> None:
        """Check metrics and update degradation if needed."""
        all_metrics = self.metrics.get_all_metrics()
        
        new_level, changed = self.manager.update(
            cost_ratio=all_metrics["cost"]["ratio"],
            error_rate=all_metrics["error_rate"],
            avg_latency_ms=all_metrics["avg_latency_ms"],
        )
        
        if changed:
            # Log or alert on level changes
            self._on_level_change(new_level, all_metrics)
    
    def _on_level_change(
        self,
        new_level: DegradationLevel,
        metrics: dict,
    ) -> None:
        """Handle level change (logging, alerting, etc.)."""
        print(f"[ALERT] Degradation level changed to {new_level.name}")
        print(f"        Metrics: cost={metrics['cost']['ratio']:.1%}, "
              f"errors={metrics['error_rate']:.1%}, "
              f"latency={metrics['avg_latency_ms']:.0f}ms")
    
    def force_check(self) -> DegradationLevel:
        """Force an immediate check (useful for testing)."""
        self._check_and_update()
        return self.manager.current_level
```

---

## User Communication During Degradation

Be transparent. Users understand system constraints when you explain them.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class UserDegradationNotice:
    """User-facing notice about degradation."""
    show_notice: bool
    title: str
    message: str
    severity: str  # "info", "warning", "critical"
    estimated_resolution: Optional[str] = None


def get_user_notice(level: DegradationLevel) -> UserDegradationNotice:
    """Get user-appropriate notice for degradation level."""
    
    notices = {
        DegradationLevel.NORMAL: UserDegradationNotice(
            show_notice=False,
            title="",
            message="",
            severity="info",
        ),
        
        DegradationLevel.REDUCED: UserDegradationNotice(
            show_notice=True,
            title="High Demand",
            message="We're experiencing higher than normal demand. "
                    "Responses may be shorter, and some advanced features "
                    "are temporarily limited.",
            severity="info",
            estimated_resolution="Usually resolves within the hour",
        ),
        
        DegradationLevel.MINIMAL: UserDegradationNotice(
            show_notice=True,
            title="Limited Service",
            message="Due to system constraints, we're providing condensed "
                    "responses only. Some non-essential features are paused.",
            severity="warning",
            estimated_resolution="We're working to restore full service",
        ),
        
        DegradationLevel.EMERGENCY: UserDegradationNotice(
            show_notice=True,
            title="Service Interruption",
            message="We're experiencing significant service constraints. "
                    "Only essential, cached responses are available. "
                    "We apologize for the inconvenience.",
            severity="critical",
            estimated_resolution="Please try again later",
        ),
    }
    
    return notices.get(level, notices[DegradationLevel.NORMAL])


def format_api_response_with_degradation(
    response: DegradedResponse,
) -> dict:
    """Format API response including degradation info."""
    
    result = {
        "content": response.content,
        "metadata": {
            "model_used": response.model_used,
            "from_cache": response.from_cache,
        }
    }
    
    # Add degradation notice if applicable
    if response.user_notice:
        notice = get_user_notice(response.degradation_level)
        if notice.show_notice:
            result["system_notice"] = {
                "title": notice.title,
                "message": notice.message,
                "severity": notice.severity,
            }
    
    # Add rejection info if rejected
    if response.was_rejected:
        result["error"] = {
            "type": "service_degraded",
            "message": response.reject_reason,
            "retry_suggested": response.degradation_level != DegradationLevel.EMERGENCY,
        }
    
    return result


# Example response formatting
"""
# Normal response
{
    "content": "Here's a detailed explanation of quantum computing...",
    "metadata": {"model_used": "gpt-4o", "from_cache": false}
}

# Reduced response
{
    "content": "Quantum computing uses qubits to...",
    "metadata": {"model_used": "gpt-4o-mini", "from_cache": false},
    "system_notice": {
        "title": "High Demand",
        "message": "We're experiencing higher than normal demand...",
        "severity": "info"
    }
}

# Rejected response (minimal mode)
{
    "content": "",
    "metadata": {"model_used": "", "from_cache": false},
    "system_notice": {
        "title": "Limited Service",
        "message": "Due to system constraints...",
        "severity": "warning"
    },
    "error": {
        "type": "service_degraded",
        "message": "System is degraded. Non-critical requests are paused.",
        "retry_suggested": true
    }
}
"""
```

---

## Recovery: Getting Back to Normal

Recovery needs to be gradual and stable. Jumping straight from EMERGENCY to NORMAL can cause immediate re-degradation (flapping).

```python
class RecoveryManager:
    """
    Manages recovery from degraded states.
    
    Principles:
    1. Recover one level at a time (EMERGENCY → MINIMAL → REDUCED → NORMAL)
    2. Require stability before recovering (hysteresis)
    3. Minimum time at each level before recovery
    4. Monitor for re-degradation and back off
    """
    
    def __init__(
        self,
        degradation_manager: DegradationManager,
        min_time_before_recovery: float = 300.0,  # 5 minutes
        stability_checks: int = 3,  # N consecutive good checks
        check_interval: float = 60.0,  # 1 minute between checks
    ):
        self.manager = degradation_manager
        self.min_time = min_time_before_recovery
        self.stability_checks = stability_checks
        self.check_interval = check_interval
        
        self._consecutive_good_checks = 0
        self._last_degradation_time = time.time()
    
    def record_check_result(
        self,
        conditions_good: bool,
    ) -> tuple[bool, str]:
        """
        Record result of a stability check.
        
        Returns:
            Tuple of (recovery_allowed, reason)
        """
        if not conditions_good:
            # Reset counter on any bad check
            self._consecutive_good_checks = 0
            self._last_degradation_time = time.time()
            return False, "Conditions not stable"
        
        self._consecutive_good_checks += 1
        
        # Check if enough time has passed
        time_since_degradation = time.time() - self._last_degradation_time
        if time_since_degradation < self.min_time:
            remaining = self.min_time - time_since_degradation
            return False, f"Waiting for stability ({remaining:.0f}s remaining)"
        
        # Check if we have enough consecutive good checks
        if self._consecutive_good_checks < self.stability_checks:
            needed = self.stability_checks - self._consecutive_good_checks
            return False, f"Need {needed} more stable checks"
        
        # All conditions met
        return True, "Recovery allowed"
    
    def attempt_recovery(
        self,
        current_metrics: dict,
    ) -> tuple[bool, str]:
        """
        Attempt to recover one level.
        
        Returns:
            Tuple of (did_recover, message)
        """
        current_level = self.manager.current_level
        
        # Already at normal
        if current_level == DegradationLevel.NORMAL:
            return False, "Already at NORMAL level"
        
        # Evaluate if conditions allow recovery
        target = self.manager.evaluate_conditions(
            cost_ratio=current_metrics["cost"]["ratio"],
            error_rate=current_metrics["error_rate"],
            avg_latency_ms=current_metrics["avg_latency_ms"],
        )
        
        # Target should be better (lower) than current
        conditions_good = target.value < current_level.value
        
        recovery_allowed, reason = self.record_check_result(conditions_good)
        
        if not recovery_allowed:
            return False, reason
        
        # Recover ONE level
        next_level = DegradationLevel(current_level.value - 1)
        
        # Use the manager's transition (will apply hysteresis)
        new_level, changed = self.manager.update(
            cost_ratio=current_metrics["cost"]["ratio"],
            error_rate=current_metrics["error_rate"],
            avg_latency_ms=current_metrics["avg_latency_ms"],
        )
        
        if changed and new_level.value < current_level.value:
            self._consecutive_good_checks = 0  # Reset for next level
            return True, f"Recovered to {new_level.name}"
        
        return False, "Recovery conditions not met by manager"


# Recovery timeline example
"""
Timeline of gradual recovery:

T+0:00  - EMERGENCY triggered (budget exhausted)
T+5:00  - Budget resets (new day), conditions improve
T+5:00  - Check 1: Good (1/3)
T+6:00  - Check 2: Good (2/3)
T+7:00  - Check 3: Good (3/3)
T+7:00  - Recover to MINIMAL
T+7:00  - Reset counter (0/3)
T+8:00  - Check 1: Good (1/3)
T+9:00  - Check 2: Good (2/3)
T+10:00 - Check 3: Good (3/3)
T+10:00 - Recover to REDUCED
T+10:00 - Reset counter (0/3)
T+11:00 - Check 1: Good (1/3)
T+12:00 - Check 2: Bad! Error spike (0/3, timer reset)
T+17:00 - 5 min stability wait
T+17:00 - Check 1: Good (1/3)
T+18:00 - Check 2: Good (2/3)
T+19:00 - Check 3: Good (3/3)
T+19:00 - Recover to NORMAL

Total recovery time: 19 minutes (not instant!)
This prevents flapping and ensures stability.
"""
```

---

## Testing Degradation

Degradation logic must be tested. You don't want to discover it's broken during an actual incident.

```python
import unittest
from unittest.mock import Mock, patch

class TestDegradation(unittest.TestCase):
    """Test degradation behavior."""
    
    def setUp(self):
        self.manager = DegradationManager(
            reduced_threshold=0.80,
            minimal_threshold=0.95,
            emergency_threshold=1.0,
            min_time_in_level=0.1,  # Fast for testing
        )
    
    def test_normal_conditions(self):
        """System stays NORMAL when conditions are good."""
        level = self.manager.evaluate_conditions(
            cost_ratio=0.50,
            error_rate=0.01,
            avg_latency_ms=100,
        )
        self.assertEqual(level, DegradationLevel.NORMAL)
    
    def test_cost_triggers_reduced(self):
        """High cost triggers REDUCED mode."""
        level = self.manager.evaluate_conditions(
            cost_ratio=0.85,  # Above 80% threshold
            error_rate=0.01,
            avg_latency_ms=100,
        )
        self.assertEqual(level, DegradationLevel.REDUCED)
    
    def test_cost_triggers_minimal(self):
        """Very high cost triggers MINIMAL mode."""
        level = self.manager.evaluate_conditions(
            cost_ratio=0.97,  # Above 95% threshold
            error_rate=0.01,
            avg_latency_ms=100,
        )
        self.assertEqual(level, DegradationLevel.MINIMAL)
    
    def test_budget_exhausted_triggers_emergency(self):
        """Exhausted budget triggers EMERGENCY mode."""
        level = self.manager.evaluate_conditions(
            cost_ratio=1.0,  # 100% = exhausted
            error_rate=0.01,
            avg_latency_ms=100,
        )
        self.assertEqual(level, DegradationLevel.EMERGENCY)
    
    def test_error_rate_triggers_degradation(self):
        """High error rate triggers degradation."""
        # 10% errors → REDUCED
        level = self.manager.evaluate_conditions(
            cost_ratio=0.50,
            error_rate=0.10,
            avg_latency_ms=100,
        )
        self.assertEqual(level, DegradationLevel.REDUCED)
        
        # 30% errors → MINIMAL
        level = self.manager.evaluate_conditions(
            cost_ratio=0.50,
            error_rate=0.30,
            avg_latency_ms=100,
        )
        self.assertEqual(level, DegradationLevel.MINIMAL)
        
        # 60% errors → EMERGENCY
        level = self.manager.evaluate_conditions(
            cost_ratio=0.50,
            error_rate=0.60,
            avg_latency_ms=100,
        )
        self.assertEqual(level, DegradationLevel.EMERGENCY)
    
    def test_manual_override(self):
        """Manual override takes precedence."""
        self.manager.set_manual_override(
            DegradationLevel.MINIMAL,
            reason="Testing"
        )
        
        # Even with good conditions, manual override wins
        self.assertEqual(
            self.manager.current_level,
            DegradationLevel.MINIMAL
        )
        
        # Clear override
        self.manager.clear_manual_override()
        
        # Now should return to automatic
        level, _ = self.manager.update(cost_ratio=0.50, error_rate=0.01)
        # Will stay at MINIMAL initially due to min_time_in_level
    
    def test_gradual_degradation(self):
        """Degradation happens in steps."""
        # Start at NORMAL
        time.sleep(0.2)  # Wait for min_time_in_level
        
        # First update with high cost → REDUCED (not straight to MINIMAL)
        level, changed = self.manager.update(cost_ratio=0.85)
        self.assertEqual(level, DegradationLevel.REDUCED)
        self.assertTrue(changed)
        
        time.sleep(0.2)
        
        # Higher cost → MINIMAL
        level, changed = self.manager.update(cost_ratio=0.97)
        self.assertEqual(level, DegradationLevel.MINIMAL)
    
    def test_hysteresis_prevents_flapping(self):
        """Recovery requires buffer room (hysteresis)."""
        # Degrade to REDUCED
        time.sleep(0.2)
        self.manager.update(cost_ratio=0.85)
        
        time.sleep(0.2)
        
        # Cost drops to 75% - still above recovery threshold (80% - 10% = 70%)
        level, changed = self.manager.update(cost_ratio=0.75)
        self.assertEqual(level, DegradationLevel.REDUCED)  # Still REDUCED
        self.assertFalse(changed)
        
        # Cost drops to 65% - now below recovery threshold
        level, changed = self.manager.update(cost_ratio=0.65)
        self.assertEqual(level, DegradationLevel.NORMAL)  # Recovered
        self.assertTrue(changed)


class TestDegradedHandler(unittest.TestCase):
    """Test degradation-aware request handling."""
    
    def setUp(self):
        self.manager = DegradationManager()
        self.mock_client = Mock()
        self.mock_cache = Mock()
        self.handler = DegradationAwareHandler(
            degradation_manager=self.manager,
            llm_client=self.mock_client,
            cache=self.mock_cache,
        )
    
    def test_model_downgrade_in_reduced_mode(self):
        """Expensive models downgraded in REDUCED mode."""
        self.manager.set_manual_override(DegradationLevel.REDUCED)
        
        self.mock_cache.get.return_value = None  # No cache hit
        self.mock_client.responses.create.return_value = Mock(output_text="Response")
        
        response = self.handler.handle_request(
            prompt="Test",
            requested_model="gpt-4o",  # Expensive model
            is_critical=False,
        )
        
        # Should use cheaper model
        call_args = self.mock_client.responses.create.call_args
        self.assertIn(call_args.kwargs["model"], ["gpt-4o-mini", "claude-haiku-4-5"])
    
    def test_non_critical_rejected_in_minimal_mode(self):
        """Non-critical requests rejected in MINIMAL mode."""
        self.manager.set_manual_override(DegradationLevel.MINIMAL)
        
        response = self.handler.handle_request(
            prompt="Test",
            requested_model="gpt-4o",
            is_critical=False,
        )
        
        self.assertTrue(response.was_rejected)
        self.assertIn("Non-critical", response.reject_reason)
    
    def test_critical_still_served_in_minimal_mode(self):
        """Critical requests still served in MINIMAL mode."""
        self.manager.set_manual_override(DegradationLevel.MINIMAL)
        
        self.mock_cache.get.return_value = None
        self.mock_client.responses.create.return_value = Mock(output_text="Response")
        
        response = self.handler.handle_request(
            prompt="Test",
            requested_model="gpt-4o",
            is_critical=True,  # Critical
        )
        
        self.assertFalse(response.was_rejected)
        self.assertEqual(response.content, "Response")
    
    def test_cache_only_in_emergency_mode(self):
        """Only cached responses in EMERGENCY mode."""
        self.manager.set_manual_override(DegradationLevel.EMERGENCY)
        
        # No cache hit
        self.mock_cache.get.return_value = None
        
        response = self.handler.handle_request(
            prompt="Test",
            requested_model="gpt-4o",
            is_critical=True,
            cache_key="test_key",
        )
        
        self.assertTrue(response.was_rejected)
        self.assertIn("emergency mode", response.reject_reason.lower())
        
        # LLM should NOT be called
        self.mock_client.responses.create.assert_not_called()
    
    def test_cache_hit_in_emergency_mode(self):
        """Cached responses served in EMERGENCY mode."""
        self.manager.set_manual_override(DegradationLevel.EMERGENCY)
        
        # Cache hit
        self.mock_cache.get.return_value = "Cached response"
        
        response = self.handler.handle_request(
            prompt="Test",
            requested_model="gpt-4o",
            is_critical=True,
            cache_key="test_key",
        )
        
        self.assertFalse(response.was_rejected)
        self.assertEqual(response.content, "Cached response")
        self.assertTrue(response.from_cache)


if __name__ == "__main__":
    unittest.main()
```

---

## Putting It All Together

```python
# Complete integration example

def create_degradation_system(
    daily_budget: float = 100.0,
) -> tuple[DegradationManager, DegradationMetrics, DegradationController]:
    """Create and wire up the complete degradation system."""
    
    # Create components
    manager = DegradationManager(
        reduced_threshold=0.80,
        minimal_threshold=0.95,
        emergency_threshold=1.0,
        recovery_buffer=0.10,
        min_time_in_level=60.0,
    )
    
    metrics = DegradationMetrics(
        daily_budget=daily_budget,
        window_seconds=300,
    )
    
    controller = DegradationController(
        manager=manager,
        metrics=metrics,
        check_interval=10.0,
    )
    
    return manager, metrics, controller


# Usage in your application
"""
# Startup
manager, metrics, controller = create_degradation_system(daily_budget=100.0)
controller.start()

# Create handler
handler = DegradationAwareHandler(
    degradation_manager=manager,
    llm_client=openai_client,
    cache=response_cache,
)

# On each request
def handle_user_request(prompt: str, user_id: str):
    start_time = time.time()
    
    try:
        # Handle with degradation awareness
        response = handler.handle_request(
            prompt=prompt,
            requested_model=user_preferred_model,
            is_critical=is_critical_request(prompt),
            cache_key=generate_cache_key(prompt),
        )
        
        # Record success metrics
        latency_ms = (time.time() - start_time) * 1000
        metrics.record_request(
            cost=calculate_cost(response),
            latency_ms=latency_ms,
            success=True,
        )
        
        return format_api_response_with_degradation(response)
        
    except Exception as e:
        # Record failure metrics
        latency_ms = (time.time() - start_time) * 1000
        metrics.record_request(
            cost=0.0,
            latency_ms=latency_ms,
            success=False,
        )
        raise

# Admin endpoint for manual override
def admin_set_degradation(level: str, reason: str):
    level_enum = DegradationLevel[level.upper()]
    manager.set_manual_override(level_enum, reason)
    return manager.get_status()

def admin_clear_override():
    manager.clear_manual_override()
    return manager.get_status()

# Shutdown
controller.stop()
"""
```

---

## Key Takeaways

1. **Degradation is a spectrum**: NORMAL → REDUCED → MINIMAL → EMERGENCY
    
2. **Reduced functionality beats no functionality**: Users prefer shorter responses over error pages
    
3. **Automatic triggers**: Cost ratio, error rate, latency all signal when to degrade
    
4. **Manual overrides**: Needed for known incidents and scheduled maintenance
    
5. **Gradual recovery**: Step up one level at a time with stability checks
    
6. **Hysteresis prevents flapping**: Require buffer room before recovering
    
7. **Be transparent with users**: Tell them what's happening and set expectations
    
8. **Test your degradation**: Simulate budget exhaustion in staging, verify behavior
    

---

## Week 8 Days 5-6 Summary

These five notes cover the complete cost control stack:

1. **Note 1**: Where the money goes (cost anatomy)
2. **Note 2**: Using cheap models for cheap tasks (model routing)
3. **Note 3**: Setting limits before execution (token budgeting)
4. **Note 4**: Enforcing limits per user and globally (rate limiting)
5. **Note 5**: What happens when limits hit (graceful degradation)

Together, they ensure your LLM system survives traffic spikes, budget limits, and provider issues while still providing value to users.

---

## References

- Circuit Breaker Pattern: https://martinfowler.com/bliki/CircuitBreaker.html
- Graceful Degradation in Distributed Systems: https://aws.amazon.com/builders-library/
- Hysteresis in Control Systems: https://en.wikipedia.org/wiki/Hysteresis