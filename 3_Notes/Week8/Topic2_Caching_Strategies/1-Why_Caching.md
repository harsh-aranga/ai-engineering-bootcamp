# Why Caching Matters for LLM Systems

## The Three Problems Caching Solves

Every LLM API call has three costs that compound as usage scales:

### 1. Latency

LLM inference is slow by computing standards:

|Operation|Typical Latency|
|---|---|
|Cache lookup (in-memory)|~1ms|
|Cache lookup (Redis)|~2-5ms|
|Embedding computation|50-200ms|
|Vector retrieval|20-100ms|
|LLM generation (GPT-4 class)|500ms-3s|
|LLM generation (complex query)|3-10s|

A user asking "What's your refund policy?" waits 1-2 seconds for an LLM response. With caching, the same question returns in milliseconds. The difference between "instant" and "noticeable delay" shapes user experience fundamentally.

### 2. Cost

Every API call costs money:

|Model|Input Cost|Output Cost|
|---|---|---|
|GPT-4o|$2.50/1M tokens|$10.00/1M tokens|
|GPT-4o-mini|$0.15/1M tokens|$0.60/1M tokens|
|Claude Sonnet|$3.00/1M tokens|$15.00/1M tokens|
|Embedding (text-embedding-3-small)|$0.02/1M tokens|—|

A customer support bot handling 10,000 queries/day at ~1,000 tokens per query:

- Without caching: ~$25-100/day depending on model
- With 50% cache hit rate: ~$12.50-50/day
- With 70% cache hit rate: ~$7.50-30/day

The savings compound. At enterprise scale (millions of queries), caching becomes a cost management necessity, not an optimization.

### 3. Redundancy

Users ask the same questions. A lot.

In typical applications:

- **Customer support**: 20-40% of queries are near-identical ("How do I reset my password?", "What are your hours?", "How do I get a refund?")
- **Internal knowledge bases**: Teams ask the same questions about policies, processes, and procedures
- **Search/RAG systems**: Related queries retrieve the same documents and generate similar answers

This redundancy is the opportunity. Every repeated question is a cache hit waiting to happen.

---

## LLM-Specific Caching Opportunities

Traditional web caching assumes one user, one session. LLM systems have richer caching opportunities because the same _work_ gets repeated across different contexts:

### Same Question, Different Users

```
User A (Monday 9am):    "What is the PTO policy?"
User B (Monday 2pm):    "What is the PTO policy?"
User C (Tuesday 10am):  "What is the PTO policy?"
```

All three should return the same cached answer. Unlike user-specific data, many LLM queries are about shared knowledge.

### Similar Questions, Same Answer

```
"What is the PTO policy?"
"Tell me about vacation days"
"How much PTO do I get?"
"What's the time off policy?"
```

These are semantically equivalent. A smart cache recognizes similarity and returns the same answer.

### Same Chunks Retrieved for Related Queries

```
Query: "What's the refund policy?"
→ Retrieves: [refund_policy.md, returns_faq.md]

Query: "How do I return an item?"
→ Retrieves: [returns_faq.md, refund_policy.md]  ← Same chunks!
```

Even if the final answers differ, the retrieval step found the same documents. Caching retrieval results saves that work.

### Same Query Embeddings Across Users

Document chunks are embedded once at index time and stored in your vector database — they don't get re-embedded on every query. But the **user's query** gets embedded on every request to compare against stored chunk embeddings.

Query embedding caching helps when:

- Multiple users ask the same or similar questions
- A user retries or rephrases within a session
- You're running batch evaluations with repeated queries

For index operations (rebuilds, migrations), caching chunk embeddings avoids recomputing embeddings for unchanged documents.

---

## Cache Hit Rate Impact

The math is straightforward but the impact is significant.

### Cost Reduction

```
Cost with caching = Base cost × (1 - hit_rate)
```

|Hit Rate|Cost Reduction|10K queries/day savings|
|---|---|---|
|30%|30%|$7.50-30/day|
|50%|50%|$12.50-50/day|
|70%|70%|$17.50-70/day|
|90%|90%|$22.50-90/day|

### Latency Reduction

Average latency improves proportionally:

```
Avg latency = (hit_rate × cache_latency) + ((1 - hit_rate) × full_latency)
```

With 1ms cache latency and 1000ms full latency:

|Hit Rate|Average Latency|Improvement|
|---|---|---|
|0%|1000ms|baseline|
|30%|700ms|30% faster|
|50%|500ms|50% faster|
|70%|300ms|70% faster|
|90%|100ms|90% faster|

### Real-World Hit Rates

What hit rates are achievable?

|Application Type|Typical Hit Rate|Why|
|---|---|---|
|FAQ bot|60-80%|Limited question space|
|Customer support|40-60%|Common issues repeat|
|Internal knowledge base|30-50%|Shared organizational questions|
|Open-ended chat|10-30%|High query variance|
|Code assistant|20-40%|Patterns repeat, specifics vary|

The pattern: more constrained domains → higher hit rates.

---

## Types of Caches in LLM Systems (Overview)

LLM systems have multiple caching opportunities at different stages:

```
┌─────────────────────────────────────────────────────────────┐
│                         User Query                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │  EXACT MATCH CACHE  │ ← Fastest check
               │  "Same query?"      │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │   SEMANTIC CACHE    │ ← Similar query?
               │  "Similar query?"   │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │  EMBEDDING CACHE    │ ← Skip embedding step
               │  "Seen this text?"  │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │  RETRIEVAL CACHE    │ ← Skip retrieval step
               │  "Same chunks?"     │
               └──────────┬──────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │     LLM CALL        │ ← Most expensive step
               │                     │
               └──────────┬──────────┘
                          │
                          ▼
                   Return Response
```

