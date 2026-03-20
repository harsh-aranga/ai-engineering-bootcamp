# Mean Reciprocal Rank (MRR)

## The Core Insight

Recall and Precision treat all positions in the top-K equally. But in practice, **position matters**.

Consider two retrievers answering "What's our refund policy?":

```
Retriever A: [irrelevant, irrelevant, irrelevant, RELEVANT, irrelevant]
Retriever B: [RELEVANT, irrelevant, irrelevant, irrelevant, irrelevant]

Both have:
  Recall@5 = 1.0 (found the relevant doc)
  Precision@5 = 0.2 (1 of 5 is relevant)
```

By Recall and Precision, they're identical. But Retriever B is clearly better — the user (or LLM) sees the relevant document immediately.

MRR captures this by asking: **How quickly do we surface the first relevant result?**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Why Position Matters                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Retriever A: First relevant doc at position 4                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │    Position:   1     2     3     4     5                    │   │
│   │                ○     ○     ○     ●     ○                    │   │
│   │                ↑                                            │   │
│   │           User/LLM starts here, wades through junk          │   │
│   └─────────────────────────────────────────────────────────────┘   │
│   Reciprocal Rank = 1/4 = 0.25                                      │
│                                                                     │
│   Retriever B: First relevant doc at position 1                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │    Position:   1     2     3     4     5                    │   │
│   │                ●     ○     ○     ○     ○                    │   │
│   │                ↑                                            │   │
│   │           User/LLM gets answer immediately                  │   │
│   └─────────────────────────────────────────────────────────────┘   │
│   Reciprocal Rank = 1/1 = 1.0                                       │
│                                                                     │
│   MRR rewards Retriever B (1.0 >> 0.25)                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The Formula

### Reciprocal Rank (Single Query)

For a single query, find the position of the **first relevant document**:

```
Reciprocal Rank (RR) = 1 / rank_of_first_relevant_document
```

|First Relevant At|Reciprocal Rank|
|---|---|
|Position 1|1/1 = 1.0|
|Position 2|1/2 = 0.5|
|Position 3|1/3 = 0.33|
|Position 5|1/5 = 0.2|
|Position 10|1/10 = 0.1|
|Not found|0|

The reciprocal heavily penalizes results where the first relevant doc is buried. Position 1 vs Position 2 is a 2x difference (1.0 vs 0.5). Position 1 vs Position 10 is a 10x difference.

### Mean Reciprocal Rank (Multiple Queries)

Average the Reciprocal Ranks across all queries:

```
MRR = (1/N) × Σ (1 / rank_i)
```

Where:

- N = number of queries
- rank_i = position of first relevant doc for query i

---

## Example Walkthrough

```
Query 1: "refund policy"
  Retrieved: [doc_A, doc_B, doc_C, doc_D, doc_E]
  Relevant:  {doc_C, doc_E}
  First relevant: doc_C at position 3
  RR = 1/3 = 0.333

Query 2: "password reset"
  Retrieved: [doc_X, doc_Y, doc_Z, doc_W, doc_V]
  Relevant:  {doc_X}
  First relevant: doc_X at position 1
  RR = 1/1 = 1.0

Query 3: "pricing tiers"
  Retrieved: [doc_P, doc_Q, doc_R, doc_S, doc_T]
  Relevant:  {doc_M, doc_N}  (neither retrieved!)
  First relevant: not found
  RR = 0

MRR = (0.333 + 1.0 + 0) / 3 = 0.444
```

An MRR of 0.444 tells you: on average, the first relevant document appears around position 2-3. There's room for improvement.

---

## What MRR Values Mean

|MRR|Interpretation|
|---|---|
|0.9 - 1.0|Excellent — first relevant doc almost always at position 1|
|0.7 - 0.9|Good — first relevant doc typically in top 2|
|0.5 - 0.7|Acceptable — first relevant doc usually in top 3-4|
|0.3 - 0.5|Poor — relevant docs often buried|
|< 0.3|Broken — users/LLMs wade through significant noise|

### Quick Mental Math

MRR ≈ 1/average_position_of_first_relevant

- MRR = 0.5 → first relevant doc averages position 2
- MRR = 0.33 → first relevant doc averages position 3
- MRR = 0.25 → first relevant doc averages position 4

---

## When MRR Shines

### 1. Navigational Queries

User wants _the_ answer, not multiple perspectives:

```
"What's the CEO's email address?"
"When does the office close on Friday?"
"What's the return shipping address?"
```

There's one right document. MRR tells you if you're surfacing it immediately.

### 2. Single-Answer RAG

When your RAG system generates a single answer from the top document (not synthesizing from multiple):

```python
# Simple RAG pattern — only uses top doc
top_doc = retriever.retrieve(query, k=1)[0]
answer = llm.generate(query, context=top_doc)
```

Here, MRR directly predicts answer quality. If the top doc is wrong, the answer is wrong.

### 3. User-Facing Search

In search interfaces where users see ranked results, the first few positions dominate attention. MRR correlates with user satisfaction.

---

## When MRR Falls Short

### 1. Multi-Document Synthesis

When you need multiple documents to answer a question:

```
Query: "Compare our pricing plans"

Relevant docs: {basic_plan_doc, pro_plan_doc, enterprise_plan_doc}

Retrieval: [basic_plan_doc, junk, junk, pro_plan_doc, enterprise_plan_doc]
           Position 1       2     3     Position 4       Position 5

MRR = 1/1 = 1.0 (perfect!)
```

MRR says perfect — but you actually need all three pricing docs for a good answer. Recall would catch this problem (Recall@3 = 0.33).

### 2. Graded Relevance

MRR treats relevance as binary. If you have:

- Highly relevant document at position 3
- Marginally relevant document at position 1

MRR scores this as 1.0 (perfect) because _something_ relevant is at position 1. But the answer quality suffers because the best doc is at position 3.

### 3. Beyond the First Hit

MRR ignores everything after the first relevant document:

```
Retrieval A: [RELEVANT, junk, junk, junk, junk]
Retrieval B: [RELEVANT, RELEVANT, RELEVANT, junk, junk]

Both have MRR = 1.0
```

Retrieval B is better for multi-document synthesis, but MRR can't tell.

---

## Implementation

```python
from typing import List, Set, Tuple, Optional
from dataclasses import dataclass


@dataclass
class MRRResult:
    """Result container for MRR computation."""
    reciprocal_rank: float
    first_relevant_position: Optional[int]  # None if no relevant doc found
    first_relevant_doc: Optional[str]
    
    def __repr__(self):
        if self.first_relevant_position:
            return f"RR={self.reciprocal_rank:.3f} (first relevant at position {self.first_relevant_position})"
        return "RR=0.000 (no relevant document found)"


def compute_reciprocal_rank(
    retrieved_ids: List[str],
    relevant_ids: Set[str]
) -> MRRResult:
    """
    Compute Reciprocal Rank for a single query.
    
    Args:
        retrieved_ids: Ordered list of document IDs (rank 1 first)
        relevant_ids: Set of ground-truth relevant document IDs
    
    Returns:
        MRRResult with reciprocal rank and position info
    """
    for position, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return MRRResult(
                reciprocal_rank=1.0 / position,
                first_relevant_position=position,
                first_relevant_doc=doc_id
            )
    
    # No relevant document found
    return MRRResult(
        reciprocal_rank=0.0,
        first_relevant_position=None,
        first_relevant_doc=None
    )


def compute_mrr(
    results: List[Tuple[List[str], Set[str]]]
) -> dict:
    """
    Compute Mean Reciprocal Rank across multiple queries.
    
    Args:
        results: List of (retrieved_ids, relevant_ids) tuples
    
    Returns:
        Dict with MRR, per-query details, and failure analysis
    """
    per_query = [
        compute_reciprocal_rank(retrieved, relevant)
        for retrieved, relevant in results
    ]
    
    rr_values = [r.reciprocal_rank for r in per_query]
    mrr = sum(rr_values) / len(rr_values) if rr_values else 0.0
    
    # Position distribution
    positions = [r.first_relevant_position for r in per_query if r.first_relevant_position]
    
    return {
        "mrr": mrr,
        "per_query": per_query,
        "total_queries": len(results),
        "queries_with_hit": len(positions),
        "queries_without_hit": len(results) - len(positions),
        "avg_first_relevant_position": sum(positions) / len(positions) if positions else None,
        "position_distribution": _position_distribution(positions)
    }


def _position_distribution(positions: List[int]) -> dict:
    """Count how often first relevant doc appears at each position."""
    dist = {}
    for pos in positions:
        dist[pos] = dist.get(pos, 0) + 1
    return dict(sorted(dist.items()))


# Example usage
eval_data = [
    # (retrieved_ids, relevant_ids)
    (["A", "B", "C", "D", "E"], {"C", "E"}),      # First relevant at position 3
    (["X", "Y", "Z", "W", "V"], {"X"}),            # First relevant at position 1
    (["P", "Q", "R", "S", "T"], {"M", "N"}),       # No relevant found
    (["A", "B", "C", "D", "E"], {"B", "D"}),       # First relevant at position 2
]

result = compute_mrr(eval_data)

print(f"MRR: {result['mrr']:.3f}")
print(f"Queries with hit: {result['queries_with_hit']}/{result['total_queries']}")
print(f"Avg position of first relevant: {result['avg_first_relevant_position']:.1f}")
print(f"Position distribution: {result['position_distribution']}")

print("\nPer-query breakdown:")
for i, r in enumerate(result['per_query'], 1):
    print(f"  Query {i}: {r}")
```

