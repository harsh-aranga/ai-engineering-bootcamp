# Multi-Level Cache Architecture — Retrieval and Response Caching

## The Cache Hierarchy Concept

A RAG pipeline has multiple expensive steps. Each can be cached independently:

```
┌─────────────────────────────────────────────────────────────┐
│                         User Query                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
              ┌───────────▼───────────┐
              │  LEVEL 1: EXACT MATCH │  ← Fastest (hash lookup)
              │  Identical query?     │     Cost: ~1μs
              └───────────┬───────────┘
                          │ miss
              ┌───────────▼───────────┐
              │  LEVEL 2: SEMANTIC    │  ← Check similar queries
              │  Similar query?       │     Cost: ~50-200ms (embedding)
              └───────────┬───────────┘
                          │ miss
              ┌───────────▼───────────┐
              │  LEVEL 3: RETRIEVAL   │  ← Use cached chunks
              │  Same chunks needed?  │     Cost: ~5ms (lookup)
              └───────────┬───────────┘     Saves: embedding + retrieval
                          │ miss
              ┌───────────▼───────────┐
              │  LEVEL 4: EMBEDDING   │  ← Skip embedding computation
              │  Text already embedded?│    Cost: ~1ms (lookup)
              └───────────┬───────────┘     Saves: ~50-200ms per text
                          │ miss
              ┌───────────▼───────────┐
              │     FULL PIPELINE     │  ← Everything from scratch
              │  Embed → Retrieve →   │
              │  Rerank → Generate    │
              └───────────────────────┘
```

Each level trades off complexity for potential savings. Higher levels (exact/semantic) save more per hit; lower levels (retrieval/embedding) have higher hit rates.

---

## What Each Cache Level Provides

### Level 1: Exact Match Cache

**What it caches**: Complete response for exact query string.

**Saves**: Entire pipeline (~500ms-3s + API cost).

**Hit rate**: Low for natural language (5-20%), high for programmatic queries (60-90%).

**When it helps**: Same query asked repeatedly, button-triggered queries, API calls.

```
Query: "What is the refund policy?"
       ↓
Exact Cache: HIT
       ↓
Return cached response immediately
```

### Level 2: Semantic Cache

**What it caches**: Complete response for semantically similar queries.

**Saves**: Entire pipeline (~500ms-3s + API cost).

**Hit rate**: Moderate (30-60% for user-typed queries).

**When it helps**: Users phrase the same question differently.

```
Query: "Tell me about refunds"
       ↓
Semantic Cache: HIT (similar to "What is the refund policy?")
       ↓
Return cached response
```

### Level 3: Retrieval Cache

**What it caches**: Retrieved chunks for a query.

**Saves**: Embedding + vector search + reranking (~100-500ms).

**Still does**: LLM generation (so answer reflects current prompt/model).

**Hit rate**: Higher than semantic (similar queries often need same chunks).

**When it helps**: Want fresh generation but same context.

```
Query: "What's the return policy?"
       ↓
Semantic Cache: MISS
       ↓
Retrieval Cache: HIT (cached chunks for "refund policy" queries)
       ↓
Skip retrieval, use cached chunks
       ↓
Generate fresh answer with current model
```

### Level 4: Embedding Cache

**What it caches**: Embedding vectors for query text.

**Saves**: Query embedding computation (~50-200ms per query).

**Hit rate**: Depends on query repetition (same/similar queries across users).

**When it helps**: Multiple users ask the same question; retries within a session; batch evaluations.

**Clarification**: Document chunks are embedded once at index time and stored in your vector database. They don't get re-embedded during retrieval. The embedding cache at query time is for **query embeddings only**.

