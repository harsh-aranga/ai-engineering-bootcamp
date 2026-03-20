# Note 4: Rate Limiting — Per-User, Global, and Cost-Based

## Why Rate Limiting Is Survival

Without rate limiting, your LLM system is a credit card with no limit attached to a public API. Three scenarios will find you:

**Scenario 1: The Enthusiastic User**

```
User discovers your API works great for their batch job.
Writes a script that sends 10,000 queries in an hour.
Your $100/month budget becomes a $1,000 day.
```

**Scenario 2: The Traffic Spike**

```
Your product gets featured on Hacker News.
Traffic goes from 100 requests/hour to 10,000 requests/hour.
Every request costs $0.01.
You wake up to a $2,400 bill.
```

**Scenario 3: The Bad Actor**

```
Someone discovers your endpoint.
Writes a bot that hammers it.
Intentional or not, you're paying.
```

Rate limiting exists to make these scenarios survivable. It's not about being stingy with users—it's about keeping your system running tomorrow.

---

## Types of Rate Limits

LLM systems need multiple layers of rate limiting. Each catches different failure modes.

### The Rate Limiting Stack

```
┌─────────────────────────────────────────────────────────────┐
│ GLOBAL LIMITS (system survival)                             │
│ - Total requests/minute across all users                    │
│ - Total cost/hour across all users                          │
│ - Circuit breaker: shut down if $X exceeded                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ PER-USER LIMITS (fairness + abuse prevention)               │
│ - Requests/minute per user                                  │
│ - Tokens/hour per user                                      │
│ - Cost/day per user                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ TIERED LIMITS (business model)                              │
│ - Free tier: 10 requests/day                                │
│ - Basic tier: 100 requests/day                              │
│ - Pro tier: 1000 requests/day                               │
└─────────────────────────────────────────────────────────────┘
```

### Per-User Request Limits

The simplest form: count requests per user per time window.

```python
from collections import defaultdict
from datetime import datetime, timedelta
import time
from typing import Tuple
from dataclasses import dataclass, field

@dataclass
class RequestWindow:
    """Track requests in a sliding window."""
    timestamps: list = field(default_factory=list)
    
    def add_request(self, timestamp: float) -> None:
        self.timestamps.append(timestamp)
    
    def count_recent(self, window_seconds: int) -> int:
        """Count requests within the window."""
        cutoff = time.time() - window_seconds
        # Clean old entries while counting
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        return len(self.timestamps)


class RequestRateLimiter:
    """
    Simple request-based rate limiter.
    
    Limits: requests per minute per user.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        window_seconds: int = 60,
    ):
        self.limit = requests_per_minute
        self.window = window_seconds
        self.user_windows: dict[str, RequestWindow] = defaultdict(RequestWindow)
    
    def check_limit(self, user_id: str) -> Tuple[bool, dict]:
        """
        Check if user can make a request.
        
        Returns:
            Tuple of (allowed, info_dict)
        """
        window = self.user_windows[user_id]
        current_count = window.count_recent(self.window)
        
        if current_count >= self.limit:
            # Calculate when they can retry
            oldest_in_window = min(window.timestamps) if window.timestamps else time.time()
            retry_after = oldest_in_window + self.window - time.time()
            
            return False, {
                "allowed": False,
                "reason": "rate_limit",
                "limit": self.limit,
                "remaining": 0,
                "retry_after_seconds": max(0, retry_after),
                "message": f"Rate limit exceeded. Try again in {int(retry_after)} seconds.",
            }
        
        # Allow the request
        window.add_request(time.time())
        
        return True, {
            "allowed": True,
            "limit": self.limit,
            "remaining": self.limit - current_count - 1,
            "retry_after_seconds": None,
        }


# Usage
limiter = RequestRateLimiter(requests_per_minute=10)

for i in range(12):
    allowed, info = limiter.check_limit("user_123")
    if allowed:
        print(f"Request {i+1}: Allowed ({info['remaining']} remaining)")
    else:
        print(f"Request {i+1}: Blocked - {info['message']}")
```

### Per-User Token Limits

Requests aren't equal in LLM land. A classification request uses 100 tokens; a report generation uses 10,000. Token-based limits are fairer:

```python
from dataclasses import dataclass, field
from collections import defaultdict
import time
from typing import Tuple

@dataclass
class TokenUsage:
    """Track token usage in a sliding window."""
    entries: list = field(default_factory=list)  # [(timestamp, tokens), ...]
    
    def add_usage(self, tokens: int) -> None:
        self.entries.append((time.time(), tokens))
    
    def get_recent_usage(self, window_seconds: int) -> int:
        """Get total tokens used in window."""
        cutoff = time.time() - window_seconds
        self.entries = [(t, tok) for t, tok in self.entries if t > cutoff]
        return sum(tok for _, tok in self.entries)


class TokenRateLimiter:
    """
    Token-based rate limiter.
    
    Limits: tokens per hour per user.
    Better for LLM APIs where requests vary wildly in size.
    """
    
    def __init__(
        self,
        tokens_per_hour: int = 100_000,
        window_seconds: int = 3600,
    ):
        self.limit = tokens_per_hour
        self.window = window_seconds
        self.user_usage: dict[str, TokenUsage] = defaultdict(TokenUsage)
    
    def check_limit(
        self,
        user_id: str,
        estimated_tokens: int,
    ) -> Tuple[bool, dict]:
        """
        Check if user can make a request with estimated tokens.
        
        Args:
            user_id: User identifier
            estimated_tokens: Estimated total tokens for this request
        """
        usage = self.user_usage[user_id]
        current_usage = usage.get_recent_usage(self.window)
        
        if current_usage + estimated_tokens > self.limit:
            return False, {
                "allowed": False,
                "reason": "token_limit",
                "limit": self.limit,
                "used": current_usage,
                "remaining": max(0, self.limit - current_usage),
                "requested": estimated_tokens,
                "message": f"Token limit exceeded. Used {current_usage:,} of {self.limit:,} tokens this hour.",
            }
        
        return True, {
            "allowed": True,
            "limit": self.limit,
            "used": current_usage,
            "remaining": self.limit - current_usage - estimated_tokens,
        }
    
    def record_usage(self, user_id: str, actual_tokens: int) -> None:
        """Record actual token usage after request completes."""
        self.user_usage[user_id].add_usage(actual_tokens)
    
    def get_user_status(self, user_id: str) -> dict:
        """Get current usage status for a user."""
        usage = self.user_usage[user_id]
        current = usage.get_recent_usage(self.window)
        
        return {
            "user_id": user_id,
            "tokens_used": current,
            "tokens_limit": self.limit,
            "tokens_remaining": max(0, self.limit - current),
            "percent_used": (current / self.limit) * 100,
            "window_seconds": self.window,
        }
```

### Per-User Cost Limits

The most accurate limit for LLM systems: dollars and cents.

```python
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
import time
from typing import Tuple

@dataclass
class CostEntry:
    timestamp: float
    cost: float


class CostRateLimiter:
    """
    Cost-based rate limiter.
    
    Limits: dollars per day per user.
    Most accurate for LLM systems with varying model/token costs.
    """
    
    def __init__(
        self,
        cost_per_day: float = 5.00,  # $5/day per user
    ):
        self.daily_limit = cost_per_day
        self.user_costs: dict[str, list[CostEntry]] = defaultdict(list)
        self._last_daily_reset = self._get_day_key()
    
    def _get_day_key(self) -> str:
        """Get current day key for reset tracking."""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _cleanup_old_entries(self, user_id: str) -> None:
        """Remove entries from previous days."""
        today = self._get_day_key()
        today_start = datetime.strptime(today, "%Y-%m-%d").timestamp()
        
        self.user_costs[user_id] = [
            e for e in self.user_costs[user_id]
            if e.timestamp >= today_start
        ]
    
    def _get_daily_spend(self, user_id: str) -> float:
        """Get user's spend today."""
        self._cleanup_old_entries(user_id)
        return sum(e.cost for e in self.user_costs[user_id])
    
    def check_limit(
        self,
        user_id: str,
        estimated_cost: float,
    ) -> Tuple[bool, dict]:
        """
        Check if user can afford a request.
        
        Args:
            user_id: User identifier
            estimated_cost: Estimated cost in USD
        """
        daily_spend = self._get_daily_spend(user_id)
        
        if daily_spend + estimated_cost > self.daily_limit:
            # Calculate reset time (midnight)
            now = datetime.now()
            tomorrow = datetime(now.year, now.month, now.day) + timedelta(days=1)
            seconds_until_reset = (tomorrow - now).total_seconds()
            
            return False, {
                "allowed": False,
                "reason": "cost_limit",
                "daily_limit": self.daily_limit,
                "spent_today": daily_spend,
                "remaining": max(0, self.daily_limit - daily_spend),
                "estimated_cost": estimated_cost,
                "retry_after_seconds": seconds_until_reset,
                "message": f"Daily budget exceeded. Spent ${daily_spend:.4f} of ${self.daily_limit:.2f} today.",
            }
        
        return True, {
            "allowed": True,
            "daily_limit": self.daily_limit,
            "spent_today": daily_spend,
            "remaining": self.daily_limit - daily_spend - estimated_cost,
        }
    
    def record_cost(self, user_id: str, actual_cost: float) -> None:
        """Record actual cost after request completes."""
        self.user_costs[user_id].append(
            CostEntry(timestamp=time.time(), cost=actual_cost)
        )
    
    def get_user_status(self, user_id: str) -> dict:
        """Get budget status for a user."""
        daily_spend = self._get_daily_spend(user_id)
        
        return {
            "user_id": user_id,
            "daily_limit": self.daily_limit,
            "spent_today": daily_spend,
            "remaining_today": max(0, self.daily_limit - daily_spend),
            "percent_used": (daily_spend / self.daily_limit) * 100,
        }


# Import needed for timedelta
from datetime import timedelta
```

