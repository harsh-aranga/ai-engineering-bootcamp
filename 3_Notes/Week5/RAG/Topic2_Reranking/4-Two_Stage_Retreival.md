# Two-Stage Retrieval: Bi-Encoder Retrieval + Cross-Encoder Reranking

## The Core Pattern

Two-stage retrieval is the **standard production pattern** for high-quality semantic search and RAG systems. It combines the strengths of bi-encoders (speed, scalability) with cross-encoders (accuracy, nuance).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TWO-STAGE RETRIEVAL                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  STAGE 1: RETRIEVAL (Bi-Encoder)                                       │
│  ├── Goal: Maximize RECALL                                             │
│  ├── Input: Query + entire corpus (pre-indexed)                        │
│  ├── Method: ANN search over pre-computed embeddings                   │
│  ├── Output: Top-100 candidates (fast, may include noise)              │
│  └── Latency: ~10-50ms for millions of documents                       │
│                               │                                         │
│                               ▼                                         │
│  STAGE 2: RERANKING (Cross-Encoder)                                    │
│  ├── Goal: Maximize PRECISION                                          │
│  ├── Input: Query + each of the 100 candidates                         │
│  ├── Method: Full transformer inference per (query, doc) pair          │
│  ├── Output: Top-5 to Top-10 (high relevance, noise filtered)          │
│  └── Latency: ~500ms-3s for 100 candidates                             │
│                               │                                         │
│                               ▼                                         │
│  RESULT: Best documents for LLM context                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Why Two Stages?

Neither bi-encoders nor cross-encoders alone solve the retrieval problem:

|Approach|Problem|
|---|---|
|Bi-encoder only|Fast, but lower precision — some irrelevant docs in top-k|
|Cross-encoder only|High precision, but O(N×Q) — can't scale to millions|
|Two-stage|Get recall from bi-encoder, precision from cross-encoder|

### The Math That Makes It Work

For a corpus of 1 million documents:

**Bi-encoder only (top-10):**

- 1 query encoding + ANN search = ~50ms
- May miss relevant docs ranked #11-50

**Cross-encoder only:**

- 1 million forward passes = ~10-100 hours per query
- Completely impractical

**Two-stage (retrieve 100, rerank to 10):**

- Bi-encoder: 1 query encoding + ANN search = ~50ms
- Cross-encoder: 100 forward passes = ~1-3 seconds
- Total: ~1-3 seconds with high recall AND precision

---

## The Recall-Precision Trade-off

### Stage 1: Optimize for Recall

Recall asks: **"Of all relevant documents, how many did we retrieve?"**

In Stage 1, you retrieve more candidates than you need (e.g., 100 when you only want 10). The goal is to ensure the relevant documents are _somewhere_ in this set, even if they're not at the top.

```
Query: "How does RLHF work?"

Bi-encoder top-100:
├── #1: "RLHF overview paper..." ← Relevant
├── #2: "Reward modeling..." ← Relevant  
├── #3: "PPO algorithm basics..." ← Somewhat relevant
├── ...
├── #47: "Human feedback collection..." ← Relevant (would be missed at top-10!)
├── ...
└── #100: "Language model fine-tuning..." ← Marginal
```

If you only retrieved top-10, you'd miss the relevant doc at #47.

### Stage 2: Optimize for Precision

Precision asks: **"Of the documents we return, how many are relevant?"**

The cross-encoder rescores all 100 candidates and surfaces the most relevant ones:

```
Cross-encoder reranking:
├── #1 (was #47): "Human feedback collection..." ← Moved up!
├── #2 (was #1): "RLHF overview paper..."
├── #3 (was #2): "Reward modeling..."
├── #4 (was #15): "InstructGPT methodology..."
├── #5 (was #3): "PPO algorithm basics..."
└── ... (remaining 95 filtered out)
```

The cross-encoder catches that #47 was actually more relevant than many higher-ranked docs.

---

## Implementation

### Complete Two-Stage Pipeline

