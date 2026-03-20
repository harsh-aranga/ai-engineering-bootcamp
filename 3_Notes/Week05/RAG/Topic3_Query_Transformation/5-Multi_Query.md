# Multi-Query Retrieval: Search From Multiple Angles

## The Core Insight

A single query captures a single perspective. But relevant documents might be written from different angles:

```
User query: "ML best practices"

Relevant documents might discuss:
- "machine learning guidelines for production systems"
- "AI model development standards"  
- "tips for training neural networks effectively"
- "common pitfalls in ML projects"
```

One embedding of "ML best practices" won't be equally close to all of these. Each document uses different vocabulary and framing.

Multi-query solves this by generating multiple query variations, retrieving for each, and intelligently merging the results:

```
Original: "ML best practices"
    ↓
Generated variations:
  - "machine learning guidelines for production"
  - "AI model development best practices"
  - "neural network training tips"
  - "common ML pitfalls to avoid"
    ↓
Retrieve for each → 4 result sets
    ↓
Merge with Reciprocal Rank Fusion → Final ranked list
```

Documents that appear highly ranked across multiple query variations rise to the top. You've cast a wider net _and_ identified the most consistently relevant results.

---

## Multi-Query vs. Query Expansion

These are related but distinct:

|Aspect|Query Expansion|Multi-Query|
|---|---|---|
|**Focus**|Add synonyms/terms to enrich _one_ query|Generate _multiple distinct_ queries|
|**Output**|Enriched single query OR term variations|Multiple complete queries (different perspectives)|
|**Goal**|Cover vocabulary gaps|Cover conceptual/perspective gaps|
|**Search**|Often single search with expanded terms|Multiple separate searches, then merge|
|**Example**|"ML" → "ML", "machine learning"|"ML best practices" → "ML guidelines", "AI tips", "model training standards"|

In practice, they're often combined: generate multiple queries, then expand each one.

---

## The RAG-Fusion Technique

RAG-Fusion (Rackauckas, 2024) formalized this pattern:

1. **Generate multiple queries** from the original using an LLM
2. **Retrieve documents** for each query independently
3. **Fuse results** using Reciprocal Rank Fusion (RRF)
4. **Generate answer** using the fused, reranked context

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RAG-Fusion Pipeline                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐                                                   │
│  │ User Query   │                                                   │
│  │ "ML best     │                                                   │
│  │  practices"  │                                                   │
│  └──────┬───────┘                                                   │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────┐                                                   │
│  │ LLM: Generate│──► Q1: "machine learning production guidelines"   │
│  │ Query        │──► Q2: "AI model development best practices"      │
│  │ Variations   │──► Q3: "ML training tips and standards"           │
│  └──────────────┘──► Q4: "common machine learning pitfalls"         │
│                                                                     │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │              Parallel Retrieval                          │      │
│  │  Q1 → [Doc A, Doc C, Doc F, ...]  (ranked by similarity) │      │
│  │  Q2 → [Doc B, Doc A, Doc D, ...]                         │      │
│  │  Q3 → [Doc A, Doc E, Doc B, ...]                         │      │
│  │  Q4 → [Doc C, Doc A, Doc G, ...]                         │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────┐                                                   │
│  │ Reciprocal   │  Doc A appears in all 4 → highest RRF score      │
│  │ Rank Fusion  │  Doc C appears in 2 → medium RRF score           │
│  │ (RRF)        │  Doc G appears in 1 → lower RRF score            │
│  └──────┬───────┘                                                   │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────┐                                                   │
│  │ Final Ranked │  [Doc A, Doc B, Doc C, Doc E, Doc D, ...]        │
│  │ Results      │                                                   │
│  └──────────────┘                                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The key insight: **Doc A appeared highly ranked across all 4 queries**. It's probably genuinely relevant, not just a lucky keyword match.

---

## Reciprocal Rank Fusion (RRF) Explained

RRF is the algorithm that makes multi-query work. It combines multiple ranked lists without needing to normalize incompatible scores.

### The Formula

For each document, sum its reciprocal ranks across all result lists:

```
RRF_score(doc) = Σ  1 / (k + rank_i(doc))
                 i
```

Where:

- `k` is a constant (typically 60)
- `rank_i(doc)` is the document's rank in result list `i` (1-indexed)
- If a document doesn't appear in a list, it's treated as having infinite rank (contributes 0)

