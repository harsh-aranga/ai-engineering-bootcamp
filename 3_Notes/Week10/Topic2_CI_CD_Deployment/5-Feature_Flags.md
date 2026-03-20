# Feature Flags: Decoupling Deployment from Release

## The Core Insight: Deployment ≠ Release

Most teams conflate two distinct concepts:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DEPLOYMENT VS RELEASE                                    │
│                                                                              │
│   DEPLOYMENT: Code reaches production servers                               │
│   - Technical operation                                                     │
│   - Happens when CI/CD pipeline completes                                   │
│   - Binary: code is deployed or not                                         │
│                                                                              │
│   RELEASE: Feature reaches users                                            │
│   - Business operation                                                      │
│   - Happens when feature is enabled                                         │
│   - Gradual: 0% → 10% → 50% → 100%                                          │
│                                                                              │
│   Traditional approach: deployment = release                                │
│   - Deploy code → everyone gets feature immediately                         │
│   - Rollback = redeploy previous version                                    │
│                                                                              │
│   Feature flag approach: deployment ≠ release                               │
│   - Deploy code → feature is OFF                                            │
│   - Enable flag → feature reaches users (gradually)                         │
│   - Rollback = disable flag (instant)                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

This separation gives you:

- **Instant rollback**: Disable flag, no redeployment
- **Gradual rollout**: Test with 1% before 100%
- **Testing in production**: Enable for internal users first
- **Decoupled timelines**: Deploy Monday, release Thursday

---

## How Feature Flags Work

At its core, a feature flag is a conditional:

```python
def process_query(query: str, user_id: str) -> str:
    if feature_flags.is_enabled("new_rag_pipeline", user_id):
        return new_rag_pipeline(query)
    else:
        return old_rag_pipeline(query)
```

The power comes from controlling that conditional externally—without code changes.

### The Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FEATURE FLAG LIFECYCLE                                   │
│                                                                              │
│   1. CREATE FLAG                                                            │
│      Name: "new_rag_pipeline"                                               │
│      State: OFF (0% of users)                                               │
│                                                                              │
│   2. DEPLOY CODE                                                            │
│      Code deployed with flag check                                          │
│      Flag is OFF → all users get old pipeline                               │
│                                                                              │
│   3. INTERNAL TESTING                                                       │
│      Enable for user_ids: ["alice@company.com", "bob@company.com"]          │
│      Internal team tests in production                                      │
│                                                                              │
│   4. GRADUAL ROLLOUT                                                        │
│      1% of users → monitor → 10% → monitor → 50% → monitor → 100%           │
│      At any point: disable flag → instant rollback                          │
│                                                                              │
│   5. CLEANUP                                                                │
│      Flag at 100% for 2 weeks, no issues                                    │
│      Remove flag and old code path                                          │
│      Technical debt reduced                                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Flag Types

Not all flags serve the same purpose. Different types have different lifecycles and management needs.

### Release Flags

**Purpose**: Gradual rollout of new features.

```python
if flags.is_enabled("new_search_ui", user_id):
    return render_new_search_ui()
else:
    return render_old_search_ui()
```

**Lifecycle**: Short (days to weeks). Remove after full rollout.

### Experiment Flags

**Purpose**: A/B testing to measure impact.

```python
variant = flags.get_variant("pricing_experiment", user_id)
# Returns: "control", "variant_a", or "variant_b"

if variant == "control":
    return show_original_pricing()
elif variant == "variant_a":
    return show_discounted_pricing()
else:
    return show_tiered_pricing()
```

**Lifecycle**: Short (duration of experiment). Remove after decision.

### Ops Flags

**Purpose**: Operational controls—kill switches, degradation modes.

```python
if flags.is_enabled("enable_llm_cache"):
    return cached_llm_call(prompt)
else:
    return llm_call(prompt)  # Direct call, no cache

# Kill switch for expensive feature
if flags.is_enabled("enable_deep_research"):
    return deep_research(query)  # Expensive
else:
    return quick_search(query)  # Cheap fallback
```

**Lifecycle**: Long-lived. These stay in the codebase permanently.

### Permission Flags

**Purpose**: Feature access by user tier or entitlement.

```python
if flags.is_enabled("premium_features", user_id):
    return render_premium_dashboard()
else:
    return render_basic_dashboard()
```

**Lifecycle**: Permanent. Tied to business logic, not release cycle.

