# Cache Invalidation and Maintenance

## The Hard Problem

> "There are only two hard things in Computer Science: cache invalidation and naming things." — Phil Karlton

The fundamental challenge: **how do you know when cached data is stale?**

In LLM/RAG systems, a cached answer becomes stale when:

- The source documents change
- The model is updated
- The prompt/system instructions change
- The retrieval configuration changes
- Business rules or policies change

The cache doesn't know any of this happened. It happily returns yesterday's answer to today's question, even if yesterday's answer is now wrong.

```
Monday:
  User: "What's our return window?"
  System: Retrieves policy.md → "30 days"
  Cache: Stores answer

Tuesday:
  Admin: Updates policy.md → "14 days"
  
Wednesday:
  User: "What's our return window?"
  Cache: HIT → Returns "30 days"  ← WRONG!
```

The cache saved latency and cost, but delivered incorrect information. This is the cache invalidation problem.

---

## Invalidation Strategies

There are four main approaches, each with different trade-offs:

### 1. TTL-Based Invalidation

**How it works**: Every cache entry expires after a fixed time.

```python
cache.set(
    query="What's our return policy?",
    result={"answer": "30 days..."},
    ttl=3600  # Expire after 1 hour
)

# After 1 hour, entry is automatically invalid
# Next query computes fresh answer
```

**Pros:**

- Simple to implement
- Predictable behavior
- No tracking required

**Cons:**

- Doesn't react to actual changes
- Either stale (long TTL) or inefficient (short TTL)
- Data might change 5 minutes after caching

**When to use:**

- Data changes on predictable schedule (daily updates)
- Cost of occasional stale answer is low
- You can't track document changes

**TTL Selection Guidelines:**

|Data Volatility|TTL|Example|
|---|---|---|
|Real-time|0 (no cache)|Stock prices|
|Frequent changes|1-15 min|Inventory levels|
|Daily updates|1-4 hours|News, reports|
|Weekly changes|12-24 hours|Policies, docs|
|Stable content|1-7 days|FAQs, guides|

### 2. Event-Based Invalidation

**How it works**: Track which documents each cached answer used. When a document changes, invalidate all cache entries that depended on it.

```python
# When caching, record which docs were used
cache.set(
    query="What's our return policy?",
    result={"answer": "30 days..."},
    tags=["doc:policy.md", "doc:returns_faq.md"]
)

# When a document is updated
def on_document_update(doc_id: str):
    cache.invalidate_by_tag(f"doc:{doc_id}")

# Updating policy.md triggers invalidation
on_document_update("policy.md")
# → Removes all cache entries tagged with "doc:policy.md"
```

**Pros:**

- Invalidates exactly when needed
- No unnecessary expirations
- Accurate to actual data changes

**Cons:**

- Complex to implement
- Requires tracking document dependencies
- Must integrate with document update pipeline

**When to use:**

- You control the document update pipeline
- Stale answers have real cost (customer support, compliance)
- Documents change unpredictably

### 3. Version-Based Invalidation

**How it works**: Include version identifiers in the cache key. When versions change, old cache entries simply don't match.

```python
def create_versioned_cache_key(
    query: str,
    doc_version: str,
    model_version: str,
    prompt_version: str
) -> str:
    """
    Cache key that incorporates all version dependencies.
    
    Any version change = automatic cache miss = fresh computation.
    """
    key_data = {
        "query": query.lower().strip(),
        "doc_version": doc_version,      # Hash of document corpus
        "model_version": model_version,   # e.g., "gpt-4o-2024-08-06"
        "prompt_version": prompt_version  # Hash of system prompt
    }
    return hashlib.sha256(
        json.dumps(key_data, sort_keys=True).encode()
    ).hexdigest()


# Monday: doc_version = "abc123"
key = create_versioned_cache_key(
    "What's our return policy?",
    doc_version="abc123",
    model_version="gpt-4o",
    prompt_version="v2"
)
# → "7f8a9b..."
# Cache: MISS → compute → store

# Tuesday: document updated, doc_version = "def456"
key = create_versioned_cache_key(
    "What's our return policy?",  # Same query
    doc_version="def456",          # Different version!
    model_version="gpt-4o",
    prompt_version="v2"
)
# → "3c4d5e..."  ← Different key!
# Cache: MISS → fresh computation
```

**Pros:**