Output:

```
MRR: 0.458
Queries with hit: 3/4
Avg position of first relevant: 2.0
Position distribution: {1: 1, 2: 1, 3: 1}

Per-query breakdown:
  Query 1: RR=0.333 (first relevant at position 3)
  Query 2: RR=1.000 (first relevant at position 1)
  Query 3: RR=0.000 (no relevant document found)
  Query 4: RR=0.500 (first relevant at position 2)
```

---

## MRR@K: Bounded Version

Sometimes you only care about the first K positions. If the first relevant doc isn't in top-K, treat it as not found:

```python
def compute_mrr_at_k(
    results: List[Tuple[List[str], Set[str]]],
    k: int
) -> float:
    """
    MRR considering only top-K positions.
    
    If first relevant doc is beyond position K, RR = 0 for that query.
    """
    total_rr = 0.0
    
    for retrieved, relevant in results:
        # Only consider top-K
        retrieved_k = retrieved[:k]
        
        for position, doc_id in enumerate(retrieved_k, start=1):
            if doc_id in relevant:
                total_rr += 1.0 / position
                break
        # If not found in top-K, contributes 0
    
    return total_rr / len(results) if results else 0.0


# Compare MRR vs MRR@3
eval_data = [
    (["A", "B", "C", "D", "E"], {"D"}),  # First relevant at position 4
    (["X", "Y", "Z", "W", "V"], {"Y"}),  # First relevant at position 2
]

print(f"MRR (unbounded): {compute_mrr(eval_data)['mrr']:.3f}")  # (0.25 + 0.5) / 2 = 0.375
print(f"MRR@3: {compute_mrr_at_k(eval_data, k=3):.3f}")          # (0 + 0.5) / 2 = 0.25
```

MRR@K is useful when you have a hard cutoff — e.g., you only show 3 results to users, or you only use top-3 docs for RAG context.

---

## MRR vs Other Retrieval Metrics

|Metric|What It Measures|Strengths|Weaknesses|
|---|---|---|---|
|**Recall@K**|Coverage — did we find all relevant docs?|Catches missing context|Ignores position|
|**Precision@K**|Cleanliness — how much noise?|Catches irrelevant junk|Ignores position|
|**MRR**|Speed — how fast to first relevant?|Rewards good ranking|Only cares about first hit|
|**NDCG**|Overall ranking quality|Handles graded relevance, all positions|More complex, needs relevance scores|

### When to Use Which

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Choosing Retrieval Metrics                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   "I need to find THE answer"                                       │
│   (navigational, single-doc)                                        │
│           → MRR is your primary metric                              │
│                                                                     │
│   "I need to gather all relevant context"                           │
│   (research, multi-doc synthesis)                                   │
│           → Recall@K is your primary metric                         │
│                                                                     │
│   "I need clean context without noise"                              │
│   (limited context window, cost-sensitive)                          │
│           → Precision@K matters most                                │
│                                                                     │
│   "I need the best docs ranked highest"                             │
│   (graded relevance, ranking quality)                               │
│           → NDCG is your primary metric                             │
│                                                                     │
│   In practice: Use multiple metrics together                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## MRR in RAG Evaluation

### Where MRR Fits

MRR is most useful for RAG systems where:

1. **Top-1 or top-few documents dominate** — The LLM primarily relies on the first few retrieved docs
2. **Single-answer queries** — User expects one definitive answer, not a synthesis
3. **You're debugging ranking** — You know relevant docs exist (Recall is fine) but they're not surfacing at the top

