# Exact Match Caching — Implementation and Limitations

## What Exact Match Means

Exact match caching is the simplest caching strategy: if the query is _identical_ to a previously seen query, return the cached result.

```
Query: "What is the refund policy?"
→ Check cache for exact match
→ Found: return cached answer
→ Not found: run full pipeline, cache result

Query: "What is the refund policy?"  (again)
→ CACHE HIT: return instantly

Query: "Tell me about refunds"
→ CACHE MISS: different string, no match
```

The strength is simplicity and zero risk of returning wrong answers. The weakness is low hit rate—users rarely type identical queries.

---

## Cache Key Design

A cache key must uniquely identify a query _and_ the configuration that affects its output.

### Why Query Alone Isn't Enough

The same query with different configurations produces different results:

```python
# Same query, different outputs
query = "Explain quantum computing"

# Config 1: GPT-4, temperature=0.7, max_tokens=500
# Config 2: GPT-4, temperature=0.0, max_tokens=100
# Config 3: GPT-3.5, temperature=0.7, max_tokens=500

# All three produce different results
# Cache key must include config
```

### Key Components

A robust cache key includes:

1. **Query text** (normalized)
2. **Model identifier** (gpt-4o, claude-sonnet-4-20250514, etc.)
3. **Generation parameters** (temperature, max_tokens, etc.)
4. **System prompt hash** (if system prompt affects output)
5. **RAG config** (retrieval settings, if applicable)

### Implementation: Hash-Based Keys

```python
import hashlib
import json
from typing import Any


def create_cache_key(
    query: str,
    config: dict[str, Any] | None = None
) -> str:
    """
    Create deterministic cache key from query + config.
    
    Args:
        query: User query (will be normalized)
        config: Configuration affecting output (model, temperature, etc.)
    
    Returns:
        SHA-256 hash string
    """
    # Normalize query
    normalized_query = query.lower().strip()
    
    # Combine query and config
    key_data = {
        "query": normalized_query,
        "config": config or {}
    }
    
    # Sort keys for deterministic JSON
    key_string = json.dumps(key_data, sort_keys=True)
    
    # Hash to fixed-length key
    return hashlib.sha256(key_string.encode()).hexdigest()


# Example usage
key1 = create_cache_key(
    "What is the refund policy?",
    {"model": "gpt-4o", "temperature": 0.0}
)
# '3a7f2b...' (64-char hex string)

key2 = create_cache_key(
    "what is the refund policy?",  # Different case
    {"model": "gpt-4o", "temperature": 0.0}
)
# Same hash as key1 (normalization worked)

key3 = create_cache_key(
    "What is the refund policy?",
    {"model": "gpt-4o", "temperature": 0.7}  # Different temp
)
# Different hash (config changed)
```

### Why SHA-256?

- **Fixed length**: Always 64 hex characters, regardless of input size
- **Deterministic**: Same input always produces same output
- **Collision-resistant**: Different inputs virtually never produce same hash
- **Fast**: Negligible computation time

---

## Basic In-Memory Implementation

Start with the simplest backend: a Python dictionary with TTL tracking.

### Entry Structure

Each cache entry stores:

```python
{
    "value": {...},           # The cached result
    "created_at": datetime,   # When it was cached
    "expires_at": datetime    # When it expires
}
```

### Full Implementation

```python
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any


class ExactMatchCache:
    """
    Simple exact-match cache with TTL expiration.
    
    For development and low-traffic production use.
    Not suitable for: multi-process deployments, persistence requirements.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Args:
            ttl_seconds: Time-to-live for cache entries (default: 1 hour)
        """
        self.cache: dict[str, dict] = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent matching."""
        return query.lower().strip()
    
    def _create_key(self, query: str, config: dict | None) -> str:
        """Create cache key from query + config."""
        key_data = {
            "query": self._normalize_query(query),
            "config": config or {}
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def get(self, query: str, config: dict | None = None) -> dict | None:
        """
        Get cached result if exists and not expired.
        
        Returns:
            Cached result dict, or None if miss/expired
        """
        key = self._create_key(query, config)
        
        if key not in self.cache:
            self.misses += 1
            return None
        
        entry = self.cache[key]
        
        # Check expiration
        if datetime.now() > entry["expires_at"]:
            del self.cache[key]
            self.misses += 1
            return None
        
        self.hits += 1
        return entry["value"]
    
    def set(
        self, 
        query: str, 
        result: dict, 
        config: dict | None = None,
        ttl_override: int | None = None
    ) -> None:
        """
        Cache a result.
        
        Args:
            query: The query string
            result: The result to cache
            config: Configuration used for this query
            ttl_override: Optional TTL override for this entry
        """
        key = self._create_key(query, config)
        ttl = ttl_override if ttl_override is not None else self.ttl
        
        self.cache[key] = {
            "value": result,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(seconds=ttl)
        }
    
    def invalidate(self, query: str, config: dict | None = None) -> bool:
        """
        Remove specific entry from cache.
        
        Returns:
            True if entry existed and was removed
        """
        key = self._create_key(query, config)
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def clear(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        count = len(self.cache)
        self.cache.clear()
        return count
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries (call periodically).
        
        Returns:
            Number of entries removed
        """
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now > entry["expires_at"]
        ]
        for key in expired_keys:
            del self.cache[key]
        return len(expired_keys)
    
    def stats(self) -> dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        return {
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0.0,
            "ttl_seconds": self.ttl
        }
```

