# Hit Rate

## The Core Insight

Hit Rate is the simplest retrieval metric. It answers one binary question: **Did we retrieve at least one relevant document?**

No ranking. No graded relevance. No position awareness. Just: hit or miss.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Hit Rate: Binary Pass/Fail                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Query 1: "refund policy"                                          │
│   Retrieved: [doc_A, doc_B, doc_C, doc_D, doc_E]                    │
│   Relevant:  {doc_C}                                                │
│   doc_C is in retrieved? YES → HIT (1)                              │
│                                                                     │
│   Query 2: "password reset"                                         │
│   Retrieved: [doc_X, doc_Y, doc_Z, doc_W, doc_V]                    │
│   Relevant:  {doc_P, doc_Q}                                         │
│   doc_P or doc_Q in retrieved? NO → MISS (0)                        │
│                                                                     │
│   Query 3: "pricing tiers"                                          │
│   Retrieved: [doc_M, doc_N, doc_O, doc_P, doc_Q]                    │
│   Relevant:  {doc_M, doc_R}                                         │
│   doc_M is in retrieved? YES → HIT (1)                              │
│                                                                     │
│   Hit Rate = 2/3 = 0.667                                            │
│   (67% of queries found at least one relevant document)             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Formula

### Single Query

```
Hit@K = 1 if |Retrieved@K ∩ Relevant| > 0 else 0
```

Binary output: 1 (hit) or 0 (miss).

### Across Multiple Queries

```
Hit Rate@K = (Number of queries with at least one hit) / (Total queries)
```

---

## Example

```
Eval set: 100 queries with labeled relevant documents

Results:
- 85 queries: at least one relevant doc in top-5
- 15 queries: zero relevant docs in top-5

Hit Rate@5 = 85/100 = 0.85
```

85% of queries successfully retrieved at least one relevant document.

---

## What Hit Rate Values Mean

|Hit Rate@K|Interpretation|
|---|---|
|0.95 - 1.0|Excellent — almost never completely failing|
|0.85 - 0.95|Good — occasional misses|
|0.70 - 0.85|Concerning — frequent complete failures|
|< 0.70|Broken — too many queries return nothing useful|

### The Floor Metric

Hit Rate is a **floor**, not a ceiling. It tells you the minimum acceptable performance level:

- Hit Rate = 1.0 does NOT mean your retrieval is good
- Hit Rate = 1.0 only means you're not _completely_ failing on any query

A system with Hit Rate = 1.0 could still have:

- Terrible ranking (relevant doc at position 100)
- Low recall (found 1 of 10 relevant docs)
- Low precision (99 irrelevant docs alongside 1 relevant)

---

## Why Hit Rate Exists

If other metrics are more informative, why use Hit Rate at all?

### 1. Sanity Check

It's the first thing to verify. If Hit Rate is low, nothing else matters — your retrieval is fundamentally broken.

```
Debugging workflow:

Hit Rate@10 = 0.6?
  → Stop. Fix this first.
  → Don't bother tuning rerankers or optimizing NDCG.
  → 40% of queries are complete failures.
```

### 2. Interpretability for Stakeholders

Non-technical stakeholders understand "85% of queries find something relevant" better than "MRR is 0.72" or "NDCG@10 is 0.81."

### 3. Alerting Threshold

Easy to set alerts on:

```python
if hit_rate < 0.90:
    alert("Retrieval quality degraded — hit rate below threshold")
```

### 4. Edge Case Detection

Hit Rate failures are the most severe. Each miss is a query where the user got _nothing_ useful. These deserve individual analysis.

---

## Implementation

```python
from typing import List, Set, Tuple
from dataclasses import dataclass


@dataclass
class HitRateResult:
    """Result container for Hit Rate computation."""
    hit_rate: float
    total_queries: int
    hits: int
    misses: int
    miss_indices: List[int]  # Which queries missed (for debugging)
    
    def __repr__(self):
        return f"Hit Rate@K={self.hit_rate:.3f} ({self.hits}/{self.total_queries} hits)"


def compute_hit(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
    k: int
) -> bool:
    """
    Check if any relevant document appears in top-K.
    
    Args:
        retrieved_ids: Ordered list of retrieved document IDs
        relevant_ids: Set of ground-truth relevant document IDs
        k: Number of top results to consider
    
    Returns:
        True if at least one relevant doc in top-K, else False
    """
    retrieved_k = set(retrieved_ids[:k])
    return len(retrieved_k & relevant_ids) > 0


def compute_hit_rate(
    results: List[Tuple[List[str], Set[str]]],
    k: int
) -> HitRateResult:
    """
    Compute Hit Rate across multiple queries.
    
    Args:
        results: List of (retrieved_ids, relevant_ids) tuples
        k: Number of top results to consider
    
    Returns:
        HitRateResult with hit rate and diagnostic info
    """
    hits = 0
    miss_indices = []
    
    for i, (retrieved, relevant) in enumerate(results):
        if compute_hit(retrieved, relevant, k):
            hits += 1
        else:
            miss_indices.append(i)
    
    total = len(results)
    
    return HitRateResult(
        hit_rate=hits / total if total > 0 else 0.0,
        total_queries=total,
        hits=hits,
        misses=total - hits,
        miss_indices=miss_indices
    )


# Example
eval_data = [
    # (retrieved_ids, relevant_ids)
    (["A", "B", "C", "D", "E"], {"C"}),        # Hit — C is in top-5
    (["X", "Y", "Z", "W", "V"], {"P", "Q"}),   # Miss — neither P nor Q retrieved
    (["M", "N", "O", "P", "Q"], {"M", "R"}),   # Hit — M is in top-5
    (["A", "B", "C", "D", "E"], {"A", "B"}),   # Hit — A and B both in top-5
]

result = compute_hit_rate(eval_data, k=5)
print(result)
# Hit Rate@K=0.750 (3/4 hits)

print(f"Misses at query indices: {result.miss_indices}")
# Misses at query indices: [1]
```