### Why It Works

```
Example: Document A appears at:
- Rank 1 in Query 1 results → 1/(60+1) = 0.0164
- Rank 3 in Query 2 results → 1/(60+3) = 0.0159
- Rank 2 in Query 3 results → 1/(60+2) = 0.0161
- Rank 1 in Query 4 results → 1/(60+1) = 0.0164

Total RRF score for Doc A = 0.0164 + 0.0159 + 0.0161 + 0.0164 = 0.0648

Document B appears at:
- Rank 1 in Query 2 results → 1/(60+1) = 0.0164
- Not in other results → 0

Total RRF score for Doc B = 0.0164

Doc A >> Doc B, even though both were #1 somewhere
```

**The magic:** Documents that consistently appear across multiple queries accumulate higher scores than documents that appear #1 in just one query.

### The k Parameter

- **k=60** is the standard default (from the original 2009 paper)
- **Lower k** (e.g., 1-10): Top ranks dominate more. Good when you trust your retrievers.
- **Higher k** (e.g., 100+): Ranks matter less, more uniform weighting. Good when ranks are noisy.

---

## Implementation: Multi-Query Generation

```python
from openai import OpenAI

client = OpenAI()


def generate_query_variations(
    query: str,
    n_variations: int = 3,
    model: str = "gpt-4o-mini"
) -> list[str]:
    """
    Generate multiple query variations from different perspectives.
    """
    prompt = f"""You are a search query generator.

Given the following query, generate {n_variations} alternative versions that:
- Approach the topic from different angles
- Use different vocabulary and phrasing
- Capture different aspects of what the user might be looking for
- Are genuinely distinct (not just synonym swaps)

Original query: {query}

Return only the alternative queries, one per line. Do not include the original query."""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,  # Higher temperature for diversity
        max_tokens=200
    )
    
    variations = response.choices[0].message.content.strip().split("\n")
    variations = [q.strip() for q in variations if q.strip()]
    
    # Always include the original query
    return [query] + variations[:n_variations]


# Example
query = "ML best practices"
variations = generate_query_variations(query, n_variations=3)

print("Generated queries:")
for i, q in enumerate(variations):
    print(f"  {i+1}. {q}")
```

Output:

```
Generated queries:
  1. ML best practices
  2. Machine learning guidelines for production systems
  3. Common pitfalls to avoid in AI model development
  4. Tips for training effective neural network models
```

---

## Implementation: Reciprocal Rank Fusion

```python
from collections import defaultdict
from typing import Any


def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    k: int = 60,
    id_key: str = "id"
) -> list[dict]:
    """
    Combine multiple ranked result lists using Reciprocal Rank Fusion.
    
    Args:
        result_lists: List of result lists, each containing dicts with id_key
        k: RRF constant (default 60)
        id_key: Key to use for document identification
    
    Returns:
        Fused and reranked list of documents
    """
    rrf_scores = defaultdict(float)
    doc_data = {}  # Store full document data
    
    for results in result_lists:
        for rank, doc in enumerate(results, start=1):
            doc_id = doc.get(id_key) or hash(str(doc.get("content", "")))
            
            # Accumulate RRF score
            rrf_scores[doc_id] += 1.0 / (k + rank)
            
            # Store document data (keep most recent)
            doc_data[doc_id] = doc
    
    # Sort by RRF score descending
    sorted_doc_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    # Build final result list with RRF scores
    fused_results = []
    for doc_id in sorted_doc_ids:
        doc = doc_data[doc_id].copy()
        doc["rrf_score"] = rrf_scores[doc_id]
        fused_results.append(doc)
    
    return fused_results


# Example usage
results_q1 = [
    {"id": "A", "content": "Doc A content", "score": 0.95},
    {"id": "C", "content": "Doc C content", "score": 0.88},
    {"id": "F", "content": "Doc F content", "score": 0.82},
]

results_q2 = [
    {"id": "B", "content": "Doc B content", "score": 0.91},
    {"id": "A", "content": "Doc A content", "score": 0.87},
    {"id": "D", "content": "Doc D content", "score": 0.79},
]

results_q3 = [
    {"id": "A", "content": "Doc A content", "score": 0.93},
    {"id": "E", "content": "Doc E content", "score": 0.85},
    {"id": "B", "content": "Doc B content", "score": 0.80},
]

fused = reciprocal_rank_fusion([results_q1, results_q2, results_q3])

print("Fused results:")
for doc in fused[:5]:
    print(f"  {doc['id']}: RRF score = {doc['rrf_score']:.4f}")
```