### Usage Example

```python
cache = ExactMatchCache(ttl_seconds=3600)

# First query - cache miss
result = cache.get("What is the refund policy?")
# None

# Simulate getting result from LLM
llm_result = {"answer": "Our refund policy allows...", "sources": [...]}

# Cache it
cache.set("What is the refund policy?", llm_result)

# Second query - cache hit
result = cache.get("What is the refund policy?")
# {"answer": "Our refund policy allows...", "sources": [...]}

# Different query - cache miss
result = cache.get("Tell me about refunds")
# None (different string)

# Check stats
print(cache.stats())
# {"size": 1, "hits": 1, "misses": 2, "hit_rate": 0.333, "ttl_seconds": 3600}
```

---

## TTL (Time To Live) Selection

TTL determines how long cached answers remain valid. The right TTL depends on how quickly your underlying data changes.

### TTL Guidelines

|Data Change Rate|TTL|Examples|
|---|---|---|
|Real-time|0 (no cache)|Stock prices, live scores|
|Minutes|1-5 min|Weather, trending topics|
|Hours|1-4 hours|News summaries, daily reports|
|Daily|12-24 hours|Product info, company policies|
|Rarely|1-7 days|Historical facts, documentation|
|Never|Unlimited|Math facts, definitions|

### The TTL Trade-off

```
Short TTL (minutes):
  + Data is fresh
  + Wrong answers expire quickly
  - Low hit rate
  - More LLM calls

Long TTL (hours/days):
  + High hit rate
  + Lower costs
  - Stale answers possible
  - Requires manual invalidation for updates
```

### Practical Strategy

Start conservative (shorter TTL), then extend based on:

1. **Observed staleness**: Are users getting outdated answers?
2. **Hit rate analysis**: Is TTL causing unnecessary misses?
3. **Data update frequency**: How often does source data change?

```python
# Different TTLs for different query types
class SmartTTLCache(ExactMatchCache):
    
    def __init__(self):
        super().__init__()
        self.ttl_rules = {
            "policy": 86400,      # 24 hours - policies rarely change
            "price": 3600,        # 1 hour - prices may update
            "availability": 300,  # 5 min - availability changes often
            "default": 3600       # 1 hour default
        }
    
    def _get_ttl(self, query: str) -> int:
        """Determine TTL based on query content."""
        query_lower = query.lower()
        
        if "price" in query_lower or "cost" in query_lower:
            return self.ttl_rules["price"]
        elif "available" in query_lower or "stock" in query_lower:
            return self.ttl_rules["availability"]
        elif "policy" in query_lower or "rule" in query_lower:
            return self.ttl_rules["policy"]
        else:
            return self.ttl_rules["default"]
    
    def set(self, query: str, result: dict, config: dict | None = None) -> None:
        """Cache with query-appropriate TTL."""
        ttl = self._get_ttl(query)
        super().set(query, result, config, ttl_override=ttl)
```

---

## Query Normalization

Normalization increases hit rate by treating "equivalent" queries as identical.

### Safe Normalizations

These transformations are almost always safe:

```python
def normalize_query(query: str) -> str:
    """
    Normalize query for cache matching.
    
    Safe transformations that preserve meaning.
    """
    normalized = query
    
    # Lowercase
    normalized = normalized.lower()
    
    # Strip leading/trailing whitespace
    normalized = normalized.strip()
    
    # Collapse multiple spaces to single space
    normalized = " ".join(normalized.split())
    
    return normalized


# Examples
normalize_query("What is the refund policy?")
# "what is the refund policy?"

normalize_query("  What  is  the  refund  policy?  ")
# "what is the refund policy?"

normalize_query("WHAT IS THE REFUND POLICY?")
# "what is the refund policy?"

# All three produce the same normalized form → same cache key
```

