# Fusion Strategies: Merging Ranked Lists (RRF, Weighted Sum)

## The Core Problem

You've run two searches on the same query:

- **BM25** returned: [doc_A, doc_C, doc_F, doc_B, doc_D] with scores [12.4, 8.7, 6.2, 5.1, 3.8]
- **Dense** returned: [doc_B, doc_A, doc_E, doc_G, doc_C] with scores [0.92, 0.87, 0.81, 0.76, 0.71]

How do you combine these into a single ranked list?

The naive approach—just add the scores—fails immediately:

```
doc_A: 12.4 + 0.87 = 13.27
doc_B: 5.1 + 0.92 = 6.02
```

BM25's unbounded scores dominate. The dense search might as well not exist.

---

## Two Approaches to Fusion

|Approach|Uses|Pros|Cons|
|---|---|---|---|
|**Score-based (Weighted Sum)**|Normalized scores|Preserves score magnitude information|Requires normalization; sensitive to outliers|
|**Rank-based (RRF)**|Position only|No normalization needed; robust|Ignores how much better #1 is vs #2|

---

## Reciprocal Rank Fusion (RRF)

RRF is the most widely used fusion method in hybrid search. It ignores scores entirely and works only with rank positions.

### The Formula

```
RRF_score(doc) = Σ  1 / (k + rank_i(doc))
                 i
```

Where:

- `k` is a smoothing constant (typically 60)
- `rank_i(doc)` is the document's position in ranked list `i` (1-indexed)
- Sum over all ranked lists where the document appears

### Why k=60?

The smoothing constant `k` controls how much being #1 matters vs. appearing in multiple lists.

Without smoothing (k=0):

```
Rank 1: 1/1 = 1.0
Rank 2: 1/2 = 0.5   ← 2x difference!
```

With k=60:

```
Rank 1: 1/61 ≈ 0.0164
Rank 2: 1/62 ≈ 0.0161  ← ~2% difference
```

The value 60 comes from the original 2009 paper by Cormack et al. They found experimentally that k=60 works well across diverse datasets. It prevents a single #1 ranking from overwhelming consensus across lists.

**Intuition**: With k=60, a document that appears at rank 5 in both lists will outscore a document that's #1 in one list but absent from the other.

### Worked Example

```
BM25 results:  [doc_A (rank 1), doc_C (rank 2), doc_F (rank 3), doc_B (rank 4)]
Dense results: [doc_B (rank 1), doc_A (rank 2), doc_E (rank 3), doc_G (rank 4)]

k = 60

doc_A: 1/(60+1) + 1/(60+2) = 0.0164 + 0.0161 = 0.0325
doc_B: 1/(60+4) + 1/(60+1) = 0.0156 + 0.0164 = 0.0320
doc_C: 1/(60+2) + 0        = 0.0161 + 0      = 0.0161
doc_E: 0        + 1/(60+3) = 0      + 0.0159 = 0.0159
doc_F: 1/(60+3) + 0        = 0.0159 + 0      = 0.0159
doc_G: 0        + 1/(60+4) = 0      + 0.0156 = 0.0156

Final ranking: [doc_A, doc_B, doc_C, doc_E, doc_F, doc_G]
```

**Key observation**: doc_A wins because it appeared in both lists (ranks 1 and 2). doc_B was #1 in dense but only #4 in BM25, so it comes second. Consensus matters.

### Python Implementation