Output:

```
Fused results:
  A: RRF score = 0.0489  (appeared in all 3 lists)
  B: RRF score = 0.0323  (appeared in 2 lists)
  C: RRF score = 0.0161  (appeared in 1 list at rank 2)
  E: RRF score = 0.0161  (appeared in 1 list at rank 2)
  F: RRF score = 0.0159  (appeared in 1 list at rank 3)
```

---

## Implementation: Complete Multi-Query Retrieval

```python
from openai import OpenAI
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict

client = OpenAI()


class MultiQueryRetriever:
    def __init__(
        self,
        n_queries: int = 3,
        k_per_query: int = 10,
        rrf_k: int = 60,
        model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small"
    ):
        self.n_queries = n_queries
        self.k_per_query = k_per_query
        self.rrf_k = rrf_k
        self.model = model
        self.embedding_model = embedding_model
    
    def retrieve(
        self,
        query: str,
        document_embeddings: np.ndarray,
        documents: list[dict],
        final_k: int = 5
    ) -> list[dict]:
        """
        Retrieve documents using multi-query + RRF.
        
        Args:
            query: Original user query
            document_embeddings: Pre-computed document embeddings
            documents: List of document dicts with 'id' and 'content'
            final_k: Number of final results to return
        
        Returns:
            List of documents ranked by RRF score
        """
        # Step 1: Generate query variations
        queries = self._generate_queries(query)
        print(f"Generated {len(queries)} queries")
        
        # Step 2: Embed all queries
        query_embeddings = self._embed_queries(queries)
        
        # Step 3: Retrieve for each query
        all_results = []
        for i, q_emb in enumerate(query_embeddings):
            results = self._retrieve_single(
                q_emb, document_embeddings, documents, self.k_per_query
            )
            all_results.append(results)
            print(f"  Query {i+1}: retrieved {len(results)} docs")
        
        # Step 4: Fuse with RRF
        fused = self._reciprocal_rank_fusion(all_results)
        
        return fused[:final_k]
    
    def _generate_queries(self, query: str) -> list[str]:
        """Generate query variations using LLM."""
        prompt = f"""Generate {self.n_queries} alternative search queries for:
"{query}"

Each query should approach the topic from a different angle.
Return only the queries, one per line."""

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200
        )
        
        variations = response.choices[0].message.content.strip().split("\n")
        variations = [q.strip() for q in variations if q.strip()]
        
        return [query] + variations[:self.n_queries]
    
    def _embed_queries(self, queries: list[str]) -> list[np.ndarray]:
        """Embed all queries."""
        response = client.embeddings.create(
            input=queries,
            model=self.embedding_model
        )
        return [np.array(e.embedding) for e in response.data]
    
    def _retrieve_single(
        self,
        query_embedding: np.ndarray,
        doc_embeddings: np.ndarray,
        documents: list[dict],
        top_k: int
    ) -> list[dict]:
        """Retrieve top-k documents for a single query embedding."""
        similarities = cosine_similarity(
            query_embedding.reshape(1, -1),
            doc_embeddings
        )[0]
        
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            doc = documents[idx].copy()
            doc["score"] = float(similarities[idx])
            results.append(doc)
        
        return results
    
    def _reciprocal_rank_fusion(
        self,
        result_lists: list[list[dict]]
    ) -> list[dict]:
        """Fuse multiple result lists using RRF."""
        rrf_scores = defaultdict(float)
        doc_data = {}
        
        for results in result_lists:
            for rank, doc in enumerate(results, start=1):
                doc_id = doc.get("id", hash(doc.get("content", "")))
                rrf_scores[doc_id] += 1.0 / (self.rrf_k + rank)
                doc_data[doc_id] = doc
        
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        fused = []
        for doc_id in sorted_ids:
            doc = doc_data[doc_id].copy()
            doc["rrf_score"] = rrf_scores[doc_id]
            fused.append(doc)
        
        return fused


# Usage example
retriever = MultiQueryRetriever(
    n_queries=3,
    k_per_query=10,
    rrf_k=60
)

# Assuming you have pre-computed embeddings and documents
# results = retriever.retrieve(
#     query="ML best practices",
#     document_embeddings=doc_embeddings,
#     documents=documents,
#     final_k=5
# )
```