### Flag Type Summary

|Type|Purpose|Lifecycle|Remove After|
|---|---|---|---|
|**Release**|Gradual rollout|Days-weeks|Full rollout|
|**Experiment**|A/B testing|Experiment duration|Decision made|
|**Ops**|Kill switches|Permanent|Never|
|**Permission**|Access control|Permanent|Never|

---

## Targeting Strategies

How do you decide which users see the feature?

### Percentage Rollout

Enable for X% of all users, randomly distributed.

```python
# 10% of users get the feature
{
    "flag": "new_rag_pipeline",
    "rollout_percentage": 10
}
```

**Important**: Use consistent hashing so the same user always gets the same experience:

```python
import hashlib

def is_enabled_for_user(flag_name: str, user_id: str, percentage: int) -> bool:
    # Hash user_id + flag_name for consistent assignment
    hash_input = f"{flag_name}:{user_id}"
    hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
    bucket = hash_value % 100
    return bucket < percentage

# User "alice" will consistently be in or out of the 10%
# across all requests, not randomly changing
```

### User ID Targeting

Enable for specific users (internal testing, beta testers).

```python
{
    "flag": "new_rag_pipeline",
    "enabled_users": ["alice@company.com", "bob@company.com"],
    "rollout_percentage": 0  # Only enabled_users get it
}
```

### Environment Targeting

Different behavior in staging vs production.

```python
{
    "flag": "new_rag_pipeline",
    "environments": {
        "staging": {"enabled": true},
        "production": {"enabled": false}
    }
}
```

### Custom Rules

Complex targeting based on user attributes.

```python
{
    "flag": "new_rag_pipeline",
    "rules": [
        {
            "condition": "user.plan == 'enterprise'",
            "enabled": true
        },
        {
            "condition": "user.country in ['US', 'CA']",
            "enabled": true,
            "percentage": 50
        },
        {
            "default": false
        }
    ]
}
```

### Targeting Priority

Typical evaluation order:

```
1. Check if user is in enabled_users list → YES → enabled
2. Check environment rules → match → return that value
3. Check custom rules in order → first match wins
4. Apply percentage rollout
5. Return default (usually false)
```

---

## Implementation Options

Feature flags can be implemented at different complexity levels.

### Option 1: Environment Variables (Simplest)

```python
import os

def is_feature_enabled(flag_name: str) -> bool:
    return os.getenv(f"FEATURE_{flag_name.upper()}", "false").lower() == "true"

# Usage
if is_feature_enabled("new_rag_pipeline"):
    ...
```

**Pros**: No dependencies, trivial to implement. **Cons**: No gradual rollout, no user targeting, requires redeploy to change.

### Option 2: Config File

```yaml
# feature_flags.yaml
flags:
  new_rag_pipeline:
    enabled: false
    rollout_percentage: 0
    enabled_users:
      - alice@company.com
      
  premium_features:
    enabled: true
    rollout_percentage: 100
```

```python
import yaml
import hashlib

class FlagManager:
    def __init__(self, config_path: str = "feature_flags.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.flags = self.config.get("flags", {})
    
    def is_enabled(self, flag_name: str, user_id: str | None = None) -> bool:
        flag = self.flags.get(flag_name, {})
        
        # Check if globally disabled
        if not flag.get("enabled", False):
            return False
        
        # Check enabled_users list
        enabled_users = flag.get("enabled_users", [])
        if user_id and user_id in enabled_users:
            return True
        
        # Check percentage rollout
        percentage = flag.get("rollout_percentage", 100)
        if percentage >= 100:
            return True
        if percentage <= 0:
            return len(enabled_users) > 0 and user_id in enabled_users
        
        # Consistent hashing for percentage
        if user_id:
            hash_input = f"{flag_name}:{user_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            bucket = hash_value % 100
            return bucket < percentage
        
        return False

# Usage
flags = FlagManager()
if flags.is_enabled("new_rag_pipeline", user_id="alice@company.com"):
    ...
```

**Pros**: User targeting, percentage rollout, no external dependencies. **Cons**: Requires redeploy to change flags (unless hot-reload config).

### Option 3: Database-Backed

Store flags in database. Hot reload without redeploy.