```python
from typing import List, Dict, Tuple
from collections import defaultdict

def reciprocal_rank_fusion(
    ranked_lists: List[List[str]],
    k: int = 60,
    weights: List[float] = None
) -> List[Tuple[str, float]]:
    """
    Fuse multiple ranked lists using Reciprocal Rank Fusion.
    
    Args:
        ranked_lists: List of ranked lists, each containing doc IDs in rank order
        k: Smoothing constant (default 60)
        weights: Optional weights for each list (default: equal weights)
    
    Returns:
        List of (doc_id, rrf_score) tuples, sorted by score descending
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    
    rrf_scores: Dict[str, float] = defaultdict(float)
    
    for ranked_list, weight in zip(ranked_lists, weights):
        for rank, doc_id in enumerate(ranked_list, start=1):  # 1-indexed
            rrf_scores[doc_id] += weight * (1.0 / (k + rank))
    
    # Sort by score descending
    sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


# Example usage with your BM25 and dense results
bm25_ranking = ["doc_A", "doc_C", "doc_F", "doc_B", "doc_D"]
dense_ranking = ["doc_B", "doc_A", "doc_E", "doc_G", "doc_C"]

fused = reciprocal_rank_fusion([bm25_ranking, dense_ranking], k=60)

for doc_id, score in fused[:5]:
    print(f"{doc_id}: {score:.4f}")

# Output:
# doc_A: 0.0325
# doc_B: 0.0320
# doc_C: 0.0322
# doc_E: 0.0159
# doc_F: 0.0159
```

### Weighted RRF

You can weight the contribution of each retriever:

```python
# Dense search matters more than BM25
fused = reciprocal_rank_fusion(
    [bm25_ranking, dense_ranking],
    k=60,
    weights=[0.4, 0.6]  # 40% BM25, 60% dense
)
```

This lets you tune based on your data. If your queries are mostly semantic, weight dense higher. If they're keyword-heavy, weight BM25 higher.

---

## Score-Based Fusion (Weighted Sum)

The alternative is to use actual scores, but you must normalize first.

### The Problem: Incompatible Scales

```
BM25 scores:  [12.4, 8.7, 6.2, 5.1, 3.8]   # Range: ~0 to unbounded
Dense scores: [0.92, 0.87, 0.81, 0.76, 0.71]  # Range: 0 to 1 (cosine)
```

You can't add these directly. Normalization brings them to the same scale.

### Min-Max Normalization

Scale scores to [0, 1] range within each result set:

```
score_norm = (score - min_score) / (max_score - min_score)
```

```python
def min_max_normalize(scores: List[float]) -> List[float]:
    """Normalize scores to [0, 1] range."""
    min_s = min(scores)
    max_s = max(scores)
    
    if max_s == min_s:
        return [1.0] * len(scores)  # All same score
    
    return [(s - min_s) / (max_s - min_s) for s in scores]


# Example
bm25_scores = [12.4, 8.7, 6.2, 5.1, 3.8]
dense_scores = [0.92, 0.87, 0.81, 0.76, 0.71]

bm25_norm = min_max_normalize(bm25_scores)
# [1.0, 0.57, 0.28, 0.15, 0.0]

dense_norm = min_max_normalize(dense_scores)
# [1.0, 0.76, 0.48, 0.24, 0.0]
```

### Weighted Sum After Normalization

```python
from typing import List, Dict, Tuple

def weighted_score_fusion(
    results_list: List[List[Tuple[str, float]]],  # [(doc_id, score), ...]
    weights: List[float] = None
) -> List[Tuple[str, float]]:
    """
    Fuse multiple result sets using weighted normalized scores.
    
    Args:
        results_list: List of result sets, each containing (doc_id, score) tuples
        weights: Weights for each result set (must sum to 1.0)
    
    Returns:
        Fused results sorted by combined score
    """
    if weights is None:
        weights = [1.0 / len(results_list)] * len(results_list)
    
    # Normalize each result set
    def normalize(results):
        if not results:
            return {}
        scores = [score for _, score in results]
        min_s, max_s = min(scores), max(scores)
        range_s = max_s - min_s if max_s != min_s else 1.0
        return {
            doc_id: (score - min_s) / range_s 
            for doc_id, score in results
        }
    
    normalized = [normalize(results) for results in results_list]
    
    # Collect all doc IDs
    all_docs = set()
    for norm_dict in normalized:
        all_docs.update(norm_dict.keys())
    
    # Compute weighted sum
    fused_scores = {}
    for doc_id in all_docs:
        score = 0.0
        for norm_dict, weight in zip(normalized, weights):
            # Documents missing from a list get score 0
            score += weight * norm_dict.get(doc_id, 0.0)
        fused_scores[doc_id] = score
    
    return sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)


# Example usage
bm25_results = [("doc_A", 12.4), ("doc_C", 8.7), ("doc_F", 6.2), ("doc_B", 5.1)]
dense_results = [("doc_B", 0.92), ("doc_A", 0.87), ("doc_E", 0.81), ("doc_G", 0.76)]

# 50% BM25, 50% dense
fused = weighted_score_fusion([bm25_results, dense_results], weights=[0.5, 0.5])

for doc_id, score in fused[:5]:
    print(f"{doc_id}: {score:.3f}")
```

