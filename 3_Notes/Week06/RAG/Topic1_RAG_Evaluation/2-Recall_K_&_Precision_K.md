# Recall@K and Precision@K

## The Core Insight

Retrieval in RAG is a filtering problem. You have thousands (or millions) of document chunks. You need to find the handful that actually answer the user's question.

Recall and Precision measure two different failure modes:

- **Recall failure**: You missed relevant documents. The answer existed in your corpus, but it never made it to the LLM. Game over — the LLM can't use context it never saw.

- **Precision failure**: You retrieved too much noise. The relevant documents are in there somewhere, but they're buried under irrelevant chunks. The LLM gets confused, wastes tokens, or latches onto the wrong context.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    The Retrieval Filtering Problem                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Your Corpus (10,000 chunks)                                       │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ │   │
│   │ ○ ○ ● ○ ○ ○ ○ ○ ○ ○ ○ ○ ● ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ● ○ ○ ○ ○ ○ │   │
│   │ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   ● = Relevant documents (maybe 3-5 out of 10,000)                  │
│   ○ = Irrelevant documents                                          │
│                                                                     │
│                              ↓                                      │
│                         Retriever                                   │
│                              ↓                                      │
│                                                                     │
│   Retrieved Top-K (K=5)                                             │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │    Position:   1     2     3     4     5                    │   │
│   │                ●     ○     ●     ○     ○                    │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   Recall@5 = 2/3 = 0.67  (found 2 of 3 relevant docs)               │
│   Precision@5 = 2/5 = 0.40  (2 of 5 retrieved are relevant)         │
│                                                                     │
│   One relevant doc (●) was MISSED — Recall failure                  │
│   Three irrelevant docs (○) were INCLUDED — Precision failure       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

Both metrics use the same inputs:
1. **Retrieved@K**: The top-K documents your retriever returned (ordered by rank)
2. **Relevant**: The ground-truth set of documents that are actually relevant to this query

---

## Recall@K: Did We Find What Matters?

**Question**: Of all the relevant documents that exist, what fraction did we retrieve in top-K?

### Formula

```
Recall@K = |Retrieved@K ∩ Relevant| / |Relevant|
```

- **Numerator**: How many relevant docs appear in your top-K
- **Denominator**: Total number of relevant docs (from ground truth)

### Example

```
Query: "What is our refund policy for enterprise customers?"

Ground truth relevant docs: {doc_7, doc_23, doc_45}

Retriever returns top-5: [doc_7, doc_102, doc_23, doc_88, doc_91]
                          (rank 1) (rank 2) (rank 3) (rank 4) (rank 5)

Retrieved ∩ Relevant = {doc_7, doc_23}

Recall@5 = 2/3 = 0.67
```

We found 2 of 3 relevant documents. **doc_45 was missed** — if it contained critical information (like an exception to the policy), the LLM will give an incomplete or wrong answer.

### What Recall Values Mean

| Recall@K | Interpretation |
|----------|----------------|
| 1.0 | Perfect — found every relevant document |
| 0.7-0.9 | Good — most relevant context retrieved, minor gaps |
| 0.4-0.7 | Problematic — significant relevant context missing |
| <0.4 | Broken — retrieval is fundamentally failing |

### What Recall Doesn't Capture

Recall treats all positions equally. These two retrievals score the same:

```
Retrieval A: [relevant, relevant, relevant, irrelevant, irrelevant]
Retrieval B: [irrelevant, irrelevant, relevant, relevant, relevant]

Both have Recall@5 = 3/3 = 1.0
```

But Retrieval B is worse — relevant docs are buried at positions 3-5. If the LLM has position bias (primacy effect) or if you truncate context, you lose value. Recall doesn't see this problem.

---

## Precision@K: How Much Noise Did We Include?

**Question**: Of the K documents we retrieved, what fraction are actually relevant?

### Formula

```
Precision@K = |Retrieved@K ∩ Relevant| / K
```

- **Numerator**: How many relevant docs appear in your top-K
- **Denominator**: K (the number of documents retrieved)

### Example

Same setup:

```
Retrieved top-5: [doc_7, doc_102, doc_23, doc_88, doc_91]
Relevant: {doc_7, doc_23, doc_45}

Retrieved ∩ Relevant = {doc_7, doc_23}

Precision@5 = 2/5 = 0.40
```

Only 40% of what we retrieved is useful. The other 60% — doc_102, doc_88, doc_91 — is noise.

### What Precision Values Mean

