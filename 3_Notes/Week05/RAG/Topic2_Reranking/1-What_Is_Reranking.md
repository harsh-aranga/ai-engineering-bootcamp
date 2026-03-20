# What is Reranking and Why It's Required

## The Problem: Initial Retrieval is Fast but Coarse

When you query a vector database, the retrieval step is optimized for **speed**, not **precision**. Here's what's happening under the hood:

1. Your query gets embedded into a vector
2. The database finds the top-k vectors closest to your query (by cosine similarity or similar metric)
3. These results come back in milliseconds — even from millions of documents

**The trade-off:** To achieve this speed, the retriever makes compromises that hurt accuracy.

### Why Initial Retrieval Falls Short

|Limitation|What Happens|Real Impact|
|---|---|---|
|**Information compression**|All meanings of a document get squeezed into a single vector (e.g., 1536 dimensions)|Nuance gets lost; semantically different passages can end up with similar vectors|
|**No query awareness at index time**|Documents are embedded offline, before any query exists|The embedding can't optimize for relevance to _your specific question_|
|**Vocabulary overlap dominance**|Similar surface-level words can score high even if meaning differs|"Apple fruit benefits" retrieves "Apple Inc. benefits package"|
|**Semantic similarity ≠ Answer relevance**|A chunk can be semantically related to the query without containing the answer|"History of neural networks" retrieved for "How to implement a neural network"|

### The Funnel Problem

You have a choice:

- **Retrieve few (top-5):** Fast, but you'll miss relevant documents that ranked #6-20
- **Retrieve many (top-100):** Better recall, but now you're stuffing 100 chunks into your LLM — noise increases, quality drops, costs rise

This is where reranking enters.

---

## What is Reranking?

**Reranking is a second-stage filter that re-evaluates and reorders your initial retrieval results using a more accurate (but slower) model.**

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐     ┌─────────┐
│   Query     │────▶│ Initial Retrieval│────▶│   Reranker   │────▶│   LLM   │
│             │     │  (top 50-100)    │     │  (top 5-10)  │     │         │
└─────────────┘     └─────────────────┘     └──────────────┘     └─────────┘
     Fast                 Fast                   Slow               Slow
   (encode)           (vector search)        (deep scoring)      (generation)
```

**The pattern:** Retrieve many (fast, coarse) → Rerank few (slow, precise) → Send best to LLM

### What the Reranker Does

1. Takes each (query, document) pair from initial retrieval
2. Scores how relevant that specific document is to that specific query
3. Reorders all documents by this new relevance score
4. Returns only the top-k most relevant documents

The key insight: **The reranker sees the query and document together**, allowing it to understand the relationship between them — something the initial retriever cannot do.

---

## Why Reranking Works Better

|Aspect|Initial Retrieval|Reranking|
|---|---|---|
|**Query-document interaction**|None — encoded separately|Full — encoded together|
|**Computation**|Query embedding + ANN search|Full model inference per pair|
|**Scoring**|Vector similarity (geometric)|Learned relevance (semantic)|
|**Speed**|Milliseconds for millions|Seconds for hundreds|
|**When it runs**|Every query|Only on retrieved candidates|

### The Quality-Latency Trade-off

Initial retrieval alone:

- ✅ Fast (< 100ms for millions of docs)
- ❌ Lower precision — top-5 may miss the best chunks

With reranking:

- ✅ Much higher precision — surfaces the truly relevant chunks
- ❌ Adds latency (reranker runs once per candidate document)

**Production reality:** A well-tuned reranking stage can improve answer quality by 10-30% with acceptable latency (~200-500ms for 50-100 candidates).

---

## When to Use Reranking

### You Should Rerank When:

1. **Precision matters more than speed** — User-facing Q&A, research assistants, high-stakes decisions
2. **Your initial retrieval returns noisy results** — Common with ambiguous queries or diverse document collections
3. **Context window is limited** — You can only fit 5 chunks, but need to pick the _best_ 5 from 50 candidates
4. **Hybrid search combines multiple signals** — BM25 + dense retrieval needs a unified ranking
5. **Domain-specific relevance differs from general similarity** — Medical, legal, technical domains where "similar" ≠ "useful"

### You Might Skip Reranking When:

1. **Latency is critical** — Real-time autocomplete, sub-100ms responses
2. **Your retriever is already highly accurate** — Domain-specific fine-tuned embeddings with clean data
3. **Cost is prohibitive** — Reranker API calls add up at scale
4. **Simple queries with clear answers** — "What is the company's return policy?" where top-1 is usually correct

---

## The Two-Stage Retrieval Pattern

This is the standard industry pattern for production RAG:

```
Stage 1: Cast a wide net
├── Retrieve top-50 to top-100 candidates
├── Fast (milliseconds)
├── Prioritizes recall (don't miss relevant docs)
└── Acceptable to include some noise

Stage 2: Filter for precision
├── Rerank candidates to top-5 to top-10
├── Slower (hundreds of milliseconds)
├── Prioritizes precision (only the best docs)
└── Noise is eliminated
```

**Why 50-100 → 5-10?**

- Retrieving 100 ensures you likely _have_ the best documents
- Reranking to 10 ensures you _keep_ only the best documents
- This gives you the recall of 100 with the precision needed for 10

---

## Impact on RAG Quality

### Without Reranking:

- LLM receives top-k by vector similarity
- Some chunks are relevant, some are noise
- Noise dilutes the signal → worse answers
- More hallucination risk when context doesn't contain the answer

### With Reranking:

- LLM receives top-k by _actual relevance_
- Chunks are strongly related to the query
- Cleaner context → better answers
- Reduced hallucination (if the answer exists, it's in the context)

### Research Finding (LitSearch Benchmark, 2024):

- Strong dense retriever: +24.8 pp improvement over BM25 at recall@5
- Adding LLM-based reranker: +4.4 pp additional improvement

The takeaway: **Reranking provides meaningful but incremental improvement on top of a good retriever.** It's not a fix for a broken retrieval stage — it's a refinement for a working one.

---

## Key Takeaways

1. **Initial retrieval is a trade-off:** Speed requires compressing documents into fixed vectors, losing nuance
    
2. **Reranking adds a precision layer:** By examining query-document pairs together, rerankers catch what similarity search misses
    
3. **Two-stage is the production pattern:** Retrieve many, rerank few — get recall and precision
    
4. **It's not magic:** Reranking refines good retrieval; it doesn't fix fundamentally broken retrieval or chunking
    
5. **Trade-off is latency vs. quality:** ~200-500ms added latency for 10-30% better answers is usually worth it in production
    

---