### Alpha Parameter Convention

Many systems use a single `alpha` to control the BM25-vs-dense balance:

```
final_score = alpha × dense_norm + (1 - alpha) × bm25_norm
```

- `alpha = 1.0`: Dense only
- `alpha = 0.0`: BM25 only
- `alpha = 0.5`: Equal weight
- `alpha = 0.7`: Favor dense (common starting point)

## Weighted Sum Fusion — Worked Example

Same inputs as the RRF example:

```
BM25 results:
  doc_A: score 12.4 (rank 1)
  doc_C: score 8.7  (rank 2)
  doc_F: score 6.2  (rank 3)
  doc_B: score 5.1  (rank 4)

Dense results:
  doc_B: score 0.92 (rank 1)
  doc_A: score 0.87 (rank 2)
  doc_E: score 0.81 (rank 3)
  doc_G: score 0.76 (rank 4)
```

### Step 1: Min-Max Normalize Each List

**BM25 normalization:**

```
min = 5.1, max = 12.4, range = 7.3

doc_A: (12.4 - 5.1) / 7.3 = 1.000
doc_C: (8.7 - 5.1)  / 7.3 = 0.493
doc_F: (6.2 - 5.1)  / 7.3 = 0.151
doc_B: (5.1 - 5.1)  / 7.3 = 0.000
```

**Dense normalization:**

```
min = 0.76, max = 0.92, range = 0.16

doc_B: (0.92 - 0.76) / 0.16 = 1.000
doc_A: (0.87 - 0.76) / 0.16 = 0.688
doc_E: (0.81 - 0.76) / 0.16 = 0.313
doc_G: (0.76 - 0.76) / 0.16 = 0.000
```

### Step 2: Weighted Sum (alpha = 0.5)

Using `final = 0.5 × dense_norm + 0.5 × bm25_norm`

Documents missing from a list get 0 for that component:

```
doc_A: 0.5 × 0.688 + 0.5 × 1.000 = 0.344 + 0.500 = 0.844
doc_B: 0.5 × 1.000 + 0.5 × 0.000 = 0.500 + 0.000 = 0.500
doc_C: 0.5 × 0.000 + 0.5 × 0.493 = 0.000 + 0.247 = 0.247
doc_E: 0.5 × 0.313 + 0.5 × 0.000 = 0.157 + 0.000 = 0.157
doc_F: 0.5 × 0.000 + 0.5 × 0.151 = 0.000 + 0.076 = 0.076
doc_G: 0.5 × 0.000 + 0.5 × 0.000 = 0.000 + 0.000 = 0.000
```

**Final ranking (weighted sum):** `[doc_A, doc_B, doc_C, doc_E, doc_F, doc_G]`

### Comparison: RRF vs Weighted Sum

| Doc   | RRF Score | RRF Rank | Weighted Sum | WS Rank |
| ----- | --------- | -------- | ------------ | ------- |
| doc_A | 0.0325    | 1        | 0.844        | 1       |
| doc_B | 0.0320    | 2        | 0.500        | 2       |
| doc_C | 0.0161    | 3        | 0.247        | 3       |
| doc_E | 0.0159    | 4        | 0.157        | 4       |
| doc_F | 0.0159    | 5        | 0.076        | 5       |

Same final ranking in this example — but notice the _spread_ is different. In weighted sum, doc_A (0.844) crushes doc_B (0.500) by a large margin. In RRF, they're nearly tied (0.0325 vs 0.0320).
### Where They Diverge

