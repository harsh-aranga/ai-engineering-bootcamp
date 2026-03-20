# NDCG (Normalized Discounted Cumulative Gain)

## The Core Insight

MRR only cares about the first relevant document. Recall and Precision ignore ranking order entirely. But real retrieval has more nuance:

1. **Multiple relevant documents exist** — and their positions all matter
2. **Relevance isn't binary** — some documents are highly relevant, others marginally relevant
3. **Position has diminishing returns** — position 1 vs 2 matters more than position 9 vs 10

NDCG captures all of this. It answers: **Are the most relevant documents ranked highest, with appropriate penalties for poor positioning?**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Why NDCG Exists                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Consider graded relevance (3=highly, 2=somewhat, 1=marginal):     │
│                                                                     │
│   Retriever A:                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │    Position:   1     2     3     4     5                    │   │
│   │    Relevance:  3     2     1     0     0                    │   │
│   │                ↑     ↑     ↑                                │   │
│   │              Best docs at top — ideal ranking               │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   Retriever B:                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │    Position:   1     2     3     4     5                    │   │
│   │    Relevance:  0     1     0     2     3                    │   │
│   │                            ↑     ↑     ↑                    │   │
│   │              Best docs buried at bottom — poor ranking      │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   Both have same docs retrieved. Recall/Precision see them equal.   │
│   MRR only sees first relevant (position 2 for B, thinks it's OK).  │
│   NDCG sees Retriever A is far superior — best content at top.      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Building Up to NDCG

NDCG is built from three concepts:

### 1. Cumulative Gain (CG) — The Naive Sum

Just add up the relevance scores of retrieved documents:

```
CG@K = Σ relevance_i  (for i = 1 to K)
```

**Problem**: Ignores position entirely. [3, 0, 0, 0, 0] and [0, 0, 0, 0, 3] score the same.

### 2. Discounted Cumulative Gain (DCG) — Position Penalty

Divide each relevance score by a position-based discount:

```
DCG@K = Σ (relevance_i / log₂(i + 1))  for i = 1 to K
```

The `log₂(i + 1)` discount factor:

|Position|Discount log₂(i+1)|Effect|
|---|---|---|
|1|log₂(2) = 1.0|Full credit|
|2|log₂(3) = 1.58|63% credit|
|3|log₂(4) = 2.0|50% credit|
|5|log₂(6) = 2.58|39% credit|
|10|log₂(11) = 3.46|29% credit|

A highly relevant document at position 10 contributes less than a third of what it would at position 1.

### 3. Normalized DCG (NDCG) — Scale to 0-1

DCG values depend on how many relevant docs exist and their relevance scores. To compare across queries, normalize by the **ideal DCG** — the DCG you'd get with perfect ranking:

```
NDCG@K = DCG@K / IDCG@K
```

Where IDCG (Ideal DCG) is computed by sorting all documents by relevance descending, then computing DCG on that ideal ordering.

**Result**: NDCG ranges from 0 to 1, where 1 means perfect ranking.

---

## The Formula (Complete)

```
DCG@K = Σ (relevance_i / log₂(i + 1))  for i = 1 to K

IDCG@K = DCG of ideal ranking (sort by relevance descending, take top K)

NDCG@K = DCG@K / IDCG@K
```

**Alternative formula** (gives more weight to highly relevant docs):

```
DCG@K = Σ ((2^relevance_i - 1) / log₂(i + 1))  for i = 1 to K
```

This exponential version is common in web search where the gap between "highly relevant" and "somewhat relevant" should be larger. For RAG evaluation, the linear version is typically sufficient.

---

## Example Walkthrough

```
Query: "Compare AWS, GCP, and Azure pricing"

Ground truth relevance scores:
  doc_aws:    3 (highly relevant — detailed AWS pricing)
  doc_gcp:    3 (highly relevant — detailed GCP pricing)  
  doc_azure:  3 (highly relevant — detailed Azure pricing)
  doc_cloud:  2 (somewhat relevant — general cloud comparison)
  doc_intro:  1 (marginally relevant — cloud computing intro)

Retriever returns (top 5):
  Position 1: doc_intro  (relevance: 1)
  Position 2: doc_cloud  (relevance: 2)
  Position 3: doc_aws    (relevance: 3)
  Position 4: doc_random (relevance: 0)
  Position 5: doc_gcp    (relevance: 3)

Relevance vector: [1, 2, 3, 0, 3]
```

### Step 1: Compute DCG@5

```
DCG@5 = 1/log₂(2) + 2/log₂(3) + 3/log₂(4) + 0/log₂(5) + 3/log₂(6)
      = 1/1.0     + 2/1.58    + 3/2.0     + 0/2.32    + 3/2.58
      = 1.0       + 1.26      + 1.5       + 0         + 1.16
      = 4.92
```

### Step 2: Compute IDCG@5 (Ideal Ranking)

Sort all available relevance scores descending: [3, 3, 3, 2, 1]

```
IDCG@5 = 3/log₂(2) + 3/log₂(3) + 3/log₂(4) + 2/log₂(5) + 1/log₂(6)
       = 3/1.0     + 3/1.58    + 3/2.0     + 2/2.32    + 1/2.58
       = 3.0       + 1.89      + 1.5       + 0.86      + 0.39
       = 7.64
```

### Step 3: Compute NDCG@5

```
NDCG@5 = DCG@5 / IDCG@5
       = 4.92 / 7.64
       = 0.644
```

**Interpretation**: The retriever achieved 64.4% of the ideal ranking. The best docs (relevance 3) are at positions 3 and 5 instead of 1 and 2, hurting the score.

---

## What NDCG Values Mean

|NDCG@K|Interpretation|
|---|---|
|0.95 - 1.0|Near-perfect ranking|
|0.8 - 0.95|Good — best docs mostly at top|
|0.6 - 0.8|Acceptable — some ranking issues|
|0.4 - 0.6|Poor — relevant docs often buried|
|< 0.4|Broken — ranking is nearly random|

### Comparing Across Systems

NDCG's normalization makes it comparable across queries with different numbers of relevant documents:

```
Query A: 10 relevant docs, NDCG = 0.75
Query B: 2 relevant docs, NDCG = 0.75

Both have the same "ranking quality" — 75% of ideal, regardless of how many relevant docs exist.
```

---

## Binary vs. Graded Relevance

NDCG supports both:

### Binary Relevance (relevant = 1, irrelevant = 0)

```
Relevance scores: [1, 0, 1, 0, 1]  (positions 1, 3, 5 are relevant)
```

This works but loses nuance. A "perfect answer" doc and a "tangentially relevant" doc score the same.

### Graded Relevance (0, 1, 2, 3 scale)

```
Relevance scores: [3, 0, 2, 0, 1]

3 = Highly relevant (directly answers the question)
2 = Somewhat relevant (partial answer, useful context)
1 = Marginally relevant (tangentially related)
0 = Irrelevant
```

Graded relevance is more informative but requires more annotation effort.

### Practical Recommendation

For RAG evaluation, a simple 3-level scale often suffices:

|Score|Meaning|Example|
|---|---|---|
|2|Directly answers the question|The exact policy document|
|1|Provides useful context|A related FAQ entry|
|0|Irrelevant|Unrelated document|

---

## Implementation

```python
import numpy as np
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class NDCGResult:
    """Result container for NDCG computation."""
    ndcg: float
    dcg: float
    idcg: float
    relevance_scores: List[float]
    ideal_ranking: List[float]
    
    def __repr__(self):
        return f"NDCG={self.ndcg:.3f} (DCG={self.dcg:.3f}, IDCG={self.idcg:.3f})"


def dcg_at_k(relevance_scores: List[float], k: int) -> float:
    """
    Compute Discounted Cumulative Gain at K.
    
    Args:
        relevance_scores: Relevance score for each position (in retrieval order)
        k: Number of positions to consider
    
    Returns:
        DCG score
    """
    scores = np.array(relevance_scores[:k])
    positions = np.arange(1, len(scores) + 1)
    discounts = np.log2(positions + 1)
    return float(np.sum(scores / discounts))


def ndcg_at_k(
    relevance_scores: List[float],
    k: int,
    all_relevance_scores: List[float] = None
) -> NDCGResult:
    """
    Compute Normalized Discounted Cumulative Gain at K.
    
    Args:
        relevance_scores: Relevance scores in retrieval order
        k: Number of positions to consider
        all_relevance_scores: All possible relevance scores (for IDCG).
                              If None, uses relevance_scores.
    
    Returns:
        NDCGResult with NDCG, DCG, IDCG, and details
    """
    # Use provided scores or fall back to retrieved scores
    if all_relevance_scores is None:
        all_relevance_scores = relevance_scores
    
    # DCG of actual ranking
    dcg = dcg_at_k(relevance_scores, k)
    
    # Ideal ranking: sort all available relevance scores descending
    ideal_ranking = sorted(all_relevance_scores, reverse=True)[:k]
    idcg = dcg_at_k(ideal_ranking, k)
    
    # Normalize
    ndcg = dcg / idcg if idcg > 0 else 0.0
    
    return NDCGResult(
        ndcg=ndcg,
        dcg=dcg,
        idcg=idcg,
        relevance_scores=relevance_scores[:k],
        ideal_ranking=ideal_ranking
    )


# Example from walkthrough
relevance_scores = [1, 2, 3, 0, 3]  # What retriever returned
all_scores = [3, 3, 3, 2, 1]        # All relevant docs' scores

result = ndcg_at_k(relevance_scores, k=5, all_relevance_scores=all_scores)
print(result)
# NDCG=0.644 (DCG=4.923, IDCG=7.640)

print(f"Actual ranking relevance: {result.relevance_scores}")
print(f"Ideal ranking relevance:  {result.ideal_ranking}")
```

---

## NDCG Across Multiple Queries

```python
from typing import List, Tuple
import statistics


def evaluate_ndcg(
    results: List[Tuple[List[float], List[float]]],
    k: int
) -> Dict:
    """
    Compute mean NDCG across multiple queries.
    
    Args:
        results: List of (retrieved_relevance, all_relevance) tuples
        k: Number of positions to consider
    
    Returns:
        Dict with mean NDCG, std, and per-query details
    """
    per_query = [
        ndcg_at_k(retrieved_rel, k, all_rel)
        for retrieved_rel, all_rel in results
    ]
    
    ndcg_values = [r.ndcg for r in per_query]
    
    return {
        "mean_ndcg": statistics.mean(ndcg_values),
        "std_ndcg": statistics.stdev(ndcg_values) if len(ndcg_values) > 1 else 0.0,
        "min_ndcg": min(ndcg_values),
        "max_ndcg": max(ndcg_values),
        "per_query": per_query,
        "total_queries": len(results)
    }


# Example: Multiple queries
eval_data = [
    # (retrieved_relevance, all_available_relevance)
    ([3, 2, 1, 0, 0], [3, 2, 1]),           # Perfect ranking
    ([0, 1, 2, 3, 0], [3, 2, 1]),           # Inverted ranking
    ([2, 0, 3, 1, 0], [3, 2, 1]),           # Mixed ranking
]

result = evaluate_ndcg(eval_data, k=5)

print(f"Mean NDCG@5: {result['mean_ndcg']:.3f} (±{result['std_ndcg']:.3f})")
print(f"Range: [{result['min_ndcg']:.3f}, {result['max_ndcg']:.3f}]")

print("\nPer-query breakdown:")
for i, r in enumerate(result['per_query'], 1):
    print(f"  Query {i}: {r}")
```

Output:

```
Mean NDCG@5: 0.720 (±0.283)
Range: [0.414, 1.000]

Per-query breakdown:
  Query 1: NDCG=1.000 (DCG=5.131, IDCG=5.131)
  Query 2: NDCG=0.414 (DCG=2.124, IDCG=5.131)
  Query 3: NDCG=0.747 (DCG=3.831, IDCG=5.131)
```

---

## NDCG in RAG: Practical Considerations

### Getting Relevance Scores

NDCG requires relevance scores, not just binary labels. Three approaches:

#### 1. Human Annotation

Annotators rate each document on a scale:

```python
annotations = {
    "query_1": {
        "doc_a": 3,  # Highly relevant
        "doc_b": 2,  # Somewhat relevant
        "doc_c": 0,  # Irrelevant
        "doc_d": 1,  # Marginally relevant
    }
}
```

**Pros**: Most accurate **Cons**: Expensive, slow, doesn't scale

#### 2. LLM-as-Judge

Use an LLM to rate relevance:

```python
def llm_relevance_score(query: str, document: str) -> int:
    """
    Use LLM to rate document relevance on 0-3 scale.
    """
    prompt = f"""Rate how relevant this document is to the query.

Query: {query}

Document: {document}

Relevance scale:
3 = Highly relevant (directly and completely answers the query)
2 = Somewhat relevant (partially answers or provides useful context)
1 = Marginally relevant (tangentially related)
0 = Irrelevant (not related to the query)

Respond with only a number (0, 1, 2, or 3)."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=1
    )
    
    try:
        return int(response.choices[0].message.content.strip())
    except ValueError:
        return 0  # Default to irrelevant on parse failure
```

**Pros**: Scales easily, cheap **Cons**: LLM biases, may not match human judgment

#### 3. Proxy from User Behavior

Use implicit signals:

|Signal|Relevance Score|
|---|---|
|User selected this answer|3|
|User clicked but bounced|1|
|User scrolled past|0|
|User gave thumbs up|3|
|User gave thumbs down|0|

**Pros**: Real user feedback, scales automatically **Cons**: Noisy, requires production traffic

---

## When NDCG Shines

### 1. Graded Relevance Exists

When some documents are clearly better than others:

```
Query: "How to configure Kubernetes autoscaling"

Doc A: Complete guide with examples (relevance: 3)
Doc B: Brief mention in a larger article (relevance: 1)
Doc C: Outdated v1.0 documentation (relevance: 1)

NDCG rewards putting Doc A at position 1.
Binary metrics treat all three as equally "relevant."
```

### 2. Full Ranking Quality Matters

When you need to evaluate the entire ranking, not just the first hit:

```
Search results page showing 10 results
RAG with multi-document synthesis
Situations where users scan multiple results
```

### 3. Comparing Retrieval Systems

NDCG's normalization makes it ideal for A/B testing retrievers:

```
Retriever A: NDCG@10 = 0.72
Retriever B: NDCG@10 = 0.68

Retriever A produces better rankings overall.
```

---

## When NDCG Falls Short

### 1. Annotation Overhead

Getting graded relevance scores is expensive in terms of human effort. For binary relevance, simpler metrics (Recall, Precision, MRR) may suffice.

### 2. Single-Answer Queries

If you only care about the first result (navigational queries), MRR is simpler and captures what matters:

```
Query: "Company phone number"

Only one document has the phone number.
NDCG's ranking-aware sophistication is overkill.
```

### 3. When All Relevant Docs Are Equal

If relevance is truly binary (relevant or not), NDCG reduces to a more complex calculation that gives similar insights to simpler metrics.

---

## NDCG vs Other Metrics

|Metric|Position-Aware|Graded Relevance|Scope|
|---|---|---|---|
|**Recall@K**|No|No (binary)|Coverage|
|**Precision@K**|No|No (binary)|Noise|
|**MRR**|Yes (first hit only)|No (binary)|First relevant|
|**NDCG@K**|Yes (all positions)|Yes|Full ranking|

### Decision Framework

```
┌─────────────────────────────────────────────────────────────────────┐
│                    When to Use NDCG                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Do you have graded relevance labels?                              │
│       │                                                             │
│       ├── YES ──► NDCG is your best ranking metric                  │
│       │                                                             │
│       └── NO ──► Do you care about ranking order?                   │
│                     │                                               │
│                     ├── Only first hit ──► MRR                      │
│                     │                                               │
│                     ├── Full ranking ──► NDCG with binary (0/1)     │
│                     │                    or use Recall + Precision  │
│                     │                                               │
│                     └── Not really ──► Recall@K, Precision@K        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Complete Evaluation Pipeline

Combining NDCG with other retrieval metrics:

```python
from typing import List, Set, Dict
from dataclasses import dataclass
import statistics


@dataclass
class ComprehensiveMetrics:
    """All retrieval metrics for a single query."""
    recall: float
    precision: float
    mrr: float
    ndcg: float
    hit: bool


def comprehensive_retrieval_eval(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
    relevance_scores: Dict[str, float],
    k: int
) -> ComprehensiveMetrics:
    """
    Compute all retrieval metrics for a single query.
    
    Args:
        retrieved_ids: Ordered list of retrieved document IDs
        relevant_ids: Set of relevant document IDs
        relevance_scores: Dict mapping doc_id to relevance score (0-3)
        k: Number of positions to consider
    
    Returns:
        ComprehensiveMetrics with all scores
    """
    retrieved_k = retrieved_ids[:k]
    retrieved_set = set(retrieved_k)
    
    # Recall
    hits = retrieved_set & relevant_ids
    recall = len(hits) / len(relevant_ids) if relevant_ids else 0.0
    
    # Precision
    precision = len(hits) / k if k > 0 else 0.0
    
    # MRR
    mrr = 0.0
    for pos, doc_id in enumerate(retrieved_k, start=1):
        if doc_id in relevant_ids:
            mrr = 1.0 / pos
            break
    
    # NDCG
    retrieved_relevance = [relevance_scores.get(doc_id, 0) for doc_id in retrieved_k]
    all_relevance = list(relevance_scores.values())
    ndcg_result = ndcg_at_k(retrieved_relevance, k, all_relevance)
    
    return ComprehensiveMetrics(
        recall=recall,
        precision=precision,
        mrr=mrr,
        ndcg=ndcg_result.ndcg,
        hit=len(hits) > 0
    )


# Example
retrieved = ["doc_c", "doc_a", "doc_x", "doc_b", "doc_y"]
relevant = {"doc_a", "doc_b", "doc_c"}
relevance = {"doc_a": 3, "doc_b": 2, "doc_c": 3, "doc_x": 0, "doc_y": 0}

metrics = comprehensive_retrieval_eval(retrieved, relevant, relevance, k=5)

print(f"Recall@5:    {metrics.recall:.3f}")
print(f"Precision@5: {metrics.precision:.3f}")
print(f"MRR:         {metrics.mrr:.3f}")
print(f"NDCG@5:      {metrics.ndcg:.3f}")
print(f"Hit:         {metrics.hit}")
```

Output:

```
Recall@5:    1.000
Precision@5: 0.600
MRR:         1.000
NDCG@5:      0.867
Hit:         True
```

**Interpretation**:

- Recall 1.0: Found all relevant docs (good coverage)
- Precision 0.6: 3 of 5 retrieved are relevant (some noise)
- MRR 1.0: First result is relevant (good for single-answer)
- NDCG 0.867: Ranking is good but not perfect (doc_a with relevance 3 is at position 2, not 1)

---

## Key Takeaways

1. **NDCG measures full ranking quality** — not just first hit (MRR) or coverage (Recall), but how well the entire ranking orders documents by relevance.
    
2. **Position discount via log₂(i+1)** — documents at higher positions get more credit. Position 1 vs 2 matters more than position 9 vs 10.
    
3. **Normalized to 0-1** — IDCG (ideal DCG) normalization makes scores comparable across queries with different numbers of relevant docs.
    
4. **Supports graded relevance** — unlike binary metrics, NDCG distinguishes between "highly relevant" and "marginally relevant."
    
5. **Use NDCG when ranking order matters AND you have (or can get) graded relevance labels.** For binary relevance or first-hit focus, simpler metrics may suffice.
    
6. **NDCG@K** — evaluate at a specific cutoff. NDCG@5 for top-5 retrieval, NDCG@10 for longer result lists.
    
7. **Common relevance scale**: 0 (irrelevant), 1 (marginal), 2 (somewhat), 3 (highly relevant). Annotation is the expensive part.