---

## When Multi-Query Helps

### 1. Broad or Ambiguous Queries

```
Query: "improve performance"
```

This could mean app performance, team performance, database performance, model performance...

Multi-query generates:

- "application speed optimization techniques"
- "team productivity improvement strategies"
- "database query performance tuning"
- "machine learning model accuracy enhancement"

Each variation retrieves different relevant documents. RRF surfaces those that are relevant to _multiple_ interpretations.

### 2. Complex, Multi-Faceted Questions

```
Query: "How do I deploy ML models securely and efficiently?"
```

This has two facets: security AND efficiency. A single query embedding might emphasize one over the other.

Multi-query generates:

- "ML model deployment security best practices"
- "efficient ML model serving and inference optimization"
- "secure machine learning production deployment"
- "low-latency ML inference with security considerations"

### 3. When Users Don't Know the Right Vocabulary

```
Query: "that thing where models forget old stuff when learning new stuff"
```

User doesn't know the term "catastrophic forgetting."

Multi-query might generate:

- "neural network catastrophic forgetting problem"
- "continual learning memory retention"
- "model knowledge retention during fine-tuning"

The LLM translates the casual description into proper terminology across multiple framings.

---

## When Multi-Query Can Hurt

### 1. Query Drift

If generated queries stray too far from the original intent:

```
Original: "Python debugging tools"
Generated (bad): 
- "Python programming language history"
- "software debugging general concepts"
- "Python vs JavaScript comparison"
```

These drift into irrelevant territory. The RRF fusion will pull in off-topic documents.

**Mitigation:** Validate generated queries for relevance (embedding similarity to original), or constrain the generation prompt.

### 2. Diminishing Returns with Too Many Queries

Research shows that beyond 3-5 queries, you get diminishing returns:

- More redundancy between queries
- More off-topic noise
- Higher latency and cost

**Recommendation:** Stick to 3-5 well-crafted variations.

### 3. Specific, Already-Optimal Queries

```
Query: "How do I configure OIDC callback URLs in Kubernetes v1.28?"
```

This is already specific. Generating variations might:

- Remove important specifics ("v1.28")
- Dilute the precision with generic terms

**Mitigation:** Skip multi-query for highly specific queries (detect via heuristics or classifier).

---

## Optimizing Multi-Query

### 1. Filter Generated Queries for Relevance

```python
def filter_queries_by_similarity(
    original_query: str,
    generated_queries: list[str],
    embed_fn,
    min_similarity: float = 0.7
) -> list[str]:
    """
    Filter out generated queries that drift too far from the original.
    """
    original_emb = np.array(embed_fn(original_query))
    
    valid_queries = [original_query]  # Always keep original
    
    for query in generated_queries:
        query_emb = np.array(embed_fn(query))
        similarity = cosine_similarity(
            original_emb.reshape(1, -1),
            query_emb.reshape(1, -1)
        )[0][0]
        
        if similarity >= min_similarity:
            valid_queries.append(query)
        else:
            print(f"Filtered out: '{query}' (similarity: {similarity:.2f})")
    
    return valid_queries
```

### 2. Parallelize Retrieval

Each query can be retrieved independently:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor


async def parallel_retrieve(
    queries: list[str],
    retriever,
    k_per_query: int = 10
) -> list[list[dict]]:
    """
    Retrieve for multiple queries in parallel.
    """
    loop = asyncio.get_event_loop()
    
    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                retriever.retrieve,
                query,
                k_per_query
            )
            for query in queries
        ]
        results = await asyncio.gather(*tasks)
    
    return results