---

## The Token Bucket Algorithm

The sliding window approaches above work, but the token bucket algorithm is more elegant and efficient. It's the industry standard for rate limiting.

### The Mental Model

Imagine a bucket that:

1. Has a maximum capacity (e.g., 100 tokens)
2. Refills at a steady rate (e.g., 10 tokens per second)
3. Each request consumes tokens from the bucket
4. If the bucket is empty, the request is rejected

This naturally handles both:

- **Sustained throughput**: Refill rate limits long-term rate
- **Burst capacity**: Bucket capacity allows short bursts

```
Bucket Capacity: 100 tokens
Refill Rate: 10 tokens/second

Scenario A: Steady traffic (10 req/sec)
- Each second: consume 10, refill 10
- Bucket stays full-ish
- All requests pass

Scenario B: Burst traffic (50 requests instantly)
- Consume 50 from bucket (50 remaining)
- Next 50 requests in same second → 50 more consumed
- Bucket empty
- Subsequent requests blocked until refill

Scenario C: Idle then burst
- No traffic for 10 seconds
- Bucket fills to capacity (100)
- User can burst 100 requests
- Then limited to refill rate (10/sec)
```

### Implementation

```python
import time
import threading
from typing import Tuple, Optional
from dataclasses import dataclass

@dataclass
class BucketState:
    """State of a token bucket."""
    tokens: float
    last_refill: float


class TokenBucket:
    """
    Token bucket rate limiter.
    
    Allows bursts up to capacity, with sustained rate limited by refill_rate.
    Thread-safe implementation.
    """
    
    def __init__(
        self,
        capacity: float,
        refill_rate: float,  # Tokens per second
    ):
        """
        Args:
            capacity: Maximum tokens (burst capacity)
            refill_rate: Tokens added per second (sustained rate)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def _refill(self) -> None:
        """Add tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens proportional to elapsed time
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
    
    def consume(self, tokens: float = 1.0) -> Tuple[bool, float]:
        """
        Try to consume tokens from the bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            Tuple of (success, wait_time)
            If success is False, wait_time indicates seconds until tokens available
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            
            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate
            
            return False, wait_time
    
    def get_state(self) -> dict:
        """Get current bucket state."""
        with self.lock:
            self._refill()
            return {
                "tokens_available": self.tokens,
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
                "percent_full": (self.tokens / self.capacity) * 100,
            }


class PerUserTokenBucketLimiter:
    """
    Per-user rate limiting using token buckets.
    
    Each user gets their own bucket with independent state.
    """
    
    def __init__(
        self,
        capacity: float = 100,
        refill_rate: float = 10,
        cleanup_interval: int = 300,  # Cleanup inactive users every 5 minutes
    ):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.cleanup_interval = cleanup_interval
        
        self.buckets: dict[str, TokenBucket] = {}
        self.buckets_lock = threading.Lock()
        self.last_cleanup = time.time()
    
    def _get_bucket(self, user_id: str) -> TokenBucket:
        """Get or create bucket for user."""
        with self.buckets_lock:
            self._maybe_cleanup()
            
            if user_id not in self.buckets:
                self.buckets[user_id] = TokenBucket(
                    capacity=self.capacity,
                    refill_rate=self.refill_rate,
                )
            
            return self.buckets[user_id]
    
    def _maybe_cleanup(self) -> None:
        """Remove inactive user buckets to prevent memory growth."""
        now = time.time()
        if now - self.last_cleanup < self.cleanup_interval:
            return
        
        # Remove buckets that haven't been used recently
        inactive_threshold = now - self.cleanup_interval
        inactive_users = [
            user_id for user_id, bucket in self.buckets.items()
            if bucket.last_refill < inactive_threshold
        ]
        
        for user_id in inactive_users:
            del self.buckets[user_id]
        
        self.last_cleanup = now
    
    def check_limit(
        self,
        user_id: str,
        tokens: float = 1.0,
    ) -> Tuple[bool, dict]:
        """
        Check if user can make a request.
        
        Args:
            user_id: User identifier
            tokens: Tokens this request will consume
        """
        bucket = self._get_bucket(user_id)
        allowed, wait_time = bucket.consume(tokens)
        
        state = bucket.get_state()
        
        if allowed:
            return True, {
                "allowed": True,
                "tokens_remaining": state["tokens_available"],
                "capacity": self.capacity,
            }
        
        return False, {
            "allowed": False,
            "reason": "rate_limit",
            "retry_after_seconds": wait_time,
            "tokens_remaining": state["tokens_available"],
            "capacity": self.capacity,
            "message": f"Rate limit exceeded. Try again in {wait_time:.1f} seconds.",
        }


# Usage example
limiter = PerUserTokenBucketLimiter(
    capacity=10,     # Allow burst of 10 requests
    refill_rate=2,   # 2 requests per second sustained
)

# Simulate burst
print("Burst of 12 requests:")
for i in range(12):
    allowed, info = limiter.check_limit("user_123")
    status = "✓" if allowed else f"✗ (wait {info.get('retry_after_seconds', 0):.1f}s)"
    print(f"  Request {i+1}: {status}")

# Wait and retry
print("\nWait 3 seconds...")
time.sleep(3)

allowed, info = limiter.check_limit("user_123")
print(f"After wait: {'✓ Allowed' if allowed else '✗ Blocked'}")
```