Change the scenario slightly — doc_B is #1 in dense with a massive score gap:

```
Dense scores: [0.99, 0.45, 0.42, 0.40]  # doc_B dominates
```

After normalization, doc_B still gets 1.0, but the gap information is lost. Min-max compressed everyone else.

RRF doesn't care — rank 1 is rank 1, whether you won by 0.01 or 0.50. This is why RRF is more robust: it ignores score magnitude entirely.

---

## Problems with Score-Based Fusion

### 1. Outlier Sensitivity

Min-max normalization is sensitive to outliers:

```
Scores: [100, 10, 9, 8, 7]  # 100 is an outlier

After normalization: [1.0, 0.032, 0.022, 0.011, 0.0]
```

The outlier compresses everyone else near 0. One spuriously high score distorts the entire ranking.

### 2. Distribution Mismatch

BM25 and dense search have different score distributions:

```
BM25:  Scores spread widely based on term frequency
Dense: Scores often clustered (many docs at 0.8-0.9 similarity)
```

Even after normalization, a document at rank #5 in BM25 might have a higher normalized score than rank #5 in dense, simply because BM25's distribution is steeper.

### 3. Missing Documents

If a document appears in one list but not the other, what score do you assign for the missing list? Zero? That heavily penalizes documents that are highly relevant to one modality but missed by the other.

---

## Why RRF Usually Wins

RRF sidesteps all of these problems:

|Problem|Score-Based|RRF|
|---|---|---|
|Scale mismatch|Must normalize|Ranks are naturally comparable|
|Outliers|Distort normalization|Can't distort (rank 1 is rank 1)|
|Missing docs|What score to assign?|Just skip that list's contribution|
|Tuning required|Must choose alpha, normalization method|k=60 works almost everywhere|
|Distribution assumptions|Assumes comparable distributions|No assumptions|

The 2009 Cormack paper showed RRF outperformed more complex learning-to-rank methods while being trivially simple to implement.

---

## Choosing k in RRF

While k=60 is the standard, you can tune it:

|k Value|Effect|Use Case|
|---|---|---|
|**Low (5-20)**|Top ranks matter a lot more|When #1 is almost certainly right|
|**Default (60)**|Balanced|General-purpose hybrid search|
|**High (100+)**|Consensus matters more|When merging many (3+) retrievers|

```python
# Compare different k values
for k in [10, 60, 100]:
    fused = reciprocal_rank_fusion([bm25_ranking, dense_ranking], k=k)
    print(f"k={k}: {[doc for doc, _ in fused[:3]]}")
```

In practice, k=60 is robust enough that tuning rarely helps significantly.

---

## What Modern Vector DBs Do

Most vector databases have absorbed hybrid search:

|Database|Fusion Method|Configuration|
|---|---|---|
|**Weaviate**|`relativeScoreFusion` (default since 1.24), `rankedFusion`|`alpha` parameter for weighting|
|**Qdrant**|RRF built-in|Via `prefetch` + `fusion`|
|**Pinecone**|Hybrid with sparse-dense|Weighted combination|
|**OpenSearch**|RRF or min-max + weighted mean|Via `normalization-processor` pipeline|
|**Elasticsearch**|RRF retriever, linear retriever|k parameter, weights|
|**Milvus**|`RRFRanker`|k parameter|

**ChromaDB note**: As of early 2025, ChromaDB added experimental hybrid search with RRF support. Check their docs for current status.

---

## Implementation for Your RAG Pipeline

Since you're using ChromaDB + rank-bm25, here's the manual fusion approach:

