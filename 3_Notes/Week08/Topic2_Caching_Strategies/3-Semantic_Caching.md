# Semantic Caching — Embeddings for Similar Query Matching

## The Core Insight

Users ask the same question with different words:

```
"What is the refund policy?"
"Tell me about refunds"
"How do refunds work?"
"Can I get my money back?"
"What are the rules for returning items?"
```

All five queries have the same intent and should return the same cached answer. Exact match caching misses all of them because the strings differ. Semantic caching catches them because the _meaning_ is similar.

The insight: **similar embeddings → similar meaning → likely same answer**.

---

## How Semantic Caching Works

```
┌─────────────────────────────────────────────────────────────┐
│              Incoming Query: "How do refunds work?"         │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │  Embed Query      │
                    │  → [0.23, -0.45,  │
                    │     0.12, ...]    │
                    └─────────┬─────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  Compare Against Cached       │
              │  Query Embeddings             │
              │                               │
              │  "What is refund policy?"     │
              │  → similarity: 0.94           │
              │                               │
              │  "Tell me about shipping"     │
              │  → similarity: 0.61           │
              │                               │
              │  "What are your hours?"       │
              │  → similarity: 0.42           │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  Best match: 0.94             │
              │  Threshold: 0.92              │
              │  0.94 > 0.92 → CACHE HIT      │
              └───────────────┬───────────────┘
                              │
                              ▼
              Return cached answer from
              "What is refund policy?"
```

The algorithm:

1. **Embed** the incoming query
2. **Compare** against all stored query embeddings
3. **Find** the most similar cached query
4. **Check threshold**: if similarity > threshold → cache hit
5. **Return** the cached result (or miss if below threshold)

---

## Implementation Components

### 1. Embedding Model

Use the same embedding model you use for RAG retrieval. Consistency matters—different models produce incompatible embeddings.