---

## Global Rate Limits

Per-user limits protect individual users from abuse. Global limits protect your entire system from collective overload.

```python
import time
import threading
from typing import Tuple
from dataclasses import dataclass

@dataclass
class GlobalLimitState:
    """Track global limits across all users."""
    requests_this_minute: int = 0
    cost_today: float = 0.0
    minute_start: float = 0.0
    day_start: str = ""


class GlobalRateLimiter:
    """
    Global rate limiting across all users.
    
    Protects system-wide resources.
    """
    
    def __init__(
        self,
        max_requests_per_minute: int = 1000,
        max_cost_per_hour: float = 100.0,
        max_cost_per_day: float = 1000.0,
        emergency_shutdown_threshold: float = 500.0,  # Shut down if this is hit in an hour
    ):
        self.max_rpm = max_requests_per_minute
        self.max_cost_hour = max_cost_per_hour
        self.max_cost_day = max_cost_per_day
        self.emergency_threshold = emergency_shutdown_threshold
        
        # Tracking
        self.minute_requests: list[float] = []  # Timestamps
        self.hour_costs: list[tuple[float, float]] = []  # (timestamp, cost)
        self.day_costs: list[tuple[float, float]] = []
        
        self.lock = threading.Lock()
        self.emergency_shutdown = False
    
    def _cleanup_old_entries(self) -> None:
        """Remove old tracking entries."""
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        day_ago = now - 86400
        
        self.minute_requests = [t for t in self.minute_requests if t > minute_ago]
        self.hour_costs = [(t, c) for t, c in self.hour_costs if t > hour_ago]
        self.day_costs = [(t, c) for t, c in self.day_costs if t > day_ago]
    
    def _get_current_stats(self) -> dict:
        """Get current usage stats."""
        self._cleanup_old_entries()
        
        return {
            "requests_this_minute": len(self.minute_requests),
            "cost_this_hour": sum(c for _, c in self.hour_costs),
            "cost_today": sum(c for _, c in self.day_costs),
        }
    
    def check_global_limits(
        self,
        estimated_cost: float = 0.0,
    ) -> Tuple[bool, dict]:
        """
        Check if system can handle another request.
        
        Called BEFORE per-user limits.
        """
        with self.lock:
            if self.emergency_shutdown:
                return False, {
                    "allowed": False,
                    "reason": "emergency_shutdown",
                    "message": "System is in emergency shutdown mode due to excessive costs.",
                }
            
            stats = self._get_current_stats()
            
            # Check request rate
            if stats["requests_this_minute"] >= self.max_rpm:
                return False, {
                    "allowed": False,
                    "reason": "global_request_limit",
                    "message": "System request limit reached. Please try again shortly.",
                    "retry_after_seconds": 60,
                }
            
            # Check hourly cost
            if stats["cost_this_hour"] + estimated_cost > self.max_cost_hour:
                return False, {
                    "allowed": False,
                    "reason": "global_cost_limit_hour",
                    "message": "System hourly cost limit reached.",
                    "retry_after_seconds": 3600,
                }
            
            # Check daily cost
            if stats["cost_today"] + estimated_cost > self.max_cost_day:
                return False, {
                    "allowed": False,
                    "reason": "global_cost_limit_day",
                    "message": "System daily cost limit reached. Try again tomorrow.",
                }
            
            return True, {
                "allowed": True,
                "stats": stats,
            }
    
    def record_request(self, actual_cost: float) -> None:
        """Record a completed request."""
        with self.lock:
            now = time.time()
            
            self.minute_requests.append(now)
            self.hour_costs.append((now, actual_cost))
            self.day_costs.append((now, actual_cost))
            
            # Check for emergency shutdown
            self._cleanup_old_entries()
            hour_cost = sum(c for _, c in self.hour_costs)
            
            if hour_cost >= self.emergency_threshold:
                self.emergency_shutdown = True
                print(f"⚠️ EMERGENCY SHUTDOWN: Hourly cost ${hour_cost:.2f} exceeded ${self.emergency_threshold:.2f}")
    
    def get_system_status(self) -> dict:
        """Get current system status."""
        with self.lock:
            stats = self._get_current_stats()
            
            return {
                "emergency_shutdown": self.emergency_shutdown,
                "requests_per_minute": {
                    "current": stats["requests_this_minute"],
                    "limit": self.max_rpm,
                    "percent": (stats["requests_this_minute"] / self.max_rpm) * 100,
                },
                "hourly_cost": {
                    "current": stats["cost_this_hour"],
                    "limit": self.max_cost_hour,
                    "percent": (stats["cost_this_hour"] / self.max_cost_hour) * 100,
                },
                "daily_cost": {
                    "current": stats["cost_today"],
                    "limit": self.max_cost_day,
                    "percent": (stats["cost_today"] / self.max_cost_day) * 100,
                },
            }
    
    def reset_emergency_shutdown(self) -> None:
        """Manually reset emergency shutdown (admin action)."""
        with self.lock:
            self.emergency_shutdown = False
            print("Emergency shutdown reset.")
```