### Risky Normalizations

Some normalizations can change meaning:

```python
# RISKY: Removing punctuation
"What's the policy?" → "whats the policy"
"What is the policy?" → "what is the policy"
# Different normalized forms, but same intent

# RISKY: Removing question marks
"Is this available" → "is this available"
"Is this available?" → "is this available"
# Maybe okay, but what about:
"You're serious?" → "youre serious"  # Meaning changes

# RISKY: Stemming
"running" → "run"
"runner" → "run"
# "I want to go running" vs "I want a runner" - different meanings
```

### Recommendation

Start with safe normalizations only. Measure cache hit rate. If hit rate is too low due to minor variations, consider:

1. Semantic caching (Note 3) instead of aggressive normalization
2. Query-type-specific normalization (only for FAQ-style queries)

---

## Limitations of Exact Match Caching

Exact match caching has fundamental limitations for natural language:

### The Paraphrase Problem

Users express the same intent with different words:

```
Intent: "I want to know about refunds"

User A: "What is the refund policy?"
User B: "Tell me about refunds"
User C: "How do I get my money back?"
User D: "refund policy"
User E: "Can I return this for a refund?"

# All 5 queries have the same intent
# Exact match cache: 5 separate entries, 0 cache hits between users
```

### Hit Rate Reality

For natural language applications:

|Query Source|Typical Exact Match Hit Rate|
|---|---|
|Programmatic queries (APIs)|60-90%|
|Button-triggered queries|70-95%|
|Search box (user-typed)|5-20%|
|Free-form chat|2-10%|

The variance in human phrasing kills exact match hit rates.

### When Exact Match Is Enough

Despite low hit rates for chat, exact match caching still makes sense when:

1. **Programmatic queries**: Code calling your API with fixed query strings
    
    ```python
    # Always identical
    result = assistant.query("Get system status")
    ```
    
2. **Button-triggered queries**: UI buttons with hardcoded text
    
    ```html
    <button onclick="query('What are your business hours?')">
      Hours
    </button>
    ```
    
3. **High-repetition environments**: Support bots where 20% of users ask the exact same question
    
    ```
    20% of 10,000 queries = 2,000 identical queries
    Even 50% hit rate on those = 1,000 LLM calls saved
    ```
    
4. **As a first-pass check**: Exact match is cheap; check it before semantic cache
    
    ```python
    def get_cached(query):
        # Fast exact match check first
        exact = exact_cache.get(query)
        if exact:
            return exact
        
        # Slower semantic check only on exact miss
        return semantic_cache.get(query)
    ```
    

---

## Backend Options

### In-Memory Dictionary

```python
# What we implemented above
cache = ExactMatchCache()
```

**Pros:**

- Simplest implementation
- Fastest access (~1μs)
- No external dependencies

**Cons:**

- Lost on process restart
- Not shared across processes/servers
- Memory limited to single process

**Use for:** Development, testing, single-process deployments

### Redis