```python
from sqlalchemy import Column, String, Boolean, Integer, JSON
from sqlalchemy.orm import Session

class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    
    name = Column(String, primary_key=True)
    enabled = Column(Boolean, default=False)
    rollout_percentage = Column(Integer, default=0)
    enabled_users = Column(JSON, default=list)
    rules = Column(JSON, default=list)

class FlagManager:
    def __init__(self, db: Session):
        self.db = db
        self._cache = {}
        self._cache_ttl = 60  # seconds
    
    def _get_flag(self, flag_name: str) -> FeatureFlag | None:
        # Add caching to avoid DB hit on every check
        return self.db.query(FeatureFlag).filter_by(name=flag_name).first()
    
    def is_enabled(self, flag_name: str, user_id: str | None = None) -> bool:
        flag = self._get_flag(flag_name)
        if not flag or not flag.enabled:
            return False
        
        # Check enabled_users
        if user_id and user_id in (flag.enabled_users or []):
            return True
        
        # Check percentage rollout
        if flag.rollout_percentage >= 100:
            return True
        if flag.rollout_percentage <= 0:
            return False
        
        # Consistent hashing
        if user_id:
            hash_input = f"{flag_name}:{user_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            bucket = hash_value % 100
            return bucket < flag.rollout_percentage
        
        return False
```

**Pros**: Change flags without redeploy, audit trail, admin UI possible. **Cons**: Database dependency, need to handle caching, more infrastructure.

### Option 4: Feature Flag Service

Dedicated services: LaunchDarkly, Unleash, Flagsmith, Split.

```python
# LaunchDarkly example
import ldclient
from ldclient.config import Config

ldclient.set_config(Config("your-sdk-key"))
client = ldclient.get()

def is_enabled(flag_name: str, user_id: str) -> bool:
    context = ldclient.Context.builder(user_id).build()
    return client.variation(flag_name, context, False)

# Usage
if is_enabled("new_rag_pipeline", user_id):
    ...
```

**Pros**: Full-featured (targeting, analytics, audit logs), managed infrastructure, SDKs for all languages. **Cons**: Cost ($), external dependency, vendor lock-in.

### Option Comparison

|Option|Complexity|Capabilities|Change Without Deploy|Cost|
|---|---|---|---|---|
|**Env vars**|Minimal|Basic on/off|No|Free|
|**Config file**|Low|Targeting, % rollout|No (unless hot reload)|Free|
|**Database**|Medium|Full targeting|Yes|Free (self-hosted)|
|**Service**|Low (managed)|Full + analytics|Yes|$$|

**Recommendation for bootcamp**: Start with config file. Graduate to database or service when you need dynamic control.

---

## Simple Implementation

Here's a production-ready config-based implementation:

```yaml
# config/feature_flags.yaml
flags:
  new_rag_pipeline:
    description: "New RAG pipeline with hybrid search"
    enabled: true
    rollout_percentage: 10
    enabled_users:
      - alice@company.com
      - bob@company.com
    created_at: "2025-03-01"
    cleanup_by: "2025-04-01"  # Track flag age
    
  experimental_agent:
    description: "Multi-step research agent"
    enabled: true
    rollout_percentage: 0
    enabled_users:
      - internal-testers
    created_at: "2025-03-15"
    cleanup_by: "2025-04-15"
    
  enable_llm_cache:
    description: "Cache LLM responses"
    enabled: true
    rollout_percentage: 100
    type: ops  # Ops flag, no cleanup needed
```