---

## Tiered Limits

Different user tiers get different limits. This is your business model encoded in rate limiting.

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class UserTier(Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class TierLimits:
    """Rate limits for a user tier."""
    requests_per_day: int
    tokens_per_hour: int
    cost_per_day: float
    max_output_tokens: int  # Max output per request
    models_allowed: list[str]


# Define tier limits
TIER_LIMITS = {
    UserTier.FREE: TierLimits(
        requests_per_day=10,
        tokens_per_hour=10_000,
        cost_per_day=0.50,
        max_output_tokens=500,
        models_allowed=["gpt-4o-mini"],
    ),
    UserTier.BASIC: TierLimits(
        requests_per_day=100,
        tokens_per_hour=100_000,
        cost_per_day=5.00,
        max_output_tokens=1000,
        models_allowed=["gpt-4o-mini", "gpt-4o"],
    ),
    UserTier.PRO: TierLimits(
        requests_per_day=1000,
        tokens_per_hour=500_000,
        cost_per_day=25.00,
        max_output_tokens=4000,
        models_allowed=["gpt-4o-mini", "gpt-4o", "claude-sonnet-4-6"],
    ),
    UserTier.ENTERPRISE: TierLimits(
        requests_per_day=10000,
        tokens_per_hour=2_000_000,
        cost_per_day=100.00,
        max_output_tokens=8000,
        models_allowed=["gpt-4o-mini", "gpt-4o", "claude-sonnet-4-6", "claude-opus-4-6"],
    ),
}


class TieredRateLimiter:
    """
    Rate limiter with tier-based limits.
    
    Combines request, token, and cost limits based on user tier.
    """
    
    def __init__(self):
        # Per-user tracking
        self.user_tiers: dict[str, UserTier] = {}
        self.daily_requests: dict[str, int] = {}
        self.hourly_tokens: dict[str, list[tuple[float, int]]] = {}  # (timestamp, tokens)
        self.daily_costs: dict[str, list[tuple[float, float]]] = {}  # (timestamp, cost)
        
        self._last_day_reset = self._get_day_key()
    
    def _get_day_key(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
    
    def set_user_tier(self, user_id: str, tier: UserTier) -> None:
        """Set the tier for a user."""
        self.user_tiers[user_id] = tier
    
    def get_user_tier(self, user_id: str) -> UserTier:
        """Get user's tier (default: FREE)."""
        return self.user_tiers.get(user_id, UserTier.FREE)
    
    def get_limits(self, user_id: str) -> TierLimits:
        """Get limits for a user based on their tier."""
        tier = self.get_user_tier(user_id)
        return TIER_LIMITS[tier]
    
    def check_limits(
        self,
        user_id: str,
        estimated_tokens: int,
        estimated_cost: float,
        model: str,
    ) -> tuple[bool, dict]:
        """
        Check all limits for a user.
        
        Returns (allowed, info_dict)
        """
        limits = self.get_limits(user_id)
        tier = self.get_user_tier(user_id)
        
        # Check model access
        if model not in limits.models_allowed:
            return False, {
                "allowed": False,
                "reason": "model_not_allowed",
                "message": f"Model '{model}' not available on {tier.value} tier.",
                "allowed_models": limits.models_allowed,
                "upgrade_hint": "Upgrade to access more models.",
            }
        
        # Check daily requests
        daily_req = self.daily_requests.get(user_id, 0)
        if daily_req >= limits.requests_per_day:
            return False, {
                "allowed": False,
                "reason": "daily_request_limit",
                "message": f"Daily request limit ({limits.requests_per_day}) reached.",
                "tier": tier.value,
                "upgrade_hint": f"Upgrade to increase your limit.",
            }
        
        # Check hourly tokens (sliding window)
        hourly_tokens = self._get_hourly_tokens(user_id)
        if hourly_tokens + estimated_tokens > limits.tokens_per_hour:
            return False, {
                "allowed": False,
                "reason": "hourly_token_limit",
                "message": f"Hourly token limit ({limits.tokens_per_hour:,}) reached.",
                "used": hourly_tokens,
                "tier": tier.value,
            }
        
        # Check daily cost
        daily_cost = self._get_daily_cost(user_id)
        if daily_cost + estimated_cost > limits.cost_per_day:
            return False, {
                "allowed": False,
                "reason": "daily_cost_limit",
                "message": f"Daily cost limit (${limits.cost_per_day:.2f}) reached.",
                "spent": daily_cost,
                "tier": tier.value,
            }
        
        return True, {
            "allowed": True,
            "tier": tier.value,
            "limits": {
                "requests_remaining": limits.requests_per_day - daily_req - 1,
                "tokens_remaining": limits.tokens_per_hour - hourly_tokens - estimated_tokens,
                "budget_remaining": limits.cost_per_day - daily_cost - estimated_cost,
            },
        }
    
    def _get_hourly_tokens(self, user_id: str) -> int:
        """Get tokens used in the last hour."""
        import time
        hour_ago = time.time() - 3600
        entries = self.hourly_tokens.get(user_id, [])
        entries = [(t, tok) for t, tok in entries if t > hour_ago]
        self.hourly_tokens[user_id] = entries
        return sum(tok for _, tok in entries)
    
    def _get_daily_cost(self, user_id: str) -> float:
        """Get cost spent today."""
        from datetime import datetime
        import time
        
        today_start = datetime.strptime(self._get_day_key(), "%Y-%m-%d").timestamp()
        entries = self.daily_costs.get(user_id, [])
        entries = [(t, c) for t, c in entries if t >= today_start]
        self.daily_costs[user_id] = entries
        return sum(c for _, c in entries)
    
    def record_usage(
        self,
        user_id: str,
        tokens: int,
        cost: float,
    ) -> None:
        """Record usage after request completes."""
        import time
        now = time.time()
        
        # Update daily requests
        self.daily_requests[user_id] = self.daily_requests.get(user_id, 0) + 1
        
        # Update hourly tokens
        if user_id not in self.hourly_tokens:
            self.hourly_tokens[user_id] = []
        self.hourly_tokens[user_id].append((now, tokens))
        
        # Update daily costs
        if user_id not in self.daily_costs:
            self.daily_costs[user_id] = []
        self.daily_costs[user_id].append((now, cost))
    
    def get_user_status(self, user_id: str) -> dict:
        """Get comprehensive status for a user."""
        tier = self.get_user_tier(user_id)
        limits = self.get_limits(user_id)
        
        daily_req = self.daily_requests.get(user_id, 0)
        hourly_tokens = self._get_hourly_tokens(user_id)
        daily_cost = self._get_daily_cost(user_id)
        
        return {
            "user_id": user_id,
            "tier": tier.value,
            "requests": {
                "used_today": daily_req,
                "limit": limits.requests_per_day,
                "remaining": limits.requests_per_day - daily_req,
            },
            "tokens": {
                "used_this_hour": hourly_tokens,
                "limit": limits.tokens_per_hour,
                "remaining": limits.tokens_per_hour - hourly_tokens,
            },
            "cost": {
                "spent_today": daily_cost,
                "limit": limits.cost_per_day,
                "remaining": limits.cost_per_day - daily_cost,
            },
            "models_allowed": limits.models_allowed,
            "max_output_tokens": limits.max_output_tokens,
        }
```

---

## Rate Limit Response Design

How you communicate rate limits matters. Users should understand what happened and what to do.

### Response Headers

```python
from typing import Optional

def create_rate_limit_headers(
    limit: int,
    remaining: int,
    reset_timestamp: Optional[float] = None,
    retry_after: Optional[float] = None,
) -> dict:
    """
    Create standard rate limit response headers.
    
    Following industry conventions (GitHub, Twitter, etc.)
    """
    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(0, remaining)),
    }
    
    if reset_timestamp:
        headers["X-RateLimit-Reset"] = str(int(reset_timestamp))
    
    if retry_after:
        headers["Retry-After"] = str(int(retry_after) + 1)  # Round up
    
    return headers