- Elegant—version change automatically invalidates
- Works for any versioned dependency
- No explicit invalidation logic needed

**Cons:**

- Requires version tracking infrastructure
- Computing document corpus version can be expensive
- Old entries sit in cache until evicted (waste space)

**When to use:**

- You have version control for documents
- Multiple dependencies affect cache validity
- You want implicit invalidation without explicit calls

### 4. Manual Purge

**How it works**: Admin explicitly clears cache when they know data is stale.

```python
# Clear specific entry
cache.invalidate(query="What's our return policy?")

# Clear entries matching pattern
cache.invalidate_by_prefix("policy:")

# Clear entire cache
cache.clear()
```

**Pros:**

- Simple to implement
- Human judgment on when to invalidate
- Good for deployments and major changes

**Cons:**

- Requires human intervention
- Easy to forget
- Can cause traffic spike (cold cache)

**When to use:**

- Rare, major updates (new product launch)
- After deployments
- Emergency corrections
- As backup when other strategies fail

---

## Tagging Cache Entries

Tags enable surgical invalidation—removing exactly the entries affected by a change.

### Implementation

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json


@dataclass
class TaggedCacheEntry:
    """Cache entry with dependency tags."""
    key: str
    value: dict
    tags: set[str]
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)


class TaggedCache:
    """
    Cache with tag-based invalidation.
    
    Tags represent dependencies (documents, configs, etc.).
    Invalidating a tag removes all entries with that tag.
    """
    
    def __init__(self, default_ttl: int = 3600):
        self.entries: dict[str, TaggedCacheEntry] = {}
        self.tag_index: dict[str, set[str]] = {}  # tag → set of cache keys
        self.default_ttl = default_ttl
    
    def _create_key(self, query: str, config: dict | None = None) -> str:
        key_data = {"query": query.lower().strip(), "config": config or {}}
        return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    def set(
        self,
        query: str,
        result: dict,
        tags: list[str] | None = None,
        config: dict | None = None,
        ttl: int | None = None
    ) -> None:
        """
        Store entry with tags for later invalidation.
        
        Args:
            query: The query string
            result: The result to cache
            tags: Dependency tags (e.g., ["doc:policy.md", "model:gpt-4o"])
            config: Configuration for cache key
            ttl: Optional TTL override
        """
        key = self._create_key(query, config)
        tags_set = set(tags) if tags else set()
        ttl = ttl or self.default_ttl
        
        entry = TaggedCacheEntry(
            key=key,
            value=result,
            tags=tags_set,
            expires_at=datetime.now() + timedelta(seconds=ttl)
        )
        
        # Store entry
        self.entries[key] = entry
        
        # Update tag index
        for tag in tags_set:
            if tag not in self.tag_index:
                self.tag_index[tag] = set()
            self.tag_index[tag].add(key)
    
    def get(self, query: str, config: dict | None = None) -> dict | None:
        """Get cached entry if exists and not expired."""
        key = self._create_key(query, config)
        
        if key not in self.entries:
            return None
        
        entry = self.entries[key]
        
        if datetime.now() > entry.expires_at:
            self._remove_entry(key)
            return None
        
        return entry.value
    
    def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate all entries with this tag.
        
        Returns:
            Number of entries invalidated.
        """
        if tag not in self.tag_index:
            return 0
        
        keys_to_remove = list(self.tag_index[tag])
        
        for key in keys_to_remove:
            self._remove_entry(key)
        
        return len(keys_to_remove)
    
    def invalidate_by_tags(self, tags: list[str]) -> int:
        """Invalidate entries matching ANY of the tags."""
        count = 0
        for tag in tags:
            count += self.invalidate_by_tag(tag)
        return count
    
    def _remove_entry(self, key: str) -> None:
        """Remove entry and clean up tag index."""
        if key not in self.entries:
            return
        
        entry = self.entries[key]
        
        # Remove from tag index
        for tag in entry.tags:
            if tag in self.tag_index:
                self.tag_index[tag].discard(key)
                if not self.tag_index[tag]:
                    del self.tag_index[tag]
        
        # Remove entry
        del self.entries[key]
    
    def get_tags_stats(self) -> dict[str, int]:
        """Get count of entries per tag."""
        return {tag: len(keys) for tag, keys in self.tag_index.items()}
```

### Usage Pattern

```python
cache = TaggedCache(default_ttl=3600)

# Cache with document tags
cache.set(
    query="What's our return policy?",
    result={"answer": "30 days...", "sources": ["policy.md"]},
    tags=["doc:policy.md", "doc:returns_faq.md", "model:gpt-4o"]
)

cache.set(
    query="How do I ship internationally?",
    result={"answer": "We ship to...", "sources": ["shipping.md"]},
    tags=["doc:shipping.md", "model:gpt-4o"]
)

# Document update triggers invalidation
def on_document_update(doc_path: str):
    """Called when a document is updated."""
    invalidated = cache.invalidate_by_tag(f"doc:{doc_path}")
    print(f"Invalidated {invalidated} cache entries for {doc_path}")

on_document_update("policy.md")
# → Invalidated 1 cache entries for policy.md
# "What's our return policy?" entry removed
# "How do I ship internationally?" entry still valid

# Model upgrade triggers invalidation
def on_model_upgrade(old_model: str, new_model: str):
    """Called when switching to a new model."""
    invalidated = cache.invalidate_by_tag(f"model:{old_model}")
    print(f"Invalidated {invalidated} entries for model {old_model}")

on_model_upgrade("gpt-4o", "gpt-4o-2024-11-20")
# → Invalidates all entries tagged with old model
```

### Tag Naming Conventions

Consistent tag naming makes invalidation predictable:

|Dependency Type|Tag Format|Example|
|---|---|---|
|Document|`doc:{path}`|`doc:policies/returns.md`|
|Document version|`doc_v:{path}:{hash}`|`doc_v:returns.md:abc123`|
|Model|`model:{name}`|`model:gpt-4o`|
|Prompt template|`prompt:{name}:{version}`|`prompt:support:v3`|
|Config|`config:{key}`|`config:retrieval_k`|
|User segment|`segment:{name}`|`segment:enterprise`|

---

## Cache Size Management

Unbounded caches eventually exhaust memory. You need eviction policies.

### Eviction Strategies

**LRU (Least Recently Used):** Remove entries that haven't been accessed recently.

```python
from collections import OrderedDict


class LRUCache:
    """Cache with LRU eviction."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.cache = OrderedDict()  # Maintains insertion/access order
    
    def get(self, key: str) -> dict | None:
        if key not in self.cache:
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        
        entry = self.cache[key]
        if datetime.now() > entry["expires_at"]:
            del self.cache[key]
            return None
        
        return entry["value"]
    
    def set(self, key: str, value: dict, ttl: int = 3600) -> None:
        # Evict oldest if at capacity
        while len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)  # Remove oldest
        
        self.cache[key] = {
            "value": value,
            "expires_at": datetime.now() + timedelta(seconds=ttl)
        }
        self.cache.move_to_end(key)  # Mark as most recently used