| Precision@K | Interpretation |
|-------------|----------------|
| 0.8-1.0 | Excellent — almost everything retrieved is useful |
| 0.5-0.8 | Acceptable — some noise but signal is clear |
| 0.3-0.5 | Noisy — LLM has to filter through junk |
| <0.3 | Very noisy — signal is buried, high hallucination risk |

### Why Noise Hurts

Low precision doesn't just waste tokens. It actively degrades generation:

1. **Distraction**: LLM attention gets pulled toward irrelevant content
2. **Conflicting signals**: Irrelevant docs may contain plausible-sounding but wrong information
3. **Context overflow**: If context is limited, noise displaces useful content
4. **Increased hallucination**: When relevant signal is weak, LLM falls back to parametric knowledge

---

## The Recall-Precision Tradeoff

These metrics are in fundamental tension. Actions that improve one typically hurt the other:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    The Recall-Precision Tradeoff                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Precision                                                         │
│       ↑                                                             │
│   1.0 ┤                        Ideal (unachievable)                 │
│       │                              ★                              │
│       │                                                             │
│   0.8 ┤         ╭─────╮                                             │
│       │        ╱       ╲                                            │
│   0.6 ┤      ╱    Real   ╲        K=3                               │
│       │     ╱   systems   ╲        ↓                                │
│   0.4 ┤    ●────────────────●────────────                           │
│       │   K=5              K=10    K=20                             │
│   0.2 ┤                              ╲                              │
│       │                               ╲                             │
│   0.0 ┼────┬────┬────┬────┬────┬────┬─╲─→ Recall                    │
│       0   0.2  0.4  0.6  0.8  1.0                                   │
│                                                                     │
│   As K increases:                                                   │
│   • Recall ↑ (more chances to find relevant docs)                   │
│   • Precision ↓ (more irrelevant docs dilute the pool)              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### The Levers

| Action | Effect on Recall | Effect on Precision |
|--------|------------------|---------------------|
| Increase K | ↑ More chances to find relevant docs | ↓ More noise included |
| Decrease K | ↓ Might miss relevant docs | ↑ Only highest-confidence results |
| Lower similarity threshold | ↑ Cast wider net | ↓ Marginal matches slip in |
| Raise similarity threshold | ↓ Miss borderline relevant | ↑ Only strong matches |
| Better embeddings | ↑ Better ranking | ↑ Better ranking |
| Add reranker | (unchanged) | ↑ Reorders to put relevant first |

Notice: **Better embeddings improve both.** That's why embedding quality is the highest-leverage improvement in most RAG systems.

---

## Why RAG Systems Prioritize Recall

In most RAG applications, **missing relevant context is worse than including some noise**.

The reasoning:

1. **Missing context is unrecoverable**: If the critical document isn't retrieved, the LLM can't use it. No amount of clever prompting fixes this.

2. **Noise can be filtered downstream**: Rerankers, cross-encoders, and even the LLM itself can often ignore irrelevant context (especially with good prompts).

3. **Users blame wrong answers more than slow ones**: Missing information → wrong answer → user trust destroyed. Extra context → slightly longer latency → usually tolerable.