def create_rate_limit_response(
    reason: str,
    limit_type: str,  # "request", "token", "cost"
    limit_value: int | float,
    current_usage: int | float,
    retry_after_seconds: Optional[float] = None,
    tier: Optional[str] = None,
) -> dict:
    """
    Create a user-friendly rate limit error response.
    """
    messages = {
        "request": f"Request limit reached: {current_usage} of {limit_value} requests used.",
        "token": f"Token limit reached: {current_usage:,} of {limit_value:,} tokens used.",
        "cost": f"Budget limit reached: ${current_usage:.2f} of ${limit_value:.2f} spent.",
    }
    
    response = {
        "error": {
            "type": "rate_limit_exceeded",
            "code": f"{limit_type}_limit_exceeded",
            "message": messages.get(limit_type, "Rate limit exceeded."),
            "limit_type": limit_type,
            "limit": limit_value,
            "used": current_usage,
            "remaining": max(0, limit_value - current_usage) if isinstance(limit_value, int) else max(0.0, limit_value - current_usage),
        }
    }
    
    if retry_after_seconds:
        response["error"]["retry_after_seconds"] = int(retry_after_seconds)
        
        if retry_after_seconds < 60:
            response["error"]["retry_message"] = f"Try again in {int(retry_after_seconds)} seconds."
        elif retry_after_seconds < 3600:
            minutes = int(retry_after_seconds / 60)
            response["error"]["retry_message"] = f"Try again in {minutes} minute{'s' if minutes > 1 else ''}."
        else:
            hours = int(retry_after_seconds / 3600)
            response["error"]["retry_message"] = f"Try again in {hours} hour{'s' if hours > 1 else ''}."
    
    if tier:
        response["error"]["tier"] = tier
        response["error"]["upgrade_hint"] = "Upgrade your plan for higher limits."
    
    return response