```
Query: "What's the refund policy?" (first time)
       ↓
All higher caches: MISS
       ↓
Embedding Cache for query: MISS → compute embedding, cache it
       ↓
Use query embedding to retrieve chunks from vector DB
       ↓
Continue pipeline

Query: "What's the refund policy?" (second time, different user)
       ↓
Exact/Semantic cache: MISS (assuming expired or threshold not met)
       ↓
Embedding Cache for query: HIT → skip embedding computation
       ↓
Use cached query embedding to retrieve chunks
       ↓
Continue pipeline (saved ~100ms)
```

For index operations (rebuilds, migrations), a separate chunk embedding cache avoids recomputing embeddings for unchanged documents — but that's an indexing concern, not a query-time cache.

---

## Cache Flow Diagram

```
Query arrives
       │
       ▼
┌──────────────────┐
│ Exact Match?     │──── HIT ────→ Return cached response
└────────┬─────────┘               (latency: ~1ms, cost: $0)
         │ MISS
         ▼
┌──────────────────┐
│ Semantic Match?  │──── HIT ────→ Return cached response
└────────┬─────────┘               (latency: ~100ms, cost: $0.0001 for embedding)
         │ MISS
         ▼
┌──────────────────┐
│ Retrieval Cache? │──── HIT ────→ Use cached chunks, skip to generation
└────────┬─────────┘               (latency: ~5ms + generation, cost: LLM only)
         │ MISS
         ▼
┌──────────────────┐
│ Embed Query      │◄─── Check embedding cache for query
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Retrieve Chunks  │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Rerank (optional)│
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Generate Answer  │
└────────┬─────────┘
         ▼
Cache results at multiple levels:
  - Exact cache: query → response
  - Semantic cache: query embedding → response
  - Retrieval cache: query → chunks
  - Embedding cache: query text → embedding
```

---

## Retrieval Cache Implementation

The retrieval cache stores which chunks were retrieved for a query. This is useful when:

- Multiple similar queries need the same context
- You want fresh generation (new model, updated prompt) but same retrieval
- Retrieval is expensive (large index, complex reranking)

```python
import hashlib
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any


@dataclass
class RetrievalCacheEntry:
    """Cached retrieval results."""
    query: str
    chunks: list[dict]  # [{id, content, metadata, score}]
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0


class RetrievalCache:
    """
    Cache for retrieval results (chunks).
    
    Allows skipping embedding + vector search while still
    running fresh generation.
    """
    
    def __init__(
        self,
        ttl_seconds: int = 1800,  # 30 min default (shorter than response cache)
        max_entries: int = 5000
    ):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self.cache: dict[str, RetrievalCacheEntry] = {}
        self.hits = 0
        self.misses = 0
    
    def _create_key(self, query: str, retrieval_config: dict | None = None) -> str:
        """
        Create cache key from query and retrieval config.
        
        Retrieval config includes: n_results, filters, rerank settings.
        Different configs = different cache keys.
        """
        key_data = {
            "query": query.lower().strip(),
            "config": retrieval_config or {}
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def get(self, query: str, config: dict | None = None) -> list[dict] | None:
        """
        Get cached chunks for query.
        
        Returns:
            List of chunk dicts, or None if miss.
        """
        key = self._create_key(query, config)
        
        if key not in self.cache:
            self.misses += 1
            return None
        
        entry = self.cache[key]
        
        if datetime.now() > entry.expires_at:
            del self.cache[key]
            self.misses += 1
            return None
        
        self.hits += 1
        entry.hit_count += 1
        return entry.chunks
    
    def set(
        self,
        query: str,
        chunks: list[dict],
        config: dict | None = None
    ) -> None:
        """Cache retrieval results."""
        # Evict if needed
        if len(self.cache) >= self.max_entries:
            self._evict_oldest()
        
        key = self._create_key(query, config)
        self.cache[key] = RetrievalCacheEntry(
            query=query,
            chunks=chunks,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self.ttl)
        )
    
    def invalidate_by_chunk_id(self, chunk_id: str) -> int:
        """
        Invalidate any cached retrievals containing a specific chunk.
        
        Call this when a document/chunk is updated or deleted.
        
        Returns:
            Number of entries invalidated.
        """
        keys_to_delete = []
        
        for key, entry in self.cache.items():
            chunk_ids = [c.get("id") for c in entry.chunks]
            if chunk_id in chunk_ids:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.cache[key]
        
        return len(keys_to_delete)
    
    def _evict_oldest(self) -> None:
        """Remove oldest entry."""
        if not self.cache:
            return
        oldest_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k].created_at
        )
        del self.cache[oldest_key]
    
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

---

## Embedding Cache Implementation

The embedding cache stores computed embeddings for **query text**. At query time, this prevents recomputing embeddings for:

- Query text that was seen before (same question from different users)
- Repeated queries during batch evaluations or testing

Note: Document chunks are embedded once at index time and stored in your vector DB. The embedding cache below is for query-time caching, not chunk caching.

```python
import hashlib
import numpy as np
from datetime import datetime, timedelta
from typing import Callable