### Exact Match Cache

The simplest cache: hash the query, look up the hash.

- **Matches**: Identical queries only
- **Speed**: O(1) lookup
- **Hit rate**: Low (queries must be character-for-character identical)
- **Risk**: None (exact match = exact answer)

Best for: High-traffic queries with exact repetition.

### Semantic Cache

Use embeddings to find _similar_ queries, not just identical ones.

- **Matches**: Queries above similarity threshold (e.g., cosine > 0.95)
- **Speed**: O(n) scan or O(log n) with vector index
- **Hit rate**: Higher (catches paraphrases)
- **Risk**: Too loose a threshold → wrong answers returned

Best for: Natural language queries where users phrase things differently.

### Embedding Cache

Cache the embedding computation itself.

- **Matches**: Identical text chunks
- **Speed**: O(1) lookup
- **Hit rate**: Depends on text repetition
- **Risk**: None (deterministic operation)

Best for: Avoiding repeated embedding of static document chunks.

### Retrieval Cache

Cache which chunks were retrieved for a query.

- **Matches**: Queries that would retrieve same chunks
- **Speed**: O(1) lookup
- **Hit rate**: Medium (related queries hit same docs)
- **Risk**: Stale if documents updated

Best for: When retrieval is slow and documents are stable.

---

## The Fundamental Trade-offs

Caching isn't free. Every cache decision involves trade-offs:

### Trade-off 1: Hit Rate vs. Correctness

```
Loose threshold (0.85 similarity):
  + Higher hit rate
  - Returns answers for questions that weren't actually asked
  
Strict threshold (0.98 similarity):
  + Only returns truly equivalent answers
  - Misses many valid cache opportunities
```

There's no universal "right" threshold. It depends on:

- Cost of wrong answer (customer support vs. medical advice)
- Variance in how users phrase questions
- How different queries actually are in your domain

### Trade-off 2: Cache Hit vs. Cache Miss Overhead

Every cache lookup adds latency:

```
Cache hit:   lookup_time + return_cached → ~5ms total
Cache miss:  lookup_time + full_pipeline → ~1005ms total
```

If hit rate is very low, you're adding 5ms to every request for nothing. The break-even math:

```
Cache overhead = lookup_time
Cache savings = hit_rate × (full_latency - lookup_time)

Worth it when: savings > overhead
              hit_rate × (full_latency - lookup_time) > lookup_time
              
With 5ms lookup and 1000ms full latency:
              hit_rate × 995ms > 5ms
              hit_rate > 0.5%
```

Almost always worth it for LLM systems because the full latency is so high.

### Trade-off 3: Freshness vs. Efficiency

Cached answers can become stale:

```
Monday:    User asks "Who is the CEO?"
           → Cache: "Jane Smith"
           
Tuesday:   CEO changes to John Doe
           
Wednesday: User asks "Who is the CEO?"
           → Cache hit: "Jane Smith"  ← WRONG
```

Strategies:

- **Short TTL**: Cache expires quickly, lower hit rate
- **Long TTL**: Higher hit rate, risk of stale data
- **Invalidation**: Explicitly clear cache when data changes (complex)

---

## When Caching Helps Most

Caching ROI depends on your usage patterns:

### High ROI Scenarios

|Factor|Why It Helps|
|---|---|
|**High query repetition**|More cache hits|
|**Stable underlying data**|Less invalidation needed|
|**Latency-sensitive UX**|Users notice the improvement|
|**High query volume**|Fixed cache infrastructure cost amortized|
|**Expensive models**|Higher savings per cache hit|

### Low ROI Scenarios

|Factor|Why It Hurts|
|---|---|
|**Highly unique queries**|Few cache hits|
|**Rapidly changing data**|Constant invalidation|
|**Low query volume**|Overhead isn't justified|
|**Cheap models**|Savings don't offset complexity|

### Quick Assessment

Ask yourself:

1. **What percentage of queries are repeated or similar?**
    
    - < 10%: Caching may not be worth the complexity
    - 10-30%: Exact match cache, maybe semantic
    - 30%+: Full caching strategy justified
2. **How often does your source data change?**
    
    - Hourly: Complex invalidation needed
    - Daily: TTL-based caching works
    - Rarely: Aggressive caching possible
3. **What's your latency budget?**
    
    - Real-time (< 500ms): Caching critical
    - Interactive (< 2s): Caching helpful
    - Batch (minutes): Caching less important
4. **What's your cost sensitivity?**
    
    - Tight budget: Cache aggressively
    - Cost flexible: Optimize for correctness first

---

## Key Takeaways

1. **Caching solves latency, cost, and redundancy** — all three improve with cache hits.
    
2. **LLM systems have unique caching opportunities** — same questions across users, similar questions with same answers, repeated retrieval and embedding computations.
    
3. **Real systems achieve 30-70% hit rates** — the exact rate depends on query patterns and cache strategy.
    
4. **Multiple cache types exist** — exact match, semantic, embedding, and retrieval caches address different stages of the pipeline.
    
5. **Every cache involves trade-offs** — hit rate vs. correctness, cache overhead vs. savings, freshness vs. efficiency.
    
6. **Caching helps most with repetitive queries and stable data** — assess your usage patterns before investing in complex caching infrastructure.
    

---

## What's Next

The following notes cover implementation:

- **Note 2**: Exact match caching — hash-based lookup, key design, TTL strategies
- **Note 3**: Semantic caching — embedding-based similarity, threshold tuning
- **Note 4**: Retrieval and embedding caching — when each matters
- **Note 5**: Cache invalidation — keeping cached answers fresh
- **Note 6**: Multi-level cache integration — combining strategies, measuring savings