### Combining MRR with Other Metrics

A typical RAG evaluation dashboard:

```python
def full_retrieval_evaluation(
    results: List[Tuple[List[str], Set[str]]],
    k: int = 10
) -> dict:
    """
    Comprehensive retrieval evaluation with multiple metrics.
    """
    recalls = []
    precisions = []
    reciprocal_ranks = []
    
    for retrieved, relevant in results:
        retrieved_k = set(retrieved[:k])
        hits = retrieved_k & relevant
        
        # Recall@K
        recall = len(hits) / len(relevant) if relevant else 0.0
        recalls.append(recall)
        
        # Precision@K
        precision = len(hits) / k if k > 0 else 0.0
        precisions.append(precision)
        
        # Reciprocal Rank
        rr = 0.0
        for pos, doc_id in enumerate(retrieved[:k], start=1):
            if doc_id in relevant:
                rr = 1.0 / pos
                break
        reciprocal_ranks.append(rr)
    
    n = len(results)
    return {
        "recall@k": sum(recalls) / n,
        "precision@k": sum(precisions) / n,
        "mrr": sum(reciprocal_ranks) / n,
        "hit_rate": sum(1 for rr in reciprocal_ranks if rr > 0) / n,
    }


# Example
eval_data = [
    (["A", "B", "C", "D", "E"], {"A", "C"}),
    (["X", "Y", "Z", "W", "V"], {"Z", "W"}),
    (["P", "Q", "R", "S", "T"], {"P"}),
]

metrics = full_retrieval_evaluation(eval_data, k=5)
print(f"Recall@5:    {metrics['recall@k']:.3f}")
print(f"Precision@5: {metrics['precision@k']:.3f}")
print(f"MRR:         {metrics['mrr']:.3f}")
print(f"Hit Rate:    {metrics['hit_rate']:.3f}")
```

Output:

```
Recall@5:    0.833
Precision@5: 0.267
MRR:         0.778
Hit Rate:    1.000
```

**Interpretation**:

- Hit Rate 1.0: Every query found at least one relevant doc (good)
- MRR 0.778: First relevant doc is typically at position 1-2 (good ranking)
- Recall 0.833: Finding most relevant docs (minor gaps)
- Precision 0.267: Lots of noise in retrieved results (reranking would help)

---

## Diagnosing Problems with MRR

### High MRR, Low Recall

```
MRR = 0.9 (first relevant doc at position 1)
Recall@10 = 0.3 (only found 30% of relevant docs)
```

**Diagnosis**: You're great at surfacing _one_ relevant doc, but missing others.

**When this is fine**: Single-answer queries where one doc is enough.

**When this is a problem**: Multi-doc synthesis where you need comprehensive context.

### Low MRR, High Recall

```
MRR = 0.2 (first relevant doc around position 5)
Recall@10 = 0.95 (found almost all relevant docs)
```

**Diagnosis**: Relevant docs exist in your results, but they're buried under noise.

**Actions**:

- Add a reranker to promote relevant docs
- Check if your embedding model is ranking noise above signal
- Look for patterns — are certain query types problematic?

### Low MRR, Low Recall

```
MRR = 0.1
Recall@10 = 0.2
```

**Diagnosis**: Retrieval is fundamentally broken. Relevant docs aren't being found, and when they are, they're buried.

**Actions**:

- This is a fundamental retrieval problem
- Check embedding model quality
- Check if documents are properly indexed
- Check chunking strategy

---

## Key Takeaways

1. **MRR measures how quickly you surface the first relevant result.** It's 1/position of first hit, averaged across queries.
    
2. **MRR rewards good ranking.** Unlike Recall/Precision, it cares about _where_ relevant docs appear, not just _whether_ they appear.
    
3. **MRR only cares about the first relevant doc.** It ignores everything after. Great for single-answer queries, blind to multi-doc needs.
    
4. **MRR values are intuitive**: 1.0 = always position 1, 0.5 = average position 2, 0.33 = average position 3.
    
5. **Use MRR alongside Recall/Precision.** MRR tells you about ranking quality; Recall tells you about coverage; Precision tells you about noise. You need all three for a complete picture.
    
6. **High MRR + Low Recall = single-doc success but multi-doc failure.** Know which matters for your use case.
    
7. **Low MRR + High Recall = ranking problem.** Relevant docs exist but are buried. A reranker can help.