**Reference:** OpenAI Embeddings API (https://platform.openai.com/docs/api-reference/embeddings/create)

```python
from openai import OpenAI
import numpy as np


class EmbeddingModel:
    """
    Wrapper for OpenAI embeddings API.
    
    Uses text-embedding-3-small by default (1536 dimensions).
    For higher accuracy, use text-embedding-3-large (3072 dimensions).
    """
    
    def __init__(
        self, 
        model: str = "text-embedding-3-small",
        api_key: str | None = None
    ):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
        # Dimension depends on model
        self._dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536  # Legacy
        }
    
    @property
    def dimensions(self) -> int:
        return self._dimensions.get(self.model, 1536)
    
    def embed(self, text: str) -> np.ndarray:
        """
        Embed a single text string.
        
        Returns:
            numpy array of shape (dimensions,)
        """
        response = self.client.embeddings.create(
            input=text,
            model=self.model
        )
        return np.array(response.data[0].embedding)
    
    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """
        Embed multiple texts in a single API call.
        
        More efficient than calling embed() in a loop.
        
        Returns:
            numpy array of shape (len(texts), dimensions)
        """
        response = self.client.embeddings.create(
            input=texts,
            model=self.model
        )
        # Response maintains input order
        embeddings = [data.embedding for data in response.data]
        return np.array(embeddings)
```

### 2. Similarity Function

Cosine similarity measures the angle between two vectors. It ranges from -1 (opposite) to 1 (identical).

```python
import numpy as np


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Returns:
        Similarity score from -1 to 1 (typically 0 to 1 for embeddings)
    """
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


# Example
emb1 = np.array([0.1, 0.2, 0.3])
emb2 = np.array([0.1, 0.2, 0.3])
print(cosine_similarity(emb1, emb2))  # 1.0 (identical)

emb3 = np.array([0.1, 0.2, 0.35])
print(cosine_similarity(emb1, emb3))  # ~0.998 (very similar)

emb4 = np.array([-0.1, -0.2, -0.3])
print(cosine_similarity(emb1, emb4))  # -1.0 (opposite)
```

For semantic caching, typical similarity scores for text embeddings:

|Similarity|Interpretation|
|---|---|
|0.95+|Nearly identical meaning|
|0.90-0.95|Very similar, probably same answer|
|0.85-0.90|Similar topic, might differ|
|0.70-0.85|Related but different|
|< 0.70|Different topics|

### 3. Cache Entry Structure

Each cached entry stores:

```python
{
    "query": str,                    # Original query text
    "embedding": np.ndarray,         # Query embedding
    "result": dict,                  # The cached answer
    "created_at": datetime,          # When cached
    "expires_at": datetime,          # When it expires
    "hit_count": int                 # How often this entry was hit
}
```

---

## Full Implementation

```python
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheEntry:
    """Single entry in the semantic cache."""
    query: str
    embedding: np.ndarray
    result: dict
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0


class SemanticCache:
    """
    Semantic cache using embeddings to match similar queries.
    
    Finds cached answers for queries that are semantically similar
    to previously seen queries, even if the exact wording differs.
    """
    
    def __init__(
        self,
        embedding_model: EmbeddingModel,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 3600,
        max_entries: int = 10000
    ):
        """
        Args:
            embedding_model: Model for computing embeddings
            similarity_threshold: Minimum similarity for cache hit (0-1)
            ttl_seconds: Time-to-live for cache entries
            max_entries: Maximum cache size (LRU eviction)
        """
        self.embedding_model = embedding_model
        self.threshold = similarity_threshold
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        
        # Storage
        self.entries: list[CacheEntry] = []
        
        # Stats
        self.hits = 0
        self.misses = 0
        self.embedding_time_ms = 0.0
        self.search_time_ms = 0.0
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if entry has expired."""
        return datetime.now() > entry.expires_at
    
    def _find_best_match(
        self, 
        query_embedding: np.ndarray
    ) -> tuple[CacheEntry | None, float]:
        """
        Find the most similar cached entry.
        
        Returns:
            (best_entry, similarity_score) or (None, 0.0) if no match
        """
        import time
        start = time.perf_counter()
        
        best_entry = None
        best_similarity = 0.0
        
        for entry in self.entries:
            # Skip expired entries
            if self._is_expired(entry):
                continue
            
            similarity = self._cosine_similarity(
                query_embedding, 
                entry.embedding
            )
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_entry = entry
        
        elapsed = (time.perf_counter() - start) * 1000
        self.search_time_ms += elapsed
        
        return best_entry, best_similarity
    
    def get(self, query: str) -> dict | None:
        """
        Look up semantically similar cached result.
        
        Returns:
            Cached result with metadata, or None if no match.
            
            On hit, returns:
            {
                **original_result,
                "_cache": "semantic_hit",
                "_cache_similarity": 0.94,
                "_cache_original_query": "What is the refund policy?"
            }
        """
        import time
        
        # Embed the query
        start = time.perf_counter()
        query_embedding = self.embedding_model.embed(query)
        embed_elapsed = (time.perf_counter() - start) * 1000
        self.embedding_time_ms += embed_elapsed
        
        # Find best match
        best_entry, similarity = self._find_best_match(query_embedding)
        
        # Check threshold
        if best_entry is None or similarity < self.threshold:
            self.misses += 1
            return None
        
        # Cache hit
        self.hits += 1
        best_entry.hit_count += 1
        
        return {
            **best_entry.result,
            "_cache": "semantic_hit",
            "_cache_similarity": round(similarity, 4),
            "_cache_original_query": best_entry.query
        }
    
    def set(self, query: str, result: dict) -> None:
        """
        Add query and result to cache.
        
        If cache is full, evicts least recently used entries.
        """
        # Evict if at capacity
        if len(self.entries) >= self.max_entries:
            self._evict_lru()
        
        # Embed query
        query_embedding = self.embedding_model.embed(query)
        
        # Create entry
        entry = CacheEntry(
            query=query,
            embedding=query_embedding,
            result=result,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self.ttl),
            hit_count=0
        )
        
        self.entries.append(entry)
    
    def _evict_lru(self, count: int = 1) -> None:
        """
        Evict least recently used entries.
        
        Uses hit_count as proxy for usefulness.
        First removes expired, then lowest hit_count.
        """
        # Remove expired first
        self.entries = [e for e in self.entries if not self._is_expired(e)]
        
        # If still over capacity, remove lowest hit_count
        while len(self.entries) >= self.max_entries and self.entries:
            min_hits = min(e.hit_count for e in self.entries)
            for i, entry in enumerate(self.entries):
                if entry.hit_count == min_hits:
                    self.entries.pop(i)
                    break
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        before = len(self.entries)
        self.entries = [e for e in self.entries if not self._is_expired(e)]
        return before - len(self.entries)
    
    def stats(self) -> dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        return {
            "size": len(self.entries),
            "max_entries": self.max_entries,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0.0,
            "threshold": self.threshold,
            "ttl_seconds": self.ttl,
            "total_embedding_time_ms": round(self.embedding_time_ms, 2),
            "total_search_time_ms": round(self.search_time_ms, 2),
            "avg_embedding_time_ms": round(
                self.embedding_time_ms / total if total > 0 else 0, 2
            ),
            "avg_search_time_ms": round(
                self.search_time_ms / total if total > 0 else 0, 2
            )
        }
```

### Usage Example

```python
# Initialize
embedding_model = EmbeddingModel(model="text-embedding-3-small")
cache = SemanticCache(
    embedding_model=embedding_model,
    similarity_threshold=0.92,
    ttl_seconds=3600
)

# First query - cache miss
result = cache.get("What is the refund policy?")
# None

# Simulate LLM response
llm_result = {
    "answer": "Our refund policy allows returns within 30 days...",
    "sources": ["refund_policy.md"]
}

# Cache it
cache.set("What is the refund policy?", llm_result)

# Similar query - should be cache HIT
result = cache.get("Tell me about refunds")
# {
#     "answer": "Our refund policy allows returns within 30 days...",
#     "sources": ["refund_policy.md"],
#     "_cache": "semantic_hit",
#     "_cache_similarity": 0.9312,
#     "_cache_original_query": "What is the refund policy?"
# }

# Different query - cache MISS
result = cache.get("What are your business hours?")
# None (similarity too low)

print(cache.stats())
# {
#     "size": 1,
#     "hits": 1,
#     "misses": 1,
#     "hit_rate": 0.5,
#     "threshold": 0.92,
#     ...
# }
```

---

## Similarity Threshold Selection

The threshold determines how similar a query must be to trigger a cache hit. This is the most important tuning parameter.

### Threshold Trade-offs

```
High threshold (0.95+):
  + Very few false positives
  + Only returns answers for truly equivalent questions
  - Lower hit rate
  - Misses valid paraphrases
  
Low threshold (0.85):
  + Higher hit rate
  + Catches more paraphrases
  - Risk of returning wrong answers
  - Similar queries might have different correct answers
```

### Domain-Dependent Tuning

The right threshold depends on your query space:

|Domain|Suggested Threshold|Rationale|
|---|---|---|
|FAQ bot|0.88-0.92|Questions are well-defined, slight variation OK|
|Customer support|0.90-0.94|Balance hit rate with correctness|
|Medical/legal|0.95+|Wrong answer is costly|
|General chat|0.92-0.95|Wide variety of queries|
|Code assistance|0.94+|Subtle differences matter|

### How to Tune

1. **Collect query pairs**: Find queries you believe should hit the same cache
2. **Compute similarities**: Embed pairs and measure cosine similarity
3. **Find the distribution**: What similarities do "same answer" pairs have?
4. **Set threshold**: Just below the minimum for "same answer" pairs

```python
def analyze_query_pairs(
    embedding_model: EmbeddingModel,
    same_answer_pairs: list[tuple[str, str]],
    different_answer_pairs: list[tuple[str, str]]
) -> dict:
    """
    Analyze similarity distributions to help set threshold.
    
    Args:
        same_answer_pairs: Query pairs that should return same answer
        different_answer_pairs: Query pairs that should NOT match
    
    Returns:
        Statistics to guide threshold selection
    """
    def compute_similarities(pairs):
        sims = []
        for q1, q2 in pairs:
            e1 = embedding_model.embed(q1)
            e2 = embedding_model.embed(q2)
            sim = np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))
            sims.append(sim)
        return sims
    
    same_sims = compute_similarities(same_answer_pairs)
    diff_sims = compute_similarities(different_answer_pairs)
    
    return {
        "same_answer": {
            "min": min(same_sims),
            "max": max(same_sims),
            "mean": np.mean(same_sims),
            "suggested_threshold": min(same_sims) - 0.02  # Small buffer
        },
        "different_answer": {
            "min": min(diff_sims),
            "max": max(diff_sims),
            "mean": np.mean(diff_sims)
        },
        "overlap_warning": max(diff_sims) > min(same_sims)
    }


# Example usage
same_pairs = [
    ("What is the refund policy?", "Tell me about refunds"),
    ("What is the refund policy?", "How do I get a refund?"),
    ("What are your hours?", "When are you open?"),
]

different_pairs = [
    ("What is the refund policy?", "What is the shipping policy?"),
    ("What are your hours?", "What is the refund policy?"),
]

analysis = analyze_query_pairs(embedding_model, same_pairs, different_pairs)
print(analysis)
# {
#     "same_answer": {"min": 0.89, "max": 0.96, "mean": 0.92, "suggested_threshold": 0.87},
#     "different_answer": {"min": 0.58, "max": 0.71, "mean": 0.64},
#     "overlap_warning": False  # Good! No overlap
# }
```

---

## The Lookup Cost Problem

### Naive O(N) Search

The basic implementation compares the query against every cached embedding:

```python
# O(N) - checks every entry
for entry in self.entries:
    similarity = cosine_similarity(query_embedding, entry.embedding)
    if similarity > best_similarity:
        best_similarity = similarity
        best_entry = entry
```

For small caches (< 10,000 entries), this is fine:

|Cache Size|Search Time (approximate)|
|---|---|
|100|< 1ms|
|1,000|~1-2ms|
|10,000|~10-20ms|
|100,000|~100-200ms|
|1,000,000|~1-2s|

### Scaling with Vector Indices

For large caches, use approximate nearest neighbor (ANN) algorithms:

|Algorithm|Time Complexity|Accuracy|Use Case|
|---|---|---|---|
|Linear scan|O(N)|Exact|< 10K entries|
|HNSW|O(log N)|~95-99%|General purpose|
|IVF|O(√N)|~90-95%|Very large scale|

**For most semantic caching use cases, linear scan is sufficient.** You typically cache thousands, not millions, of queries.

If you need scale:

```python
# Using FAISS for approximate nearest neighbor
import faiss

class ScalableSemanticCache:
    """
    Semantic cache with FAISS index for fast lookup.
    
    Use when cache size > 10,000 entries.
    """
    
    def __init__(
        self,
        embedding_model: EmbeddingModel,
        similarity_threshold: float = 0.92,
        use_gpu: bool = False
    ):
        self.embedding_model = embedding_model
        self.threshold = similarity_threshold
        
        # FAISS index for fast similarity search
        dim = embedding_model.dimensions
        self.index = faiss.IndexFlatIP(dim)  # Inner product (cosine for normalized)
        
        # Metadata storage (indexed by position)
        self.entries: list[dict] = []
    
    def _normalize(self, embedding: np.ndarray) -> np.ndarray:
        """Normalize for cosine similarity via inner product."""
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm
    
    def get(self, query: str) -> dict | None:
        """Fast similarity search using FAISS."""
        if self.index.ntotal == 0:
            return None
        
        # Embed and normalize
        query_embedding = self._normalize(
            self.embedding_model.embed(query)
        ).reshape(1, -1).astype('float32')
        
        # Search for top-1 match
        similarities, indices = self.index.search(query_embedding, k=1)
        
        similarity = similarities[0][0]
        idx = indices[0][0]
        
        if similarity < self.threshold:
            return None
        
        entry = self.entries[idx]
        return {
            **entry["result"],
            "_cache": "semantic_hit",
            "_cache_similarity": float(similarity)
        }
    
    def set(self, query: str, result: dict) -> None:
        """Add to cache and FAISS index."""
        embedding = self._normalize(
            self.embedding_model.embed(query)
        ).astype('float32')
        
        # Add to FAISS index
        self.index.add(embedding.reshape(1, -1))
        
        # Store metadata
        self.entries.append({
            "query": query,
            "result": result,
            "created_at": datetime.now()
        })
```

---

## Returning Cache Metadata

Including metadata in cache responses helps with:

1. **Debugging**: Why did this answer come from cache?
2. **Monitoring**: Track cache behavior in production
3. **Transparency**: Let users know they got a cached answer

### Essential Metadata

```python
{
    # Original result
    "answer": "...",
    "sources": [...],
    
    # Cache metadata
    "_cache": "semantic_hit",           # vs "exact_hit" or "miss"
    "_cache_similarity": 0.9312,        # How similar was the match?
    "_cache_original_query": "What...", # What query was actually cached?
    "_cache_created_at": "2024-01-15",  # How old is this cached answer?
    "_cache_latency_ms": 5.2            # How long did cache lookup take?
}
```

### Using Metadata for Debugging

```python
def debug_cache_hit(result: dict) -> None:
    """Print cache hit details for debugging."""
    if "_cache" not in result:
        print("Not from cache")
        return
    
    print(f"Cache type: {result['_cache']}")
    print(f"Similarity: {result.get('_cache_similarity', 'N/A')}")
    print(f"Original query: {result.get('_cache_original_query', 'N/A')}")
    
    # Warning for borderline matches
    sim = result.get('_cache_similarity', 1.0)
    if 0.90 < sim < 0.95:
        print("⚠️  Borderline match - verify answer correctness")
```

---

## Limitations of Semantic Caching

### 1. Embedding Cost on Every Query

Unlike exact match (hash lookup is free), semantic cache embeds every query:

```
Exact match: hash("query") → lookup → ~1μs
Semantic:    embed("query") → search → ~50-200ms

Even cache misses pay the embedding cost.
```

**Mitigation**: Use exact match as first-pass, semantic only on exact miss.

### 2. False Positives

Similar queries don't always have the same answer:

```
Query 1: "What is the return policy for electronics?"
Query 2: "What is the return policy for clothing?"
Similarity: 0.91

# These are similar, but have different correct answers!
# If threshold is 0.90, you'll return the wrong answer.
```

**Mitigation**:

- Tune threshold carefully
- Include domain/category in cache key
- Log false positives and adjust

### 3. Context-Dependent Queries

Some queries depend on conversation context:

```
Previous: "Tell me about the iPhone 15"
Query: "What's the battery life?"
→ Answer: iPhone 15 battery life

Previous: "Tell me about the MacBook Pro"
Query: "What's the battery life?"  (identical!)
→ Answer: MacBook Pro battery life

# Same query, different correct answer based on context
```

**Mitigation**:

- Include conversation context in cache key
- Don't cache context-dependent queries
- Use shorter TTL for conversational queries

### 4. Stale Embeddings

If you change embedding models, old cache entries become incompatible:

```python
# Old cache entries: embedded with text-embedding-ada-002
# New model: text-embedding-3-small

# Comparing embeddings from different models → meaningless similarity scores!
```

**Mitigation**:

- Include model version in cache key
- Clear cache when changing models
- Version your cache entries

```python
def create_semantic_cache_key(query: str, model: str, config: dict) -> str:
    """Include model version to prevent cross-model matches."""
    return {
        "query": query,
        "embedding_model": model,  # Critical!
        "config": config
    }
```

---

## When to Use Semantic vs. Exact Match

|Factor|Exact Match|Semantic|
|---|---|---|
|Query source|Programmatic/buttons|User-typed|
|Query variation|Low (same strings)|High (paraphrasing)|
|Cost sensitivity|Less sensitive|More sensitive (embedding cost)|
|Correctness sensitivity|Any|High (threshold tuning needed)|
|Implementation complexity|Simple|Moderate|
|Hit rate (user queries)|5-20%|30-60%|

**Best practice**: Use both in sequence:

```python
def get_cached(query: str) -> dict | None:
    # Fast exact check first (free)
    result = exact_cache.get(query)
    if result:
        return {**result, "_cache": "exact_hit"}
    
    # Semantic check only on exact miss
    result = semantic_cache.get(query)
    if result:
        return result  # Already has semantic metadata
    
    return None
```

---

## Key Takeaways

1. **Semantic caching catches paraphrases**: "What is X?" and "Tell me about X" hit the same cache entry.
    
2. **Embedding cost is paid on every lookup**: Unlike exact match, even misses cost ~50-200ms for embedding.
    
3. **Threshold is the critical parameter**: Too loose → wrong answers; too strict → low hit rate. Tune empirically.
    
4. **Linear scan is fine for small caches**: < 10K entries, just iterate. Use FAISS/HNSW only at scale.
    
5. **Include metadata in responses**: Similarity score and original query help debugging and monitoring.
    
6. **Watch for false positives**: Similar queries don't always deserve the same answer. Context and domain matter.
    
7. **Use exact match first**: It's free. Only invoke semantic cache on exact miss.
    

---

## What's Next

- **Note 4**: Retrieval and embedding caching — cache intermediate computation, not just final answers
- **Note 5**: Cache invalidation — keeping cached answers fresh when data changes
- **Note 6**: Multi-level cache integration — combining all cache types into a unified system