class EmbeddingCache:
    """
    Cache for computed query embeddings.
    
    Prevents recomputing embeddings for queries that were already seen.
    """
    
    def __init__(
        self,
        embedding_fn: Callable[[str], np.ndarray],
        ttl_seconds: int = 86400,  # 24 hours (embeddings are stable)
        max_entries: int = 50000
    ):
        """
        Args:
            embedding_fn: Function that computes embedding for text.
            ttl_seconds: Cache TTL (long, since embeddings don't change).
            max_entries: Maximum cached embeddings.
        """
        self.embedding_fn = embedding_fn
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        
        self.cache: dict[str, dict] = {}  # {text_hash: {embedding, expires_at}}
        self.hits = 0
        self.misses = 0
        self.compute_time_saved_ms = 0.0
    
    def _hash_text(self, text: str) -> str:
        """Hash text content for cache key."""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def get_or_compute(self, text: str) -> np.ndarray:
        """
        Get embedding from cache or compute and cache it.
        
        This is the main interface - always returns an embedding.
        """
        import time
        
        text_hash = self._hash_text(text)
        
        # Check cache
        if text_hash in self.cache:
            entry = self.cache[text_hash]
            
            if datetime.now() <= entry["expires_at"]:
                self.hits += 1
                # Estimate time saved (~100ms per embedding)
                self.compute_time_saved_ms += 100
                return entry["embedding"]
            else:
                # Expired
                del self.cache[text_hash]
        
        # Cache miss - compute
        self.misses += 1
        start = time.perf_counter()
        embedding = self.embedding_fn(text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        # Store in cache
        self._store(text_hash, embedding)
        
        return embedding
    
    def get(self, text: str) -> np.ndarray | None:
        """
        Get embedding from cache only (don't compute).
        
        Returns None on miss.
        """
        text_hash = self._hash_text(text)
        
        if text_hash not in self.cache:
            return None
        
        entry = self.cache[text_hash]
        
        if datetime.now() > entry["expires_at"]:
            del self.cache[text_hash]
            return None
        
        return entry["embedding"]
    
    def _store(self, text_hash: str, embedding: np.ndarray) -> None:
        """Store embedding in cache."""
        # Evict if needed
        if len(self.cache) >= self.max_entries:
            self._evict_oldest()
        
        self.cache[text_hash] = {
            "embedding": embedding,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(seconds=self.ttl)
        }
    
    def preload(self, texts: list[str]) -> None:
        """
        Preload embeddings for a list of texts.
        
        Useful for warming the cache with document chunks.
        """
        for text in texts:
            self.get_or_compute(text)
    
    def _evict_oldest(self) -> None:
        """Remove oldest entry."""
        if not self.cache:
            return
        oldest_hash = min(
            self.cache.keys(),
            key=lambda h: self.cache[h]["created_at"]
        )
        del self.cache[oldest_hash]
    
    def stats(self) -> dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        return {
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0.0,
            "compute_time_saved_ms": round(self.compute_time_saved_ms, 2),
            "ttl_seconds": self.ttl
        }
```

---

## When Each Level Helps

|Cache Level|Best For|Hit Rate|Savings Per Hit|
|---|---|---|---|
|**Exact Match**|Programmatic queries, buttons, repeated API calls|5-90%*|Full pipeline|
|**Semantic**|User-typed queries with variation|30-60%|Full pipeline|
|**Retrieval**|Fresh generation with same context|40-70%|Retrieval step|
|**Embedding**|Repeated chunks/queries|60-90%|Embedding step|

*Hit rate varies dramatically by use case.

### Decision Framework

```python
def should_enable_cache_level(
    query_source: str,
    query_repetition: str,
    data_freshness: str,
    generation_freshness: str
) -> dict[str, bool]:
    """
    Decide which cache levels to enable.
    
    Args:
        query_source: "programmatic" | "user_typed" | "mixed"
        query_repetition: "high" | "medium" | "low"
        data_freshness: "static" | "daily" | "hourly" | "realtime"
        generation_freshness: "cached_ok" | "prefer_fresh" | "must_fresh"
    
    Returns:
        Dict of cache levels to enable.
    """
    levels = {
        "exact_match": False,
        "semantic": False,
        "retrieval": False,
        "embedding": True  # Almost always beneficial
    }
    
    # Exact match: high value for programmatic/repeated
    if query_source == "programmatic" or query_repetition == "high":
        levels["exact_match"] = True
    
    # Semantic: valuable for user-typed queries
    if query_source in ("user_typed", "mixed"):
        levels["semantic"] = True
    
    # Retrieval: enable unless generation must be fresh
    if generation_freshness != "must_fresh" and data_freshness != "realtime":
        levels["retrieval"] = True
    
    # Response caches (exact/semantic) only if cached generation OK
    if generation_freshness == "must_fresh":
        levels["exact_match"] = False
        levels["semantic"] = False
    
    return levels


# Example usage
config = should_enable_cache_level(
    query_source="user_typed",
    query_repetition="medium",
    data_freshness="daily",
    generation_freshness="cached_ok"
)
# {'exact_match': False, 'semantic': True, 'retrieval': True, 'embedding': True}
```

---

## Multi-Level Cache System Implementation

Here's a complete implementation that combines all cache levels:

```python
import hashlib
import json
import time
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class CacheResult:
    """Result from cache lookup."""
    hit: bool
    level: str  # "exact" | "semantic" | "retrieval" | "none"
    data: Any = None
    similarity: float | None = None
    latency_ms: float = 0.0
    original_query: str | None = None


@dataclass
class CacheStats:
    """Statistics for a single cache level."""
    hits: int = 0
    misses: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class MultiLevelCache:
    """
    Multi-level caching system for RAG pipelines.
    
    Levels (checked in order):
    1. Exact match - identical query strings
    2. Semantic - similar query embeddings
    3. Retrieval - cached chunks for query
    4. Embedding - cached embeddings for text
    
    Lower levels (retrieval, embedding) have higher hit rates but
    save less per hit. Higher levels save more but hit less often.
    """
    
    def __init__(
        self,
        embedding_fn: Callable[[str], np.ndarray],
        exact_ttl: int = 3600,
        semantic_ttl: int = 3600,
        semantic_threshold: float = 0.92,
        retrieval_ttl: int = 1800,
        embedding_ttl: int = 86400,
        enable_exact: bool = True,
        enable_semantic: bool = True,
        enable_retrieval: bool = True,
        enable_embedding: bool = True
    ):
        """
        Args:
            embedding_fn: Function to compute embeddings.
            exact_ttl: TTL for exact match cache (seconds).
            semantic_ttl: TTL for semantic cache (seconds).
            semantic_threshold: Similarity threshold for semantic hits.
            retrieval_ttl: TTL for retrieval cache (seconds).
            embedding_ttl: TTL for embedding cache (seconds).
            enable_*: Enable/disable each cache level.
        """
        self.embedding_fn = embedding_fn
        self.semantic_threshold = semantic_threshold
        
        # TTLs
        self.exact_ttl = exact_ttl
        self.semantic_ttl = semantic_ttl
        self.retrieval_ttl = retrieval_ttl
        self.embedding_ttl = embedding_ttl
        
        # Enable flags
        self.enable_exact = enable_exact
        self.enable_semantic = enable_semantic
        self.enable_retrieval = enable_retrieval
        self.enable_embedding = enable_embedding
        
        # Storage
        self.exact_cache: dict[str, dict] = {}
        self.semantic_entries: list[dict] = []
        self.retrieval_cache: dict[str, dict] = {}
        self.embedding_cache: dict[str, dict] = {}
        
        # Stats
        self.stats = {
            "exact": CacheStats(),
            "semantic": CacheStats(),
            "retrieval": CacheStats(),
            "embedding": CacheStats()
        }
        
        # Cost tracking (estimated)
        self.estimated_cost_saved_usd = 0.0
        self.estimated_latency_saved_ms = 0.0
    
    # ─────────────────────────────────────────────────────────────
    # Exact Match Cache
    # ─────────────────────────────────────────────────────────────
    
    def _exact_key(self, query: str, config: dict | None = None) -> str:
        key_data = {"query": query.lower().strip(), "config": config or {}}
        return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    def _check_exact(self, query: str, config: dict | None = None) -> CacheResult:
        """Check exact match cache."""
        if not self.enable_exact:
            return CacheResult(hit=False, level="exact")
        
        start = time.perf_counter()
        key = self._exact_key(query, config)
        
        if key in self.exact_cache:
            entry = self.exact_cache[key]
            if datetime.now() <= entry["expires_at"]:
                self.stats["exact"].hits += 1
                return CacheResult(
                    hit=True,
                    level="exact",
                    data=entry["result"],
                    latency_ms=(time.perf_counter() - start) * 1000
                )
            else:
                del self.exact_cache[key]
        
        self.stats["exact"].misses += 1
        return CacheResult(hit=False, level="exact")
    
    def _set_exact(self, query: str, result: dict, config: dict | None = None) -> None:
        """Store in exact match cache."""
        if not self.enable_exact:
            return
        key = self._exact_key(query, config)
        self.exact_cache[key] = {
            "result": result,
            "expires_at": datetime.now() + timedelta(seconds=self.exact_ttl)
        }
    
    # ─────────────────────────────────────────────────────────────
    # Semantic Cache
    # ─────────────────────────────────────────────────────────────
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        dot = np.dot(a, b)
        norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
    
    def _check_semantic(self, query: str) -> CacheResult:
        """Check semantic cache."""
        if not self.enable_semantic or not self.semantic_entries:
            return CacheResult(hit=False, level="semantic")
        
        start = time.perf_counter()
        
        # Get query embedding (may hit embedding cache)
        query_embedding = self.get_embedding(query)
        
        best_entry = None
        best_similarity = 0.0
        
        for entry in self.semantic_entries:
            if datetime.now() > entry["expires_at"]:
                continue
            
            similarity = self._cosine_similarity(query_embedding, entry["embedding"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_entry = entry
        
        if best_entry and best_similarity >= self.semantic_threshold:
            self.stats["semantic"].hits += 1
            return CacheResult(
                hit=True,
                level="semantic",
                data=best_entry["result"],
                similarity=round(best_similarity, 4),
                original_query=best_entry["query"],
                latency_ms=(time.perf_counter() - start) * 1000
            )
        
        self.stats["semantic"].misses += 1
        return CacheResult(
            hit=False,
            level="semantic",
            latency_ms=(time.perf_counter() - start) * 1000
        )
    
    def _set_semantic(self, query: str, result: dict) -> None:
        """Store in semantic cache."""
        if not self.enable_semantic:
            return
        
        query_embedding = self.get_embedding(query)
        self.semantic_entries.append({
            "query": query,
            "embedding": query_embedding,
            "result": result,
            "expires_at": datetime.now() + timedelta(seconds=self.semantic_ttl)
        })
    
    # ─────────────────────────────────────────────────────────────
    # Retrieval Cache
    # ─────────────────────────────────────────────────────────────
    
    def _retrieval_key(self, query: str, config: dict | None = None) -> str:
        key_data = {"query": query.lower().strip(), "config": config or {}}
        return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    
    def get_retrieval(self, query: str, config: dict | None = None) -> list[dict] | None:
        """Get cached retrieval results."""
        if not self.enable_retrieval:
            return None
        
        key = self._retrieval_key(query, config)
        
        if key in self.retrieval_cache:
            entry = self.retrieval_cache[key]
            if datetime.now() <= entry["expires_at"]:
                self.stats["retrieval"].hits += 1
                return entry["chunks"]
            else:
                del self.retrieval_cache[key]
        
        self.stats["retrieval"].misses += 1
        return None
    
    def set_retrieval(self, query: str, chunks: list[dict], config: dict | None = None) -> None:
        """Cache retrieval results."""
        if not self.enable_retrieval:
            return
        
        key = self._retrieval_key(query, config)
        self.retrieval_cache[key] = {
            "chunks": chunks,
            "expires_at": datetime.now() + timedelta(seconds=self.retrieval_ttl)
        }
    
    # ─────────────────────────────────────────────────────────────
    # Embedding Cache
    # ─────────────────────────────────────────────────────────────
    
    def _embedding_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()
    
    def get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding, using cache if available.
        
        This is the main embedding interface - always returns embedding.
        """
        if not self.enable_embedding:
            return self.embedding_fn(text)
        
        key = self._embedding_key(text)
        
        if key in self.embedding_cache:
            entry = self.embedding_cache[key]
            if datetime.now() <= entry["expires_at"]:
                self.stats["embedding"].hits += 1
                return entry["embedding"]
            else:
                del self.embedding_cache[key]
        
        # Compute and cache
        self.stats["embedding"].misses += 1
        embedding = self.embedding_fn(text)
        
        self.embedding_cache[key] = {
            "embedding": embedding,
            "expires_at": datetime.now() + timedelta(seconds=self.embedding_ttl)
        }
        
        return embedding
    
    # ─────────────────────────────────────────────────────────────
    # Main Interface
    # ─────────────────────────────────────────────────────────────
    
    def get_response(self, query: str, config: dict | None = None) -> CacheResult:
        """
        Check all response caches (exact, semantic).
        
        Returns:
            CacheResult with hit status and cached data if found.
        """
        # Level 1: Exact match
        result = self._check_exact(query, config)
        if result.hit:
            self._track_savings("response")
            return result
        
        # Level 2: Semantic match
        result = self._check_semantic(query)
        if result.hit:
            self._track_savings("response")
            return result
        
        return CacheResult(hit=False, level="none")
    
    def set_response(self, query: str, result: dict, config: dict | None = None) -> None:
        """
        Store response in all response caches.
        """
        self._set_exact(query, result, config)
        self._set_semantic(query, result)
    
    def _track_savings(self, cache_type: str) -> None:
        """Track estimated cost and latency savings."""
        if cache_type == "response":
            # Full pipeline saved: ~$0.001 per query, ~1000ms
            self.estimated_cost_saved_usd += 0.001
            self.estimated_latency_saved_ms += 1000
        elif cache_type == "retrieval":
            # Retrieval saved: ~$0.0001, ~200ms
            self.estimated_cost_saved_usd += 0.0001
            self.estimated_latency_saved_ms += 200
        elif cache_type == "embedding":
            # Embedding saved: ~$0.00001, ~100ms
            self.estimated_cost_saved_usd += 0.00001
            self.estimated_latency_saved_ms += 100
    
    # ─────────────────────────────────────────────────────────────
    # Invalidation
    # ─────────────────────────────────────────────────────────────
    
    def invalidate_by_document(self, doc_id: str) -> dict[str, int]:
        """
        Invalidate cache entries related to a document.
        
        Call when a document is updated or deleted.
        
        Returns:
            Count of invalidated entries per cache level.
        """
        counts = {"exact": 0, "semantic": 0, "retrieval": 0}
        
        # Exact cache: clear entries that used this doc
        # (requires storing which docs were used - simplified here)
        
        # Retrieval cache: clear entries containing this doc's chunks
        keys_to_delete = []
        for key, entry in self.retrieval_cache.items():
            for chunk in entry.get("chunks", []):
                if chunk.get("doc_id") == doc_id:
                    keys_to_delete.append(key)
                    break
        
        for key in keys_to_delete:
            del self.retrieval_cache[key]
        counts["retrieval"] = len(keys_to_delete)
        
        return counts
    
    def clear(self, level: str | None = None) -> dict[str, int]:
        """
        Clear cache entries.
        
        Args:
            level: Specific level to clear, or None for all.
        
        Returns:
            Count of cleared entries per level.
        """
        counts = {}
        
        if level is None or level == "exact":
            counts["exact"] = len(self.exact_cache)
            self.exact_cache.clear()
        
        if level is None or level == "semantic":
            counts["semantic"] = len(self.semantic_entries)
            self.semantic_entries.clear()
        
        if level is None or level == "retrieval":
            counts["retrieval"] = len(self.retrieval_cache)
            self.retrieval_cache.clear()
        
        if level is None or level == "embedding":
            counts["embedding"] = len(self.embedding_cache)
            self.embedding_cache.clear()
        
        return counts
    
    # ─────────────────────────────────────────────────────────────
    # Statistics
    # ─────────────────────────────────────────────────────────────
    
    def get_stats(self) -> dict:
        """Get comprehensive cache statistics."""
        return {
            "exact": {
                "enabled": self.enable_exact,
                "size": len(self.exact_cache),
                "hits": self.stats["exact"].hits,
                "misses": self.stats["exact"].misses,
                "hit_rate": round(self.stats["exact"].hit_rate, 4)
            },
            "semantic": {
                "enabled": self.enable_semantic,
                "size": len(self.semantic_entries),
                "hits": self.stats["semantic"].hits,
                "misses": self.stats["semantic"].misses,
                "hit_rate": round(self.stats["semantic"].hit_rate, 4),
                "threshold": self.semantic_threshold
            },
            "retrieval": {
                "enabled": self.enable_retrieval,
                "size": len(self.retrieval_cache),
                "hits": self.stats["retrieval"].hits,
                "misses": self.stats["retrieval"].misses,
                "hit_rate": round(self.stats["retrieval"].hit_rate, 4)
            },
            "embedding": {
                "enabled": self.enable_embedding,
                "size": len(self.embedding_cache),
                "hits": self.stats["embedding"].hits,
                "misses": self.stats["embedding"].misses,
                "hit_rate": round(self.stats["embedding"].hit_rate, 4)
            },
            "savings": {
                "estimated_cost_saved_usd": round(self.estimated_cost_saved_usd, 4),
                "estimated_latency_saved_ms": round(self.estimated_latency_saved_ms, 2)
            }
        }
```

---

## Usage Example

```python
from openai import OpenAI

# Setup
openai_client = OpenAI()

def embed(text: str) -> np.ndarray:
    """Embedding function using OpenAI."""
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return np.array(response.data[0].embedding)

# Create multi-level cache
cache = MultiLevelCache(
    embedding_fn=embed,
    exact_ttl=3600,
    semantic_ttl=3600,
    semantic_threshold=0.92,
    retrieval_ttl=1800,
    embedding_ttl=86400
)


# Integrate with RAG pipeline
def query_with_cache(query: str) -> dict:
    """RAG query with multi-level caching."""
    
    # Check response caches (exact + semantic)
    cache_result = cache.get_response(query)
    if cache_result.hit:
        return {
            **cache_result.data,
            "_cache": cache_result.level,
            "_cache_similarity": cache_result.similarity,
            "_cache_latency_ms": cache_result.latency_ms
        }
    
    # Check retrieval cache
    cached_chunks = cache.get_retrieval(query)
    if cached_chunks:
        # Skip retrieval, go straight to generation
        response = generate_answer(query, cached_chunks)
        
        # Cache the response for future
        cache.set_response(query, response)
        
        return {
            **response,
            "_cache": "retrieval",
            "_cache_latency_ms": 5.0  # Retrieval skipped
        }
    
    # Full pipeline - no cache hits
    # Embedding cache is used automatically via cache.get_embedding()
    query_embedding = cache.get_embedding(query)
    
    chunks = retrieve_chunks(query_embedding)
    
    # Cache retrieval results
    cache.set_retrieval(query, chunks)
    
    response = generate_answer(query, chunks)
    
    # Cache response
    cache.set_response(query, response)
    
    return {**response, "_cache": "miss"}


# Run queries
result1 = query_with_cache("What is the refund policy?")
# Full pipeline, cached

result2 = query_with_cache("What is the refund policy?")
# Exact match hit

result3 = query_with_cache("Tell me about refunds")
# Semantic hit

print(cache.get_stats())
```

---

## Cache Statistics to Track

### Per-Level Metrics

|Metric|What It Tells You|
|---|---|
|**Size**|How many entries in this cache|
|**Hits**|Number of successful cache hits|
|**Misses**|Number of cache misses|
|**Hit Rate**|hits / (hits + misses)|

### Aggregate Metrics

|Metric|How to Calculate|
|---|---|
|**Overall Hit Rate**|Any cache hit / total queries|
|**Response Cache Hit Rate**|(exact_hits + semantic_hits) / total|
|**Cost Savings**|Sum of (hit_count × cost_per_query) per level|
|**Latency Savings**|Sum of (hit_count × latency_saved) per level|

### Example Stats Output

```python
{
    "exact": {
        "enabled": True,
        "size": 150,
        "hits": 45,
        "misses": 455,
        "hit_rate": 0.09
    },
    "semantic": {
        "enabled": True,
        "size": 200,
        "hits": 180,
        "misses": 275,
        "hit_rate": 0.3956
    },
    "retrieval": {
        "enabled": True,
        "size": 300,
        "hits": 120,
        "misses": 155,
        "hit_rate": 0.4364
    },
    "embedding": {
        "enabled": True,
        "size": 5000,
        "hits": 2500,
        "misses": 3000,
        "hit_rate": 0.4545
    },
    "savings": {
        "estimated_cost_saved_usd": 0.2370,
        "estimated_latency_saved_ms": 237000.0
    }
}
```

---

## Key Takeaways

1. **Multiple cache levels address different needs**: Exact match is fastest; semantic catches paraphrases; retrieval allows fresh generation; embedding caches computation.
    
2. **Check caches in order of savings**: Exact → Semantic → Retrieval → Embedding. Earlier hits save more.
    
3. **Retrieval cache is often the sweet spot**: Higher hit rate than semantic (similar queries retrieve same chunks), still allows fresh generation.
    
4. **Embedding cache is almost always worth it**: Very high hit rate, no risk of stale answers, only saves computation time.
    
5. **Track stats per level**: Understand where your hits come from to tune TTLs and thresholds.
    
6. **Different TTLs for different levels**: Response caches need shorter TTLs (data changes affect answers); embedding cache can be long (embeddings are stable).
    

---

## What's Next

- **Note 5**: Cache invalidation strategies — keeping cached data fresh when sources change
- **Note 6**: Production cache integration — putting it all together with monitoring and tuning