```

**LFU (Least Frequently Used):** Remove entries that have been accessed least often.

```python
import heapq
from dataclasses import dataclass, field


@dataclass(order=True)
class LFUEntry:
    """Entry sortable by access frequency."""
    frequency: int
    last_access: datetime = field(compare=False)
    key: str = field(compare=False)
    value: dict = field(compare=False)
    expires_at: datetime = field(compare=False)


class LFUCache:
    """Cache with LFU eviction."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.entries: dict[str, LFUEntry] = {}
    
    def get(self, key: str) -> dict | None:
        if key not in self.entries:
            return None
        
        entry = self.entries[key]
        
        if datetime.now() > entry.expires_at:
            del self.entries[key]
            return None
        
        # Increment frequency
        entry.frequency += 1
        entry.last_access = datetime.now()
        
        return entry.value
    
    def set(self, key: str, value: dict, ttl: int = 3600) -> None:
        # Evict least frequently used if at capacity
        while len(self.entries) >= self.max_size:
            # Find entry with lowest frequency
            min_entry = min(self.entries.values(), key=lambda e: e.frequency)
            del self.entries[min_entry.key]
        
        self.entries[key] = LFUEntry(
            frequency=1,
            last_access=datetime.now(),
            key=key,
            value=value,
            expires_at=datetime.now() + timedelta(seconds=ttl)
        )
```

**Hybrid: LRU with Frequency Boost:** Combine recency and frequency—protect frequently-used entries from eviction.

```python
class HybridCache:
    """
    LRU eviction with frequency protection.
    
    Entries with high hit counts are protected from eviction
    even if they haven't been accessed recently.
    """
    
    def __init__(self, max_size: int = 10000, frequency_threshold: int = 10):
        self.max_size = max_size
        self.frequency_threshold = frequency_threshold
        self.cache = OrderedDict()
    
    def _evict_one(self) -> None:
        """Evict one entry, preferring low-frequency entries."""
        # First pass: try to evict low-frequency entries
        for key in list(self.cache.keys()):
            if self.cache[key]["hits"] < self.frequency_threshold:
                del self.cache[key]
                return
        
        # All entries are high-frequency: evict oldest anyway
        self.cache.popitem(last=False)
```

### Memory Monitoring

Track memory usage to avoid OOM:

```python
import sys


def estimate_cache_memory(cache: dict) -> int:
    """Estimate memory usage of cache in bytes."""
    return sys.getsizeof(cache) + sum(
        sys.getsizeof(k) + sys.getsizeof(v)
        for k, v in cache.items()
    )


class MemoryAwareCache:
    """Cache with memory limit."""
    
    def __init__(self, max_memory_mb: int = 500):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache = OrderedDict()
    
    def set(self, key: str, value: dict, ttl: int = 3600) -> None:
        # Check memory before adding
        current_memory = estimate_cache_memory(self.cache)
        entry_size = sys.getsizeof(key) + sys.getsizeof(value)
        
        # Evict until we have room
        while current_memory + entry_size > self.max_memory_bytes:
            if not self.cache:
                raise MemoryError("Single entry exceeds cache memory limit")
            self.cache.popitem(last=False)
            current_memory = estimate_cache_memory(self.cache)
        
        self.cache[key] = {
            "value": value,
            "expires_at": datetime.now() + timedelta(seconds=ttl)
        }
```

---

## Stale Cache Risks

Understanding what can go wrong helps design better invalidation:

### Risk Categories

|Risk|Impact|Mitigation|
|---|---|---|
|**Outdated facts**|User gets old info|Event-based invalidation|
|**Policy changes**|Compliance violations|Short TTL + manual purge|
|**Model drift**|Different behavior|Version in cache key|
|**Trust erosion**|Users stop trusting system|Detection + monitoring|
|**Legal exposure**|Regulatory issues|Audit trail + rapid invalidation|

### Detection Strategies

Sometimes you can detect stale cache hits:

```python
def detect_potential_staleness(
    cached_result: dict,
    current_doc_hashes: dict[str, str]
) -> dict:
    """
    Check if cached result might be stale.
    
    Compare document hashes used in cached result
    against current document hashes.
    """
    cached_sources = cached_result.get("_sources", [])
    cached_hashes = cached_result.get("_doc_hashes", {})
    
    stale_docs = []
    for doc_id in cached_sources:
        cached_hash = cached_hashes.get(doc_id)
        current_hash = current_doc_hashes.get(doc_id)
        
        if cached_hash and current_hash and cached_hash != current_hash:
            stale_docs.append(doc_id)
    
    return {
        "potentially_stale": len(stale_docs) > 0,
        "stale_documents": stale_docs,
        "recommendation": "recompute" if stale_docs else "use_cached"
    }


# Usage: check before returning cached result
def get_with_staleness_check(query: str) -> dict:
    cached = cache.get(query)
    
    if cached:
        # Quick staleness check
        current_hashes = get_current_doc_hashes()
        staleness = detect_potential_staleness(cached, current_hashes)
        
        if staleness["potentially_stale"]:
            # Invalidate and recompute
            cache.invalidate(query)
            return compute_fresh(query)
        
        return cached
    
    return compute_fresh(query)
```

---

## Cache Warming

After a cache clear or deployment, the cache is "cold"—every request is a miss. This creates latency spikes and increased costs.

### Warming Strategies

**1. Query Log Replay:** Replay recent popular queries to pre-populate cache.

```python
def warm_cache_from_logs(
    cache: MultiLevelCache,
    query_logs: list[dict],
    top_n: int = 1000
) -> dict:
    """
    Warm cache by replaying top queries from logs.
    
    Args:
        cache: The cache to warm
        query_logs: List of {query, count} from analytics
        top_n: Number of top queries to warm
    
    Returns:
        Warming statistics
    """
    # Sort by frequency
    sorted_queries = sorted(
        query_logs,
        key=lambda x: x["count"],
        reverse=True
    )[:top_n]
    
    warmed = 0
    failed = 0
    
    for entry in sorted_queries:
        query = entry["query"]
        try:
            # Run full pipeline (not cached)
            result = run_rag_pipeline(query)
            
            # Store in cache
            cache.set_response(query, result)
            warmed += 1
            
        except Exception as e:
            print(f"Failed to warm: {query}: {e}")
            failed += 1
    
    return {
        "warmed": warmed,
        "failed": failed,
        "total_attempted": len(sorted_queries)
    }
```

**2. Common Query List:** Maintain a curated list of common queries.

```python
COMMON_QUERIES = [
    "What is the refund policy?",
    "What are your business hours?",
    "How do I track my order?",
    "What payment methods do you accept?",
    "How do I contact support?",
    # ... etc
]


def warm_cache_from_list(cache: MultiLevelCache) -> dict:
    """Warm cache with predefined common queries."""
    warmed = 0
    
    for query in COMMON_QUERIES:
        try:
            result = run_rag_pipeline(query)
            cache.set_response(query, result)
            warmed += 1
        except Exception:
            pass
    
    return {"warmed": warmed, "total": len(COMMON_QUERIES)}
```

**3. Gradual Warming:** Warm in background while serving traffic.

```python
import threading
import queue


class BackgroundCacheWarmer:
    """
    Warms cache in background thread.
    
    Doesn't block request handling.
    """
    
    def __init__(self, cache: MultiLevelCache, pipeline_fn):
        self.cache = cache
        self.pipeline_fn = pipeline_fn
        self.queue = queue.Queue()
        self.running = True
        
        # Start background thread
        self.thread = threading.Thread(target=self._warm_loop, daemon=True)
        self.thread.start()
    
    def schedule_warming(self, queries: list[str]) -> None:
        """Add queries to warming queue."""
        for query in queries:
            self.queue.put(query)
    
    def _warm_loop(self) -> None:
        """Background warming loop."""
        while self.running:
            try:
                query = self.queue.get(timeout=1)
                
                # Skip if already cached
                if self.cache.get_response(query).hit:
                    continue
                
                # Warm this query
                result = self.pipeline_fn(query)
                self.cache.set_response(query, result)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Warming error: {e}")
    
    def stop(self) -> None:
        """Stop background warming."""
        self.running = False
        self.thread.join()
```

### When to Warm

|Event|Warming Action|
|---|---|
|Deployment|Replay top 1000 queries|
|Cache clear|Warm from common query list|
|New documents|Warm queries related to new content|
|Traffic spike incoming|Pre-warm expected popular queries|

---

## Monitoring Cache Health

Healthy caches have stable, predictable behavior. Monitor for anomalies.

### Key Metrics

```python
@dataclass
class CacheHealthMetrics:
    """Metrics for cache health monitoring."""
    
    # Hit rates
    exact_hit_rate: float
    semantic_hit_rate: float
    retrieval_hit_rate: float
    overall_hit_rate: float
    
    # Sizes
    total_entries: int
    memory_usage_mb: float
    
    # Performance
    avg_lookup_latency_ms: float
    p99_lookup_latency_ms: float
    
    # Staleness indicators
    avg_entry_age_hours: float
    oldest_entry_age_hours: float
    
    # Trends
    hit_rate_trend: str  # "stable", "increasing", "decreasing"
    size_trend: str      # "stable", "growing", "shrinking"


def compute_cache_health(
    cache: MultiLevelCache,
    lookups: list[dict]  # Recent lookup records
) -> CacheHealthMetrics:
    """Compute health metrics from cache and recent lookups."""
    stats = cache.get_stats()
    
    # Hit rates
    overall_hits = sum(
        stats[level]["hits"] 
        for level in ["exact", "semantic", "retrieval"]
    )
    overall_total = sum(
        stats[level]["hits"] + stats[level]["misses"]
        for level in ["exact", "semantic", "retrieval"]
    )
    
    # Latencies from recent lookups
    latencies = [l["latency_ms"] for l in lookups]
    
    return CacheHealthMetrics(
        exact_hit_rate=stats["exact"]["hit_rate"],
        semantic_hit_rate=stats["semantic"]["hit_rate"],
        retrieval_hit_rate=stats["retrieval"]["hit_rate"],
        overall_hit_rate=overall_hits / overall_total if overall_total > 0 else 0,
        total_entries=sum(stats[l]["size"] for l in ["exact", "semantic", "retrieval"]),
        memory_usage_mb=estimate_cache_memory(cache) / (1024 * 1024),
        avg_lookup_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
        p99_lookup_latency_ms=sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0,
        avg_entry_age_hours=0,  # Would need entry timestamps
        oldest_entry_age_hours=0,
        hit_rate_trend="stable",
        size_trend="stable"
    )
```

### Alerting Rules

|Metric|Warning Threshold|Critical Threshold|
|---|---|---|
|Hit rate drop|20% below baseline|50% below baseline|
|Memory usage|80% of limit|95% of limit|
|Lookup latency|2x baseline|5x baseline|
|Entry age|2x TTL|5x TTL|

```python
def check_cache_alerts(metrics: CacheHealthMetrics, baselines: dict) -> list[dict]:
    """Check for alertable conditions."""
    alerts = []
    
    # Hit rate drop
    if metrics.overall_hit_rate < baselines["hit_rate"] * 0.8:
        alerts.append({
            "severity": "warning",
            "metric": "hit_rate",
            "message": f"Hit rate dropped to {metrics.overall_hit_rate:.2%}",
            "baseline": baselines["hit_rate"]
        })
    
    if metrics.overall_hit_rate < baselines["hit_rate"] * 0.5:
        alerts.append({
            "severity": "critical",
            "metric": "hit_rate",
            "message": f"Hit rate critically low: {metrics.overall_hit_rate:.2%}"
        })
    
    # Memory usage
    max_memory_mb = baselines.get("max_memory_mb", 1000)
    memory_pct = metrics.memory_usage_mb / max_memory_mb
    
    if memory_pct > 0.95:
        alerts.append({
            "severity": "critical",
            "metric": "memory",
            "message": f"Cache memory at {memory_pct:.0%} of limit"
        })
    elif memory_pct > 0.80:
        alerts.append({
            "severity": "warning",
            "metric": "memory",
            "message": f"Cache memory at {memory_pct:.0%} of limit"
        })
    
    return alerts
```

### Dashboard Metrics

Track these over time:

```
┌────────────────────────────────────────────────────────────┐
│  Cache Health Dashboard                                    │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Hit Rates (last hour)                                     │
│  ├─ Exact:     ███░░░░░░░ 12%                             │
│  ├─ Semantic:  ██████░░░░ 38%                             │
│  ├─ Retrieval: ████████░░ 52%                             │
│  └─ Overall:   ██████████ 68%                             │
│                                                            │
│  Cache Size                                                │
│  ├─ Entries: 15,234                                       │
│  └─ Memory:  423 MB / 1000 MB                             │
│                                                            │
│  Latency (p50 / p99)                                       │
│  ├─ Exact:     0.1ms / 0.5ms                              │
│  ├─ Semantic:  45ms / 120ms                               │
│  └─ Retrieval: 2ms / 8ms                                  │
│                                                            │
│  Savings (last 24h)                                        │
│  ├─ API Calls Avoided: 45,230                             │
│  ├─ Estimated Cost:    $45.23                             │
│  └─ Latency Saved:     12.6 hours                         │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **TTL is simple but blunt**: Use for predictable update schedules; accept some staleness.
    
2. **Event-based is accurate but complex**: Requires tracking dependencies and integrating with update pipelines.
    
3. **Version-based is elegant**: Include all dependencies in cache key; version changes automatically invalidate.
    
4. **Tags enable surgical invalidation**: Tag entries with their dependencies; invalidate by tag when dependencies change.
    
5. **Always have eviction**: Unbounded caches exhaust memory. Use LRU, LFU, or memory limits.
    
6. **Warm strategically**: After clears or deployments, pre-populate with common queries to avoid cold-start latency.
    
7. **Monitor continuously**: Hit rate drops signal problems—query pattern changes, cache configuration issues, or staleness.
    
8. **Design for the cost of staleness**: High-stakes applications (compliance, medical) need aggressive invalidation; low-stakes can tolerate longer TTLs.
    

---

## What's Next

- **Note 6**: Production cache integration — putting it all together with real backends, monitoring, and operational best practices