```python
from sentence_transformers import SentenceTransformer, CrossEncoder, util
import numpy as np

class TwoStageRetriever:
    def __init__(
        self,
        bi_encoder_model: str = "multi-qa-MiniLM-L6-cos-v1",
        cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        retrieval_top_k: int = 100,
        rerank_top_k: int = 10
    ):
        """
        Two-stage retrieval: bi-encoder retrieval + cross-encoder reranking.
        
        Args:
            bi_encoder_model: Model for fast initial retrieval
            cross_encoder_model: Model for accurate reranking
            retrieval_top_k: How many candidates to retrieve (Stage 1)
            rerank_top_k: How many to return after reranking (Stage 2)
        """
        self.bi_encoder = SentenceTransformer(bi_encoder_model)
        self.cross_encoder = CrossEncoder(cross_encoder_model)
        self.retrieval_top_k = retrieval_top_k
        self.rerank_top_k = rerank_top_k
        
        # Will hold pre-computed document embeddings
        self.doc_embeddings = None
        self.documents = None
    
    def index(self, documents: list[str]):
        """
        Pre-compute document embeddings (offline, done once).
        """
        self.documents = documents
        self.doc_embeddings = self.bi_encoder.encode(
            documents,
            convert_to_tensor=True,
            show_progress_bar=True
        )
        print(f"Indexed {len(documents)} documents")
    
    def retrieve(self, query: str) -> list[dict]:
        """
        Stage 1: Fast retrieval with bi-encoder.
        Returns top-k candidates with bi-encoder scores.
        """
        query_embedding = self.bi_encoder.encode(query, convert_to_tensor=True)
        
        hits = util.semantic_search(
            query_embedding,
            self.doc_embeddings,
            top_k=self.retrieval_top_k
        )[0]
        
        # Add document text to results
        for hit in hits:
            hit['text'] = self.documents[hit['corpus_id']]
        
        return hits
    
    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """
        Stage 2: Accurate reranking with cross-encoder.
        Returns top-k candidates with cross-encoder scores.
        """
        # Prepare (query, document) pairs for cross-encoder
        pairs = [(query, cand['text']) for cand in candidates]
        
        # Score all pairs
        cross_scores = self.cross_encoder.predict(pairs)
        
        # Add cross-encoder scores to candidates
        for cand, score in zip(candidates, cross_scores):
            cand['cross_score'] = float(score)
        
        # Sort by cross-encoder score (descending) and take top-k
        reranked = sorted(candidates, key=lambda x: x['cross_score'], reverse=True)
        return reranked[:self.rerank_top_k]
    
    def search(self, query: str) -> list[dict]:
        """
        Full two-stage retrieval pipeline.
        """
        # Stage 1: Retrieve candidates
        candidates = self.retrieve(query)
        
        # Stage 2: Rerank candidates
        results = self.rerank(query, candidates)
        
        return results
```

### Using the Pipeline

```python
# Sample documents
documents = [
    "RLHF (Reinforcement Learning from Human Feedback) trains language models using human preferences.",
    "PPO is a policy gradient algorithm used in reinforcement learning.",
    "GPT-4 was trained using RLHF to align with human values and preferences.",
    "Reward modeling creates a learned reward function from human comparisons.",
    "The Python programming language is known for its readability.",
    "InstructGPT used RLHF to follow instructions more reliably.",
    "Human feedback collection involves showing humans pairs of outputs to compare.",
    "Neural networks consist of interconnected layers of neurons.",
    "Fine-tuning adapts a pre-trained model to a specific task.",
    "Constitutional AI is an alternative to RLHF for alignment.",
]

# Initialize and index
retriever = TwoStageRetriever(
    retrieval_top_k=5,  # Small corpus, so retrieve fewer
    rerank_top_k=3
)
retriever.index(documents)

# Search
query = "How does RLHF work?"
results = retriever.search(query)

print(f"Query: {query}\n")
print("Top results after two-stage retrieval:")
for i, result in enumerate(results, 1):
    print(f"\n{i}. Score: {result['cross_score']:.4f}")
    print(f"   Bi-encoder rank: #{result['corpus_id']+1}")
    print(f"   Text: {result['text'][:80]}...")
```

---

## Choosing the Right Values

### How Many to Retrieve (Stage 1)?

The retrieval count depends on:

|Factor|Lower (50-100)|Higher (200-500)|
|---|---|---|
|Corpus size|< 100K docs|> 1M docs|
|Query ambiguity|Specific queries|Broad queries|
|Bi-encoder quality|High-quality, fine-tuned|General-purpose|
|Latency budget|Tight (< 1s total)|Relaxed (< 5s total)|

**Rule of thumb:** Start with 100, measure recall, increase if you're missing relevant docs.

### How Many to Rerank To (Stage 2)?

|Factor|Lower (3-5)|Higher (10-20)|
|---|---|---|
|LLM context window|Small (4K tokens)|Large (32K+ tokens)|
|Answer complexity|Single fact|Multi-faceted|
|Diversity needs|Single perspective|Multiple sources|

**Rule of thumb:** Match your LLM's effective context usage. If you're stuffing 10 chunks into context, rerank to 10-15 (allowing some buffer).

---

## Latency Breakdown

Understanding where time goes helps optimize:

```
┌──────────────────────────────────────────────────────────────┐
│              LATENCY BREAKDOWN (100 candidates)              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Query encoding (bi-encoder):           ~5-10ms              │
│  ANN search (1M docs):                  ~10-30ms             │
│  ──────────────────────────────────────────────────          │
│  Stage 1 total:                         ~15-40ms             │
│                                                              │
│  Cross-encoder scoring (100 pairs):     ~500-3000ms          │
│  ──────────────────────────────────────────────────          │
│  Stage 2 total:                         ~500-3000ms          │
│                                                              │
│  TOTAL:                                 ~0.5-3s              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Key insight:** Stage 2 dominates. To reduce latency:

1. Retrieve fewer candidates (e.g., 50 instead of 100)
2. Use a faster cross-encoder (e.g., TinyBERT instead of MiniLM-L-12)
3. Batch efficiently on GPU

---

## Hybrid First Stage (BM25 + Dense)

For production systems, the first stage is often **hybrid** — combining BM25 and dense retrieval:

```
┌─────────────────────────────────────────────────────────────┐
│                    HYBRID TWO-STAGE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  STAGE 1A: BM25 Retrieval                                  │
│  └── Top-50 by keyword match                               │
│                               │                             │
│  STAGE 1B: Dense Retrieval   │                             │
│  └── Top-50 by semantic match│                             │
│                               │                             │
│              ┌────────────────┴────────────────┐            │
│              │         FUSION (RRF)            │            │
│              │  Combine and dedupe to top-100  │            │
│              └────────────────┬────────────────┘            │
│                               │                             │
│                               ▼                             │
│  STAGE 2: Cross-Encoder Reranking                          │
│  └── Rerank combined set to top-10                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

This catches both:

- Keyword matches that semantic search might miss (exact product names, codes)
- Semantic matches that keyword search would miss (synonyms, paraphrases)

---

## When to Skip Stage 2

Reranking isn't always necessary:

|Scenario|Skip Reranking?|Reason|
|---|---|---|
|Internal tools, low stakes|✅ Yes|Latency matters more than marginal accuracy|
|High-quality fine-tuned bi-encoder|Maybe|If bi-encoder is domain-specific, reranking adds less value|
|Very small corpus (< 1000 docs)|Consider|Cross-encoder could score entire corpus directly|
|Real-time autocomplete|✅ Yes|Sub-100ms latency required|
|High-stakes decisions (medical, legal)|❌ No|Precision is critical|
|User-facing search|❌ No|Quality perception matters|

---

## Production Considerations

### 1. Caching

If queries repeat, cache reranking results:

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_rerank(query: str, candidate_ids: tuple) -> list:
    # Reranking is expensive, cache results for repeated queries
    ...
```

### 2. Async Reranking

For non-blocking UX, stream initial results while reranking:

```
User submits query
    │
    ├── Immediately: Show "searching..."
    │
    ├── ~50ms: Return bi-encoder results (Stage 1)
    │          └── Display provisional results
    │
    └── ~1-2s: Return reranked results (Stage 2)
               └── Update display with final results
```

### 3. Monitoring

Track both stages:

```python
# Metrics to monitor
- bi_encoder_latency_ms
- cross_encoder_latency_ms  
- retrieval_count (how many candidates retrieved)
- rerank_position_change (avg movement after reranking)
- recall_at_k (if you have relevance labels)
```

### 4. Fallback

If reranking fails or times out, return bi-encoder results:

```python
def search_with_fallback(query: str, timeout_ms: int = 2000):
    candidates = retrieve(query)  # Stage 1
    
    try:
        with timeout(timeout_ms):
            return rerank(query, candidates)  # Stage 2
    except TimeoutError:
        logger.warning("Reranking timed out, returning bi-encoder results")
        return candidates[:rerank_top_k]
```

---

## Key Takeaways

1. **Two-stage is the production standard** — most serious retrieval systems use this pattern
    
2. **Stage 1 (bi-encoder) optimizes recall** — retrieve more than you need, ensure relevant docs are in the set
    
3. **Stage 2 (cross-encoder) optimizes precision** — filter down to only the most relevant
    
4. **Typical numbers: retrieve 50-100, rerank to 5-10** — adjust based on corpus size and latency budget
    
5. **Stage 2 dominates latency** — optimize by retrieving fewer or using faster cross-encoders
    
6. **Hybrid first stage often wins** — BM25 + dense catches both keyword and semantic matches
    
7. **Not always needed** — low-stakes, latency-critical, or small-corpus cases may skip reranking
    

---

## Connection to RAG

In a RAG pipeline, two-stage retrieval feeds the context for generation:

```
User Query
    │
    ▼
┌─────────────────────────┐
│   TWO-STAGE RETRIEVAL   │
│   ├── Bi-encoder: top-100│
│   └── Cross-encoder: top-5│
└───────────┬─────────────┘
            │
            ▼
    Top-5 chunks (high relevance)
            │
            ▼
┌─────────────────────────┐
│    LLM GENERATION       │
│    (context = top-5)    │
└─────────────────────────┘
            │
            ▼
       Answer
```

The quality of retrieval directly impacts answer quality. Two-stage retrieval ensures the LLM receives the most relevant context, reducing hallucination and improving answer accuracy.