```

### 3. Combine with Reranking

Multi-query + RRF improves recall. Add a cross-encoder reranker to improve precision:

```python
def multi_query_with_reranking(
    query: str,
    retriever,
    reranker,
    n_queries: int = 3,
    retrieve_k: int = 20,
    final_k: int = 5
) -> list[dict]:
    """
    Multi-query retrieval + RRF + cross-encoder reranking.
    """
    # Step 1: Generate query variations
    queries = generate_query_variations(query, n_queries)
    
    # Step 2: Retrieve for each query
    all_results = [retriever.retrieve(q, top_k=retrieve_k) for q in queries]
    
    # Step 3: Fuse with RRF (broad recall)
    fused = reciprocal_rank_fusion(all_results)
    
    # Step 4: Rerank top candidates with cross-encoder (precision)
    # Use ORIGINAL query for reranking, not the variations
    candidates = fused[:retrieve_k]  # Take top candidates from RRF
    
    rerank_pairs = [(query, doc["content"]) for doc in candidates]
    rerank_scores = reranker.predict(rerank_pairs)
    
    # Sort by rerank score
    for doc, score in zip(candidates, rerank_scores):
        doc["rerank_score"] = score
    
    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    
    return candidates[:final_k]
```

This pipeline:

1. Uses multi-query for **broad recall** (find more candidates)
2. Uses RRF to **identify consistently relevant** documents
3. Uses reranker for **final precision** (pick the best ones)

---

## Cost and Latency Considerations

Multi-query adds overhead at every step:

|Step|Single Query|Multi-Query (4 queries)|
|---|---|---|
|Query generation|N/A|~200-300ms (1 LLM call)|
|Query embedding|~50ms|~100ms (4 embeddings, often batched)|
|Retrieval|~30ms|~30ms × 4 = ~120ms (or ~30ms if parallelized)|
|**Total overhead**|~80ms|~230-420ms|

For a high-traffic system (10,000 queries/hour):

- LLM calls for query generation: ~$0.80/hour (gpt-4o-mini)
- 4× embedding cost
- 4× retrieval load

**Optimization strategies:**

1. **Parallelize retrieval** — reduces latency from 4× to ~1×
2. **Cache query variations** — common queries don't need regeneration
3. **Use smaller models** — for query generation, gpt-4o-mini or even local models work fine
4. **Conditional multi-query** — only use for ambiguous/broad queries

```python
def should_use_multi_query(query: str) -> bool:
    """
    Heuristics for when multi-query is worth the cost.
    """
    words = query.split()
    
    # Short queries benefit most from multi-query
    if len(words) <= 4:
        return True
    
    # Broad/ambiguous terms suggest multi-query
    broad_terms = ["best", "good", "improve", "help", "about", "explain"]
    if any(term in query.lower() for term in broad_terms):
        return True
    
    # Highly specific queries don't need multi-query
    specific_indicators = ["version", "v1", "v2", "error", "exception", "configure"]
    if any(ind in query.lower() for ind in specific_indicators):
        return False
    
    return True  # Default to multi-query
```

---

## LangChain's MultiQueryRetriever

LangChain provides a built-in implementation:

```python
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# Setup
embeddings = OpenAIEmbeddings()
vectorstore = Chroma.from_documents(documents, embeddings)
llm = ChatOpenAI(temperature=0.7)

# Create multi-query retriever
retriever = MultiQueryRetriever.from_llm(
    retriever=vectorstore.as_retriever(search_kwargs={"k": 10}),
    llm=llm
)

# Use it
results = retriever.invoke("ML best practices")
```

The `MultiQueryRetriever`:

1. Takes your base retriever
2. Generates multiple queries using the LLM
3. Retrieves for each query
4. Returns the union of results (deduped)

Note: LangChain's default implementation uses simple union, not RRF. For RRF, you'd implement custom logic or use LlamaIndex's `QueryFusionRetriever`.

---

## Key Takeaways

1. **Multi-query generates diverse query variations** to capture different perspectives on the user's intent, then retrieves for each and merges results.
    
2. **Reciprocal Rank Fusion (RRF)** is the key algorithm — it combines ranked lists by summing reciprocal ranks, favoring documents that appear highly across multiple queries.
    
3. **RRF formula:** `score(doc) = Σ 1/(k + rank_i(doc))` where k=60 is the typical default.
    
4. **Most effective for:** broad/ambiguous queries, multi-faceted questions, and when users don't know the right vocabulary.
    
5. **Can hurt when:** generated queries drift off-topic, too many queries cause redundancy/noise, or the original query is already highly specific.
    
6. **Stick to 3-5 query variations** — beyond that, diminishing returns and increased noise.
    
7. **Combine with reranking** for best results: multi-query for recall, RRF for consistency, cross-encoder for final precision.
    
8. **Cost/latency scales linearly** with query count — parallelize retrieval and use conditional multi-query for optimization.