```python
# src/feature_flags.py
import hashlib
import yaml
from pathlib import Path
from typing import Any
from functools import lru_cache
import time

class FeatureFlags:
    def __init__(self, config_path: str = "config/feature_flags.yaml"):
        self.config_path = Path(config_path)
        self._load_config()
        self._last_load = time.time()
        self._reload_interval = 60  # Reload config every 60 seconds
    
    def _load_config(self) -> None:
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        self.flags = config.get("flags", {})
    
    def _maybe_reload(self) -> None:
        """Hot reload config if interval passed."""
        if time.time() - self._last_load > self._reload_interval:
            self._load_config()
            self._last_load = time.time()
    
    def is_enabled(
        self, 
        flag_name: str, 
        user_id: str | None = None,
        default: bool = False
    ) -> bool:
        """
        Check if a feature flag is enabled for a user.
        
        Args:
            flag_name: Name of the feature flag
            user_id: User identifier for targeting
            default: Default value if flag doesn't exist
            
        Returns:
            True if feature is enabled for this user
        """
        self._maybe_reload()
        
        flag = self.flags.get(flag_name)
        if flag is None:
            return default
        
        # Check if globally enabled
        if not flag.get("enabled", False):
            return False
        
        # Check enabled_users list
        enabled_users = flag.get("enabled_users", [])
        if user_id and user_id in enabled_users:
            return True
        
        # Check percentage rollout
        percentage = flag.get("rollout_percentage", 100)
        
        if percentage >= 100:
            return True
        if percentage <= 0:
            # Only enabled for explicit users
            return False
        
        # Consistent hashing for percentage rollout
        if user_id:
            return self._in_rollout_percentage(flag_name, user_id, percentage)
        
        return False
    
    def _in_rollout_percentage(
        self, 
        flag_name: str, 
        user_id: str, 
        percentage: int
    ) -> bool:
        """
        Determine if user is in rollout percentage using consistent hashing.
        Same user always gets same result for same flag.
        """
        hash_input = f"{flag_name}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100
        return bucket < percentage
    
    def get_all_flags(self) -> dict[str, Any]:
        """Return all flag configurations (for admin/debugging)."""
        self._maybe_reload()
        return self.flags.copy()
    
    def get_stale_flags(self, days: int = 30) -> list[str]:
        """Return flags past their cleanup_by date."""
        from datetime import datetime, timedelta
        
        stale = []
        cutoff = datetime.now() - timedelta(days=days)
        
        for name, config in self.flags.items():
            cleanup_by = config.get("cleanup_by")
            if cleanup_by:
                cleanup_date = datetime.fromisoformat(cleanup_by)
                if cleanup_date < cutoff:
                    stale.append(name)
        
        return stale


# Global instance
_flags: FeatureFlags | None = None

def get_flags() -> FeatureFlags:
    global _flags
    if _flags is None:
        _flags = FeatureFlags()
    return _flags

def is_enabled(flag_name: str, user_id: str | None = None) -> bool:
    """Convenience function for flag checking."""
    return get_flags().is_enabled(flag_name, user_id)
```

Usage in application:

```python
from feature_flags import is_enabled

def process_query(query: str, user_id: str) -> str:
    if is_enabled("new_rag_pipeline", user_id):
        return new_rag_pipeline(query)
    else:
        return old_rag_pipeline(query)
```

---

## The Cleanup Problem

Feature flags accumulate. Without discipline, your codebase becomes:

```python
# After 6 months of flags...
def process_query(query: str, user_id: str) -> str:
    if is_enabled("new_rag_v3", user_id):
        if is_enabled("enhanced_retrieval", user_id):
            if is_enabled("experimental_reranker", user_id):
                return newest_pipeline(query)
            else:
                return enhanced_pipeline_v2(query)
        else:
            return enhanced_pipeline_v1(query)
    elif is_enabled("new_rag_v2", user_id):
        # Old flag, should have been removed
        return old_enhanced_pipeline(query)
    else:
        return legacy_pipeline(query)  # Does anyone use this?
```

This is technical debt. Every flag is a branch in your code that must be maintained.

### Prevention Strategies

**1. Set cleanup dates when creating flags:**

```yaml
new_rag_pipeline:
  description: "New RAG pipeline with hybrid search"
  enabled: true
  rollout_percentage: 100
  created_at: "2025-03-01"
  cleanup_by: "2025-04-01"  # 30 days after creation
```

**2. Alert on stale flags:**

```python
# In your CI or monitoring
stale_flags = flags.get_stale_flags(days=30)
if stale_flags:
    send_alert(f"Stale feature flags need cleanup: {stale_flags}")
```

**3. Track flag count as a metric:**

```python
# Monitor flag proliferation
flag_count = len(flags.get_all_flags())
metrics.gauge("feature_flags.total_count", flag_count)
```

**4. Regular cleanup sprints:**

Schedule quarterly "flag cleanup" sessions:

- Review all flags
- Remove flags at 100% for > 30 days
- Delete associated old code paths

**5. Flag removal checklist:**

```markdown
## Feature Flag Removal: [flag_name]

- [ ] Flag at 100% rollout
- [ ] No issues for 14+ days
- [ ] Remove flag check from code
- [ ] Remove old code path
- [ ] Remove flag from config
- [ ] Update tests
- [ ] Deploy
```

---

## AI-Specific Flag Uses

Feature flags are particularly valuable for AI applications where behavior changes are risky.

### Model Testing

Gate model selection with flags:

```python
def get_model() -> str:
    if is_enabled("use_gpt4o_latest", user_id):
        return "gpt-4o-2024-11-20"  # New model
    else:
        return "gpt-4o-2024-08-06"  # Stable model
```

**Rollout**: Test new model with 1% of users. Monitor quality metrics. Gradually increase.

### Prompt Experiments

Gate prompt versions:

```python
PROMPTS = {
    "v1": "You are a helpful research assistant.",
    "v2": "You are a research assistant. Always cite sources. Be concise."
}

def get_system_prompt(user_id: str) -> str:
    if is_enabled("prompt_v2", user_id):
        return PROMPTS["v2"]
    return PROMPTS["v1"]
```

**Rollout**: A/B test prompts. Measure response quality, user satisfaction.

### Feature Rollout

Gate new capabilities:

```python
def handle_query(query: str, user_id: str) -> str:
    if is_enabled("multi_step_agent", user_id):
        return run_multi_step_agent(query)
    else:
        return run_simple_rag(query)
```

**Rollout**: New agent capability to internal users first, then beta testers, then general availability.

### Graceful Degradation

Ops flags for cost/performance control:

```python
def process_query(query: str, user_id: str) -> str:
    # Kill switch for expensive deep research
    if not is_enabled("enable_deep_research"):
        return quick_search(query)  # Cheap fallback
    
    # Normal path
    if query_needs_deep_research(query):
        return deep_research(query)
    return standard_search(query)
```

**Use case**: Disable expensive features during traffic spikes or cost overruns.

```python
# Degradation ladder
def get_retrieval_config() -> dict:
    if not is_enabled("ops_full_retrieval"):
        # Degraded mode: fewer chunks, no reranking
        return {"top_k": 3, "rerank": False}
    
    if not is_enabled("ops_reranking"):
        # Partial degradation: no reranking
        return {"top_k": 10, "rerank": False}
    
    # Full capability
    return {"top_k": 10, "rerank": True}
```

### AI Flag Summary

|Use Case|Flag Type|Lifecycle|Example|
|---|---|---|---|
|**New model**|Release|Weeks|`use_gpt4o_latest`|
|**Prompt version**|Experiment|Days-weeks|`prompt_v2`|
|**New capability**|Release|Weeks|`multi_step_agent`|
|**Kill switch**|Ops|Permanent|`enable_deep_research`|
|**Degradation**|Ops|Permanent|`ops_reranking`|

---

## Key Takeaways

1. **Deployment ≠ Release**: Feature flags let you deploy code without releasing it to users.
    
2. **Instant rollback**: Disable flag, feature disappears. No redeploy needed.
    
3. **Gradual rollout**: 1% → 10% → 50% → 100%. Catch problems early.
    
4. **Flag types serve different purposes**:
    
    - Release: gradual rollout (temporary)
    - Experiment: A/B testing (temporary)
    - Ops: kill switches (permanent)
    - Permission: access control (permanent)
5. **Targeting strategies**:
    
    - Percentage rollout with consistent hashing
    - User ID targeting for internal testing
    - Custom rules for complex conditions
6. **Start simple, scale up**:
    
    - Config file for most teams
    - Database for dynamic control
    - Service (LaunchDarkly) for enterprise needs
7. **Cleanup is critical**: Set cleanup dates, alert on stale flags, schedule removal sprints.
    
8. **AI-specific value**:
    
    - Model testing without full deployment
    - Prompt experiments with measurement
    - Graceful degradation when needed

---

## Summary: Days 3-4 CI/CD + Deployment

You now have a complete mental model for shipping AI applications safely:

|Note|Topic|Key Concept|
|---|---|---|
|1|CI/CD Pipeline|Code → Build → Test → Deploy → Monitor|
|2|GitHub Actions|Workflow → Jobs → Steps (YAML automation)|
|3|Deployment Strategies|Blue-Green (instant rollback) vs Canary (gradual)|
|4|Rollback|Automatic triggers + multiple mechanisms|
|5|Feature Flags|Deployment ≠ Release, instant control|

The flow for production AI deployment:

```
Code change → CI runs tests → Build Docker image → 
Deploy behind feature flag (OFF) → Enable for internal → 
Gradual rollout → Monitor → 100% or rollback → 
Cleanup flag after stable
```

This is how mature AI teams ship: safely, gradually, with the ability to undo anything instantly.