# Example responses

# Request limit exceeded
print(create_rate_limit_response(
    reason="rate_limit",
    limit_type="request",
    limit_value=100,
    current_usage=100,
    retry_after_seconds=45,
    tier="free",
))

# Token limit exceeded  
print(create_rate_limit_response(
    reason="rate_limit",
    limit_type="token",
    limit_value=100000,
    current_usage=100000,
    retry_after_seconds=1800,
    tier="basic",
))
```

---

## Complete Rate Limiter: Combining Everything

```python
import time
import threading
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum

@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    reason: Optional[str] = None
    limit_type: Optional[str] = None
    retry_after_seconds: Optional[float] = None
    message: Optional[str] = None
    user_status: Optional[dict] = None
    headers: Optional[dict] = None


class ComprehensiveRateLimiter:
    """
    Production rate limiter combining:
    - Global limits (system protection)
    - Per-user limits (fairness)
    - Tiered limits (business model)
    - Cost-based limits (budget control)
    
    Checks in order:
    1. Emergency shutdown
    2. Global request rate
    3. Global cost limits
    4. User tier access (model allowed?)
    5. User request limit
    6. User token limit
    7. User cost limit
    """
    
    def __init__(
        self,
        # Global limits
        global_rpm: int = 1000,
        global_cost_per_hour: float = 100.0,
        global_cost_per_day: float = 1000.0,
        emergency_threshold: float = 500.0,
    ):
        # Global limiter
        self.global_limiter = GlobalRateLimiter(
            max_requests_per_minute=global_rpm,
            max_cost_per_hour=global_cost_per_hour,
            max_cost_per_day=global_cost_per_day,
            emergency_shutdown_threshold=emergency_threshold,
        )
        
        # Tiered limiter (handles per-user limits)
        self.tiered_limiter = TieredRateLimiter()
        
        self.lock = threading.Lock()
    
    def set_user_tier(self, user_id: str, tier: UserTier) -> None:
        """Set user's tier."""
        self.tiered_limiter.set_user_tier(user_id, tier)
    
    def check_request(
        self,
        user_id: str,
        model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        estimated_cost: float,
    ) -> RateLimitResult:
        """
        Comprehensive rate limit check.
        
        Call this BEFORE making an API request.
        """
        # 1. Check global limits first
        global_allowed, global_info = self.global_limiter.check_global_limits(estimated_cost)
        
        if not global_allowed:
            return RateLimitResult(
                allowed=False,
                reason=global_info["reason"],
                limit_type="global",
                retry_after_seconds=global_info.get("retry_after_seconds"),
                message=global_info["message"],
            )
        
        # 2. Check user limits
        estimated_total_tokens = estimated_input_tokens + estimated_output_tokens
        user_allowed, user_info = self.tiered_limiter.check_limits(
            user_id=user_id,
            estimated_tokens=estimated_total_tokens,
            estimated_cost=estimated_cost,
            model=model,
        )
        
        if not user_allowed:
            return RateLimitResult(
                allowed=False,
                reason=user_info["reason"],
                limit_type="user",
                retry_after_seconds=user_info.get("retry_after_seconds"),
                message=user_info["message"],
                headers=create_rate_limit_headers(
                    limit=self.tiered_limiter.get_limits(user_id).requests_per_day,
                    remaining=user_info.get("limits", {}).get("requests_remaining", 0),
                ),
            )
        
        # 3. All checks passed
        user_status = self.tiered_limiter.get_user_status(user_id)
        
        return RateLimitResult(
            allowed=True,
            user_status=user_status,
            headers=create_rate_limit_headers(
                limit=user_status["requests"]["limit"],
                remaining=user_status["requests"]["remaining"],
            ),
        )
    
    def record_request(
        self,
        user_id: str,
        actual_tokens: int,
        actual_cost: float,
    ) -> None:
        """Record a completed request."""
        # Record globally
        self.global_limiter.record_request(actual_cost)
        
        # Record for user
        self.tiered_limiter.record_usage(
            user_id=user_id,
            tokens=actual_tokens,
            cost=actual_cost,
        )
    
    def get_user_status(self, user_id: str) -> dict:
        """Get user's current limit status."""
        return self.tiered_limiter.get_user_status(user_id)
    
    def get_system_status(self) -> dict:
        """Get system-wide status."""
        return self.global_limiter.get_system_status()