**Reference:** redis-py 7.x documentation (https://redis.io/docs/latest/develop/clients/redis-py/)

```python
import redis
import json
import hashlib
from typing import Any


class RedisExactMatchCache:
    """
    Redis-backed exact match cache.
    
    Production-ready: persistent, shared across processes, fast.
    """
    
    def __init__(
        self, 
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        prefix: str = "llm_cache:",
        default_ttl: int = 3600
    ):
        """
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            prefix: Key prefix for namespacing
            default_ttl: Default TTL in seconds
        """
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True  # Return strings, not bytes
        )
        self.prefix = prefix
        self.default_ttl = default_ttl
    
    def _create_key(self, query: str, config: dict | None) -> str:
        """Create Redis key from query + config."""
        key_data = {
            "query": query.lower().strip(),
            "config": config or {}
        }
        key_string = json.dumps(key_data, sort_keys=True)
        hash_key = hashlib.sha256(key_string.encode()).hexdigest()
        return f"{self.prefix}{hash_key}"
    
    def get(self, query: str, config: dict | None = None) -> dict | None:
        """Get cached result."""
        key = self._create_key(query, config)
        value = self.client.get(key)
        
        if value is None:
            return None
        
        return json.loads(value)
    
    def set(
        self, 
        query: str, 
        result: dict, 
        config: dict | None = None,
        ttl: int | None = None
    ) -> None:
        """Cache a result with TTL."""
        key = self._create_key(query, config)
        ttl = ttl or self.default_ttl
        
        # setex: SET with EXpiration
        self.client.setex(
            key,
            ttl,
            json.dumps(result)
        )
    
    def invalidate(self, query: str, config: dict | None = None) -> bool:
        """Remove specific entry."""
        key = self._create_key(query, config)
        return bool(self.client.delete(key))
    
    def clear_all(self) -> int:
        """
        Clear all cache entries with this prefix.
        
        Warning: KEYS command is slow on large databases.
        Use SCAN for production with many keys.
        """
        keys = self.client.keys(f"{self.prefix}*")
        if keys:
            return self.client.delete(*keys)
        return 0
    
    def stats(self) -> dict:
        """Get cache statistics."""
        # Count keys with our prefix
        keys = self.client.keys(f"{self.prefix}*")
        
        return {
            "size": len(keys),
            "prefix": self.prefix,
            "default_ttl": self.default_ttl
        }
```

**Pros:**

- Persistent (survives restarts)
- Shared across processes/servers
- Fast (~1-2ms network round trip)
- Built-in TTL expiration
- Battle-tested at scale

**Cons:**

- Requires Redis server
- Network latency (still fast)
- Additional infrastructure

**Use for:** Production deployments, multi-server setups

### SQLite

```python
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import Any


class SQLiteExactMatchCache:
    """
    SQLite-backed exact match cache.
    
    Simple persistence without external services.
    """
    
    def __init__(
        self, 
        db_path: str = "llm_cache.db",
        default_ttl: int = 3600
    ):
        self.db_path = db_path
        self.default_ttl = default_ttl
        self._init_db()
    
    def _init_db(self):
        """Create cache table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires 
                ON cache(expires_at)
            """)
    
    def _create_key(self, query: str, config: dict | None) -> str:
        """Create cache key."""
        key_data = {
            "query": query.lower().strip(),
            "config": config or {}
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def get(self, query: str, config: dict | None = None) -> dict | None:
        """Get cached result if not expired."""
        key = self._create_key(query, config)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
        
        if row is None:
            return None
        
        value, expires_at = row
        expires_at = datetime.fromisoformat(expires_at)
        
        if datetime.now() > expires_at:
            self.invalidate(query, config)
            return None
        
        return json.loads(value)
    
    def set(
        self, 
        query: str, 
        result: dict, 
        config: dict | None = None,
        ttl: int | None = None
    ) -> None:
        """Cache a result."""
        key = self._create_key(query, config)
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache (key, value, expires_at)
                VALUES (?, ?, ?)
            """, (key, json.dumps(result), expires_at.isoformat()))
    
    def invalidate(self, query: str, config: dict | None = None) -> bool:
        """Remove specific entry."""
        key = self._create_key(query, config)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            return cursor.rowcount > 0
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (datetime.now().isoformat(),)
            )
            return cursor.rowcount
```

**Pros:**

- Persistent (file-based)
- No external services
- Zero configuration
- Portable (just a file)

**Cons:**

- Single-machine only
- Slower than Redis for high throughput
- Manual expiration cleanup needed

**Use for:** Single-machine deployments, development with persistence

### Comparison Table

|Feature|In-Memory|Redis|SQLite|
|---|---|---|---|
|Persistence|❌|✅|✅|
|Multi-process|❌|✅|⚠️ (locking issues)|
|Multi-server|❌|✅|❌|
|Latency|~1μs|~1-2ms|~1-5ms|
|Auto TTL expiration|Manual|✅|Manual|
|Setup complexity|None|Medium|Low|

---

## Key Takeaways

1. **Exact match is the simplest cache**: Hash query + config, lookup result. Zero risk of wrong answers.
    
2. **Cache keys must include config**: Model, temperature, and other parameters affect output.
    
3. **Normalize queries carefully**: Lowercase and strip whitespace are safe. Aggressive normalization risks changing meaning.
    
4. **TTL balances freshness vs. hit rate**: Start conservative, extend based on observed staleness.
    
5. **Hit rates are low for natural language**: Users phrase things differently. Expect 5-20% for typed queries.
    
6. **Exact match is still valuable**: As a fast first-pass check before semantic cache, and for programmatic/button-triggered queries.
    
7. **Choose backend by deployment**: Dict for dev, Redis for production, SQLite for simple persistence.
    

---

## What's Next

- **Note 3**: Semantic caching — use embeddings to match _similar_ queries, not just identical ones
- **Note 4**: Retrieval and embedding caching — cache intermediate computation steps
- **Note 5**: Cache invalidation — keeping cached answers fresh when data changes