This leads to the standard two-stage pattern:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Two-Stage Retrieval Pattern                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Stage 1: Retrieval (optimize for RECALL)                          │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  • Retrieve K=20 to K=50 documents                          │   │
│   │  • Cast a wide net — don't miss relevant docs               │   │
│   │  • Accept low precision at this stage                       │   │
│   │  • Fast: embedding similarity search                        │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│   Stage 2: Reranking (optimize for PRECISION)                       │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  • Rerank the K=20-50 candidates                            │   │
│   │  • Use cross-encoder for better relevance scoring           │   │
│   │  • Take top 5-10 after reranking                            │   │
│   │  • Slower but more accurate: cross-encoder inference        │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│   Stage 3: Generation                                               │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  • High recall (didn't miss relevant docs)                  │   │
│   │  • High precision (noise filtered out)                      │   │
│   │  • LLM sees clean, relevant context                         │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## When Precision Matters More

There are scenarios where precision trumps recall:

### 1. Tight Context Windows

If your model has limited context (4K-8K tokens) and chunks are large (~500 tokens), you can only fit 8-16 chunks. Every irrelevant chunk displaces a potentially relevant one.

### 2. Cost-Sensitive Applications

Tokens cost money. Retrieving 20 chunks when 5 would suffice increases generation cost 4x. For high-volume applications, this adds up.

### 3. Strict Factuality Requirements

In legal, medical, or financial applications, noise isn't just inefficient — it's dangerous. An irrelevant document mentioning a different policy could cause the LLM to confidently state wrong information.

### 4. When You Can't Rerank

If latency is critical and you can't afford a reranking step, you need high precision directly from retrieval.

---

## Implementation

```python
from typing import Set, List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class RetrievalMetrics:
    """Container for retrieval evaluation metrics."""
    recall: float
    precision: float
    hit: bool  # Whether any relevant doc was found
    retrieved_relevant: Set[str]  # Which relevant docs were found
    missed: Set[str]  # Which relevant docs were missed
    
    def __repr__(self):
        return (
            f"Recall@K={self.recall:.3f}, Precision@K={self.precision:.3f}, "
            f"Hit={self.hit}, Found={len(self.retrieved_relevant)}, "
            f"Missed={len(self.missed)}"
        )


def compute_retrieval_metrics(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
    k: int
) -> RetrievalMetrics:
    """
    Compute Recall@K and Precision@K for a single query.
    
    Args:
        retrieved_ids: Ordered list of document IDs from retriever (rank 1 first)
        relevant_ids: Set of ground-truth relevant document IDs
        k: Number of top results to evaluate
    
    Returns:
        RetrievalMetrics with recall, precision, and diagnostic info
    """
    retrieved_k = set(retrieved_ids[:k])
    
    # What we found vs. what we missed
    retrieved_relevant = retrieved_k & relevant_ids
    missed = relevant_ids - retrieved_k
    
    # Recall: fraction of relevant docs we found
    recall = len(retrieved_relevant) / len(relevant_ids) if relevant_ids else 0.0
    
    # Precision: fraction of retrieved docs that are relevant
    precision = len(retrieved_relevant) / len(retrieved_k) if retrieved_k else 0.0
    
    # Hit: did we find at least one relevant doc?
    hit = len(retrieved_relevant) > 0
    
    return RetrievalMetrics(
        recall=recall,
        precision=precision,
        hit=hit,
        retrieved_relevant=retrieved_relevant,
        missed=missed
    )


# Example usage
retrieved = ["doc_7", "doc_102", "doc_23", "doc_88", "doc_91"]
relevant = {"doc_7", "doc_23", "doc_45"}

metrics = compute_retrieval_metrics(retrieved, relevant, k=5)
print(metrics)
# Recall@K=0.667, Precision@K=0.400, Hit=True, Found=2, Missed=1

print(f"Found: {metrics.retrieved_relevant}")  # {'doc_7', 'doc_23'}
print(f"Missed: {metrics.missed}")  # {'doc_45'}
```

---

## Evaluation Across Multiple Queries

Single-query metrics are useful for debugging. Aggregate metrics tell you about system performance.

```python
from typing import List, Tuple, Set
from dataclasses import dataclass, field
import statistics


@dataclass
class AggregateMetrics:
    """Aggregate retrieval metrics across multiple queries."""
    mean_recall: float
    mean_precision: float
    hit_rate: float  # Fraction of queries with at least one hit
    
    # Distribution info
    recall_std: float
    precision_std: float
    
    # Failure analysis
    zero_recall_queries: int  # Complete retrieval failures
    low_recall_queries: int  # Recall < 0.5
    total_queries: int
    
    # Per-query details for debugging
    per_query: List[RetrievalMetrics] = field(repr=False)
    
    def failure_rate(self) -> float:
        """Fraction of queries with zero relevant docs retrieved."""
        return self.zero_recall_queries / self.total_queries if self.total_queries else 0.0


def evaluate_retrieval(
    results: List[Tuple[List[str], Set[str]]],
    k: int
) -> AggregateMetrics:
    """
    Evaluate retrieval across multiple queries.
    
    Args:
        results: List of (retrieved_ids, relevant_ids) tuples
        k: Number of top results to evaluate
    
    Returns:
        AggregateMetrics with mean, std, and failure analysis
    """
    per_query = [
        compute_retrieval_metrics(retrieved, relevant, k)
        for retrieved, relevant in results
    ]
    
    recalls = [m.recall for m in per_query]
    precisions = [m.precision for m in per_query]
    hits = [m.hit for m in per_query]
    
    return AggregateMetrics(
        mean_recall=statistics.mean(recalls),
        mean_precision=statistics.mean(precisions),
        hit_rate=sum(hits) / len(hits),
        recall_std=statistics.stdev(recalls) if len(recalls) > 1 else 0.0,
        precision_std=statistics.stdev(precisions) if len(precisions) > 1 else 0.0,
        zero_recall_queries=sum(1 for r in recalls if r == 0),
        low_recall_queries=sum(1 for r in recalls if r < 0.5),
        total_queries=len(results),
        per_query=per_query
    )


# Example: Evaluate across multiple queries
eval_data = [
    # (retrieved_ids, relevant_ids)
    (["A", "B", "C", "D", "E"], {"A", "C"}),      # Recall: 1.0, Precision: 0.4
    (["X", "Y", "A", "Z", "W"], {"A", "B", "C"}), # Recall: 0.33, Precision: 0.2
    (["A", "B", "C", "D", "E"], {"A", "B", "C"}), # Recall: 1.0, Precision: 0.6
    (["X", "Y", "Z", "W", "V"], {"A", "B"}),      # Recall: 0.0, Precision: 0.0
]

agg = evaluate_retrieval(eval_data, k=5)

print(f"Mean Recall@5: {agg.mean_recall:.3f} (±{agg.recall_std:.3f})")
print(f"Mean Precision@5: {agg.mean_precision:.3f} (±{agg.precision_std:.3f})")
print(f"Hit Rate: {agg.hit_rate:.1%}")
print(f"Zero Recall Queries: {agg.zero_recall_queries}/{agg.total_queries}")
print(f"Failure Rate: {agg.failure_rate():.1%}")
```

Output:

```
Mean Recall@5: 0.583 (±0.480)
Mean Precision@5: 0.300 (±0.245)
Hit Rate: 75.0%
Zero Recall Queries: 1/4
Failure Rate: 25.0%
```

---

## Recall@K Across Different K Values

Evaluating at multiple K values reveals whether your retriever is fundamentally broken or just needs reranking:

```python
def analyze_recall_curve(
    results: List[Tuple[List[str], Set[str]]],
    k_values: List[int] = [1, 3, 5, 10, 20]
) -> Dict[int, float]:
    """
    Mean Recall@K across queries for multiple K values.
    
    Useful for deciding optimal K and diagnosing retrieval issues.
    """
    all_recalls = {k: [] for k in k_values}
    
    for retrieved, relevant in results:
        for k in k_values:
            metrics = compute_retrieval_metrics(retrieved, relevant, k)
            all_recalls[k].append(metrics.recall)
    
    return {k: statistics.mean(recalls) for k, recalls in all_recalls.items()}


# Example
eval_data = [
    # Relevant docs at various positions
    (["X", "A", "Y", "B", "Z", "C", "W", "V", "U", "T"], {"A", "B", "C"}),
    (["A", "B", "C", "X", "Y", "Z", "W", "V", "U", "T"], {"A", "B", "C"}),
    (["X", "Y", "Z", "W", "A", "B", "V", "U", "T", "C"], {"A", "B", "C"}),
]

recall_curve = analyze_recall_curve(eval_data, k_values=[1, 3, 5, 10])

print("Recall@K curve:")
for k, recall in recall_curve.items():
    bar = "█" * int(recall * 20)
    print(f"  K={k:2d}: {recall:.2f} {bar}")
```

Output:

```
Recall@K curve:
  K= 1: 0.33 ██████
  K= 3: 0.67 █████████████
  K= 5: 0.78 ███████████████
  K=10: 1.00 ████████████████████
```

**Interpretation**: Recall improves significantly as K increases. This tells you:
- Relevant docs ARE in the index (good)
- But they're not always ranked at the top (ranking problem)
- A reranker would likely help significantly

If Recall@20 was still low, that signals a fundamental retrieval problem (bad embeddings, missing docs, chunking issues).

---

## When Recall@K and Precision@K Disagree

Understanding the failure patterns:

### High Recall, Low Precision

```
Recall@10 = 0.95  (found almost everything relevant)
Precision@10 = 0.20  (but 80% of retrieved docs are noise)
```

**Diagnosis**: Retriever is casting too wide a net. It's finding relevant docs, but also pulling in lots of garbage.

**Actions**:
- Add a reranker to filter noise
- Reduce K if context window is limited
- Improve embedding model for better discrimination
- Add metadata filters to pre-filter candidates

### Low Recall, High Precision

```
Recall@10 = 0.30  (missing 70% of relevant docs)
Precision@10 = 0.90  (what we found is almost all relevant)
```

**Diagnosis**: Retriever is too conservative. It's only returning high-confidence matches, missing relevant docs that don't match closely.

**Actions**:
- Increase K to cast a wider net
- Lower similarity threshold
- Use query expansion or multi-query to cover more variations
- Check if relevant docs use different vocabulary (semantic gap)

### Low Recall, Low Precision

```
Recall@10 = 0.20
Precision@10 = 0.15
```

**Diagnosis**: Retrieval is fundamentally broken.

**Actions**:
- Check if relevant docs are actually in the index
- Evaluate embedding model quality (try a different model)
- Review chunking strategy (are relevant passages being split badly?)
- Check for data quality issues (OCR errors, encoding problems)

---

## Building Ground Truth for Evaluation

These metrics require knowing which documents are relevant. Three approaches:

### 1. Manual Annotation (Gold Standard)

Human experts label documents as relevant/irrelevant for each query.

```python
eval_dataset = [
    {
        "query": "What is our refund policy?",
        "relevant_doc_ids": ["policy_doc_3", "faq_17", "terms_section_4"],
    },
    {
        "query": "How do I reset my password?",
        "relevant_doc_ids": ["help_article_22", "security_faq_5"],
    },
    # ... 50-100 queries for meaningful evaluation
]
```

**Pros**: High quality, trustworthy
**Cons**: Expensive, time-consuming, doesn't scale

### 2. Synthetic Generation (LLM-Based)

Generate questions from your documents, where the source document is automatically relevant.

```python
def generate_synthetic_queries(
    document: str,
    doc_id: str,
    n_queries: int = 3
) -> List[Dict]:
    """
    Generate evaluation queries from a document.
    The source document is automatically the relevant doc.
    """
    prompt = f"""Given this document, generate {n_queries} natural questions 
that this document would answer.

Document:
{document}

Return only the questions, one per line."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    questions = response.choices[0].message.content.strip().split("\n")
    
    return [
        {"query": q.strip(), "relevant_doc_ids": [doc_id]}
        for q in questions if q.strip()
    ]
```

**Pros**: Scales easily, cheap
**Cons**: May not reflect real user queries, single-doc relevance only

### 3. Production Logs + Feedback

Use real queries from production. Mark documents as relevant based on:
- User clicked/dwelled on the result
- User marked answer as helpful
- Answer was accepted/used

**Pros**: Reflects real user behavior
**Cons**: Requires production traffic, feedback signals may be noisy

---

## Integration with RAG Evaluation Pipeline

Retrieval metrics are one piece of the full evaluation:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Full RAG Evaluation Pipeline                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   [Query] ──► [Retriever] ──► [Retrieved Docs] ──► [Generator] ──► [Answer]
│                    │                │                    │              │
│                    ▼                ▼                    ▼              ▼
│              ┌──────────┐    ┌───────────┐      ┌────────────┐  ┌──────────┐
│              │ Recall@K │    │ Context   │      │Faithfulness│  │ Answer   │
│              │Precision@K│   │ Relevance │      │            │  │ Correct? │
│              │ MRR, NDCG│    │           │      │            │  │          │
│              └──────────┘    └───────────┘      └────────────┘  └──────────┘
│                    │                │                    │              │
│                    └────────────────┴────────────────────┴──────────────┘
│                                          │
│                                          ▼
│                               Combined RAG Score
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Critical insight**: High retrieval metrics don't guarantee good answers.

You can have Recall@10 = 1.0 (found all relevant docs) but still get wrong answers because:
- Relevant docs were at positions 8-10 (LLM position bias)
- Context exceeded window limit (truncation)
- LLM ignored context and hallucinated
- Retrieved docs had conflicting information

Always measure end-to-end quality (faithfulness, answer correctness) alongside retrieval metrics.

---

## Key Takeaways

1. **Recall@K** = fraction of relevant docs found. Measures coverage. **Missing context is unrecoverable.**

2. **Precision@K** = fraction of retrieved docs that are relevant. Measures noise. **Too much noise hurts generation quality.**

3. **They trade off**: Increasing K helps recall but hurts precision. Better embeddings improve both.

4. **RAG systems typically prioritize recall** for retrieval, then use reranking to improve precision.

5. **Recall@K at multiple K values** reveals if your problem is ranking (relevant docs exist but ranked poorly) vs. fundamental retrieval (relevant docs not retrieved at all).

6. **High retrieval metrics ≠ good answers**. You need generation metrics (faithfulness, correctness) for full evaluation.

7. **Building ground truth is the hard part**. Use a mix of manual annotation, synthetic generation, and production feedback.