# Usage example
rate_limiter = ComprehensiveRateLimiter(
    global_rpm=1000,
    global_cost_per_hour=100.0,
)

# Set up a user
rate_limiter.set_user_tier("user_123", UserTier.BASIC)

# Check before request
result = rate_limiter.check_request(
    user_id="user_123",
    model="gpt-4o-mini",
    estimated_input_tokens=1000,
    estimated_output_tokens=300,
    estimated_cost=0.001,
)

if result.allowed:
    print("Request allowed!")
    print(f"Remaining requests: {result.user_status['requests']['remaining']}")
    
    # Make API call...
    # actual_cost = ...
    
    # Record usage
    rate_limiter.record_request(
        user_id="user_123",
        actual_tokens=1300,
        actual_cost=0.0012,
    )
else:
    print(f"Request blocked: {result.message}")
    if result.retry_after_seconds:
        print(f"Retry after: {result.retry_after_seconds} seconds")
```

---

## Cost-Based Limits: The Most Important Limit

Request counts and token counts are proxies. Cost is what actually matters for LLM systems.

```
Request-based problem:
  10 classification requests: $0.001 total
  10 report generation requests: $0.50 total
  Same request count, 500x cost difference

Token-based problem:
  100,000 tokens on gpt-4o-mini: ~$0.06
  100,000 tokens on gpt-4o: ~$1.00
  Same token count, 16x cost difference

Cost-based solution:
  $5/day limit
  Works regardless of request type or model
  Directly maps to your budget
```

The cost-based limit should be your primary defense. Request and token limits are secondary guardrails.

---

## Key Takeaways

1. **Layer your limits**: Global → Per-user → Tiered → Cost-based
    
2. **Token bucket for request rate limiting**: Allows bursts while maintaining sustained rate
    
3. **Cost-based limits are most accurate** for LLM systems where requests vary wildly
    
4. **Clear error responses**: Include retry-after, remaining limits, and upgrade hints
    
5. **Emergency shutdown**: Have a circuit breaker for when costs spiral
    
6. **Track everything**: You need visibility into what's being consumed
    
7. **Headers matter**: Use standard `X-RateLimit-*` and `Retry-After` headers
    

---

## What's Next

With rate limiting in place, the next note covers:

- **Note 5**: Graceful degradation when limits hit

---

## References

- Token Bucket Algorithm: https://en.wikipedia.org/wiki/Token_bucket
- Rate Limiting Best Practices: https://cloud.google.com/architecture/rate-limiting-strategies-techniques
- HTTP Rate Limit Headers: https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/