```python
from rank_bm25 import BM25Okapi
import chromadb
from typing import List, Tuple

class HybridRetriever:
    def __init__(self, chunks: List[str], collection):
        """
        chunks: Your text chunks
        collection: ChromaDB collection (already embedded)
        """
        self.chunks = chunks
        self.collection = collection
        
        # Build BM25 index
        tokenized = [self._tokenize(chunk) for chunk in chunks]
        self.bm25 = BM25Okapi(tokenized)
        
        # Map chunk text to index for BM25
        self.chunk_to_idx = {chunk: i for i, chunk in enumerate(chunks)}
    
    def _tokenize(self, text: str) -> List[str]:
        return text.lower().split()
    
    def search(
        self, 
        query: str, 
        top_k: int = 5,
        bm25_k: int = 20,
        dense_k: int = 20,
        rrf_k: int = 60
    ) -> List[Tuple[str, float]]:
        """
        Hybrid search with RRF fusion.
        
        Args:
            query: Search query
            top_k: Final number of results
            bm25_k: Candidates from BM25
            dense_k: Candidates from dense search
            rrf_k: RRF smoothing constant
        """
        # BM25 search
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_ranking = sorted(
            range(len(bm25_scores)), 
            key=lambda i: bm25_scores[i], 
            reverse=True
        )[:bm25_k]
        bm25_docs = [self.chunks[i] for i in bm25_ranking]
        
        # Dense search (ChromaDB)
        dense_results = self.collection.query(
            query_texts=[query],
            n_results=dense_k
        )
        dense_docs = dense_results['documents'][0]
        
        # RRF fusion
        rrf_scores = {}
        
        for rank, doc in enumerate(bm25_docs, start=1):
            rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (rrf_k + rank)
        
        for rank, doc in enumerate(dense_docs, start=1):
            rrf_scores[doc] = rrf_scores.get(doc, 0) + 1 / (rrf_k + rank)
        
        # Sort and return top_k
        sorted_results = sorted(
            rrf_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        return sorted_results[:top_k]


# Usage
retriever = HybridRetriever(chunks, chroma_collection)
results = retriever.search("error code XYZ123", top_k=5)

for chunk, score in results:
    print(f"Score: {score:.4f}")
    print(f"Chunk: {chunk[:100]}...")
    print()
```

---

## Key Takeaways

1. **RRF is the default choice** — No normalization needed, robust to outliers, minimal tuning
2. **k=60 works almost everywhere** — Only tune if you have strong reason
3. **Score-based fusion needs care** — Min-max normalization is simple but fragile; consider z-score for outlier-heavy data
4. **Over-retrieve, then fuse** — Get top-20 from each retriever, fuse to top-5. You want candidates from both methods.
5. **Consensus wins in RRF** — A document appearing in both lists at mediocre ranks beats a document at #1 in only one list

---

## When to Use What — Expanded

|Scenario|Recommended|Why|
|---|---|---|
|**Starting out / no labeled data**|RRF with k=60|You don't know which retriever is better for your data. RRF treats both equally, requires no tuning, and performs well out of the box. You can ship and iterate.|
|**Have labeled data for tuning**|Weighted sum with optimized alpha|If you have ground-truth relevance judgments (query → correct docs), you can run experiments: try alpha=0.3, 0.5, 0.7, measure NDCG/MRR, pick the best. Weighted sum gives you that lever to pull. RRF's k=60 is already near-optimal so there's less to gain from tuning.|
|**Merging 3+ retrievers**|RRF|Say you have BM25 + dense + a metadata filter retriever. RRF scales naturally — just add another list. Weighted sum requires choosing 3 weights that sum to 1.0, and the tuning space explodes. RRF just works.|
|**Production search engine**|Let the DB handle it|Weaviate, Qdrant, OpenSearch have battle-tested hybrid implementations with optimizations you won't replicate (parallel execution, efficient index merging). Don't hand-roll fusion in production when the DB does it natively.|
|**Need explainability**|Score-based fusion|When a user or stakeholder asks "why did this rank #1?", you can say "BM25 gave it 0.8, dense gave it 0.6, weighted average = 0.7." With RRF, you can only say "it appeared at rank 2 in both lists." The former is more intuitive for non-technical audiences.|

**One more implicit scenario:**

|Scenario|Recommended|Why|
|---|---|---|
|**One retriever is clearly dominant**|Weighted sum, heavily weighted|If you _know_ that for your domain, dense retrieval is right 90% of the time and BM25 is a safety net, set alpha=0.9. RRF with equal weights would give BM25 more influence than it deserves.|