---

## Hit Rate at Different K Values

Like Recall, Hit Rate improves as K increases:

```python
def hit_rate_at_multiple_k(
    results: List[Tuple[List[str], Set[str]]],
    k_values: List[int] = [1, 3, 5, 10, 20]
) -> dict:
    """
    Compute Hit Rate at multiple K values.
    
    Useful for understanding how much K matters for your system.
    """
    return {
        k: compute_hit_rate(results, k).hit_rate
        for k in k_values
    }


# Example
eval_data = [
    # Relevant doc at different positions
    (["X", "Y", "A", "Z", "W", "V", "U", "T", "S", "R"], {"A"}),  # Hit at position 3
    (["X", "Y", "Z", "W", "V", "A", "U", "T", "S", "R"], {"A"}),  # Hit at position 6
    (["X", "Y", "Z", "W", "V", "U", "T", "S", "A", "R"], {"A"}),  # Hit at position 9
    (["X", "Y", "Z", "W", "V", "U", "T", "S", "R", "Q"], {"A"}),  # No hit at all
]

hit_rates = hit_rate_at_multiple_k(eval_data, k_values=[1, 3, 5, 10])

print("Hit Rate@K:")
for k, hr in hit_rates.items():
    bar = "█" * int(hr * 20)
    print(f"  K={k:2d}: {hr:.2f} {bar}")
```

Output:

```
Hit Rate@K:
  K= 1: 0.00 
  K= 3: 0.25 █████
  K= 5: 0.25 █████
  K=10: 0.75 ███████████████
```

**Interpretation**:

- Hit Rate@1 = 0: No query has relevant doc at position 1
- Hit Rate@10 = 0.75: 3 of 4 queries find something in top-10
- The jump from K=5 to K=10 suggests relevant docs are often buried at positions 6-10

---

## Hit Rate vs Recall

They're related but different:

|Metric|Question|Output|
|---|---|---|
|**Hit Rate@K**|Did we find _any_ relevant doc?|Binary (yes/no per query)|
|**Recall@K**|What _fraction_ of relevant docs did we find?|0.0 to 1.0 per query|

```
Query: "Compare cloud providers"
Relevant docs: {aws_doc, gcp_doc, azure_doc}

Retrieved top-5: [aws_doc, random_1, random_2, random_3, random_4]

Hit@5 = 1 (we found at least one)
Recall@5 = 1/3 = 0.33 (we found 1 of 3)
```

**Hit Rate is satisfied with partial success. Recall measures completeness.**

### When They Diverge

```
Scenario A: 100 queries, each has 1 relevant doc
  - 90 queries find their relevant doc
  - Hit Rate@5 = 0.90
  - Mean Recall@5 = 0.90

Scenario B: 100 queries, each has 10 relevant docs
  - 90 queries find at least 1 relevant doc
  - But on average only find 2 of 10
  - Hit Rate@5 = 0.90
  - Mean Recall@5 = 0.20

Same Hit Rate, very different Recall.
```

Scenario B looks fine by Hit Rate but is actually problematic — you're missing 80% of relevant context.

---

## When Hit Rate Is Enough

### 1. Single-Document Queries

When only one document can answer the question:

```
"What is the CEO's phone number?"
"When was the company founded?"
```

If you hit, you have the answer. Recall and ranking don't matter.

### 2. Quick Sanity Checks

Before diving into sophisticated metrics:

```python
def quick_retrieval_check(results, k=10):
    hit_rate = compute_hit_rate(results, k).hit_rate
    
    if hit_rate < 0.8:
        print(f"⚠️  Hit Rate@{k} = {hit_rate:.2f} — retrieval is fundamentally broken")
        print("    Fix this before analyzing other metrics.")
        return False
    
    print(f"✓  Hit Rate@{k} = {hit_rate:.2f} — baseline OK, proceed to detailed analysis")
    return True
```

### 3. Alerting and Monitoring

Simple threshold for production alerts:

```python
# In your monitoring pipeline
if hit_rate_at_k(today_eval_results, k=10) < 0.90:
    send_alert("Retrieval degradation detected")
```

---

## When Hit Rate Hides Problems

### 1. Ranking Disasters

```
Retrieved: [junk, junk, junk, junk, junk, junk, junk, junk, junk, RELEVANT]

Hit@10 = 1 ✓
```

Hit Rate says "pass" but the relevant doc is at position 10. MRR would expose this (RR = 0.1).

### 2. Low Coverage

```
Relevant docs: {A, B, C, D, E, F, G, H, I, J}  (10 docs)
Retrieved: [A, junk, junk, junk, junk]

Hit@5 = 1 ✓
Recall@5 = 0.1 ✗
```

Hit Rate says "pass" but you found 1 of 10 relevant docs. Recall exposes the coverage gap.

### 3. Precision Disasters

```
Relevant: {A}
Retrieved: [A, junk, junk, junk, junk, junk, junk, junk, junk, junk] (100 results)

Hit@100 = 1 ✓
Precision@100 = 0.01 ✗
```

You found it, but buried in 99 irrelevant documents. The LLM will struggle.

---

## Debugging Hit Rate Failures

When Hit Rate is low, each miss deserves investigation:

```python
def analyze_hit_rate_failures(
    results: List[Tuple[List[str], Set[str], str]],  # Added query text
    k: int
) -> List[dict]:
    """
    Analyze queries that completely failed to retrieve relevant docs.
    
    Args:
        results: List of (retrieved_ids, relevant_ids, query_text) tuples
        k: Number of top results to consider
    
    Returns:
        List of failure analysis dicts
    """
    failures = []
    
    for i, (retrieved, relevant, query) in enumerate(results):
        if not compute_hit(retrieved, relevant, k):
            failures.append({
                "query_index": i,
                "query": query,
                "relevant_docs": relevant,
                "retrieved_top_5": retrieved[:5],
                "possible_causes": _diagnose_failure(retrieved, relevant, k)
            })
    
    return failures


def _diagnose_failure(retrieved: List[str], relevant: Set[str], k: int) -> List[str]:
    """Generate possible causes for a retrieval failure."""
    causes = []
    
    # Check if relevant docs appear beyond top-K
    retrieved_all = set(retrieved)
    if retrieved_all & relevant:
        causes.append(f"Relevant doc exists but beyond top-{k} — ranking problem")
    else:
        causes.append("Relevant doc not retrieved at all — embedding or indexing problem")
    
    return causes


# Example usage
eval_data = [
    (["A", "B", "C"], {"A"}, "refund policy"),           # Hit
    (["X", "Y", "Z"], {"P"}, "password reset"),          # Miss
    (["M", "N", "O"], {"M"}, "pricing info"),            # Hit
    (["D", "E", "F", "G", "H", "I", "J", "K", "L", "P"], {"P"}, "shipping times"),  # Miss at k=5, hit at k=10
]

failures = analyze_hit_rate_failures(eval_data, k=5)

print(f"Found {len(failures)} complete failures:\n")
for f in failures:
    print(f"Query: '{f['query']}'")
    print(f"  Relevant docs: {f['relevant_docs']}")
    print(f"  Retrieved top-5: {f['retrieved_top_5']}")
    print(f"  Diagnosis: {f['possible_causes']}")
    print()
```

---

## Hit Rate in the Metrics Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Retrieval Metrics Hierarchy                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Level 1: SANITY CHECK                                             │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Hit Rate@K                                                 │   │
│   │  "Are we completely failing on any queries?"                │   │
│   │  If < 0.9, stop here and fix fundamentals.                  │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│   Level 2: COVERAGE & NOISE                                         │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  Recall@K — Are we finding all relevant docs?               │   │
│   │  Precision@K — Are we avoiding noise?                       │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│   Level 3: RANKING QUALITY                                          │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  MRR — Is the first relevant doc at the top?                │   │
│   │  NDCG@K — Is the full ranking optimal?                      │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   Evaluate top-to-bottom. Don't optimize Level 3 if Level 1 fails. │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **Hit Rate = fraction of queries with at least one relevant doc retrieved.** Binary pass/fail per query.
    
2. **It's a floor metric, not a quality metric.** Hit Rate = 1.0 means you're not completely failing. It doesn't mean you're doing well.
    
3. **Use it as a sanity check first.** If Hit Rate@10 < 0.9, fix fundamental retrieval before optimizing ranking or precision.
    
4. **Easy to explain to stakeholders.** "85% of queries find something relevant" is intuitive.
    
5. **Good for alerting.** Simple threshold: `if hit_rate < 0.90: alert()`
    
6. **Hides ranking and coverage problems.** A relevant doc at position 10 still counts as a hit. Finding 1 of 10 relevant docs still counts as a hit.
    
7. **Debug misses individually.** Each miss is a complete failure. Investigate why those specific queries returned nothing useful.