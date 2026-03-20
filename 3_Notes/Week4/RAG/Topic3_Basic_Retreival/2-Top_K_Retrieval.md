# Top-K Retrieval: How Many Chunks to Retrieve

## The Core Trade-off

There's a trade-off of selecting top-k contexts: a smaller k compromises the recall, while a larger k could introduce irrelevant or noisy context and mislead the LLM generation.

This is the fundamental tension in RAG retrieval:

- **Too few chunks (low k)**: You might miss the chunk that contains the answer
- **Too many chunks (high k)**: You flood the LLM with noise, degrading answer quality

LLMs are not good at reading too many chunked contexts (e.g., top-100) even with the long-context window, not only due to efficiency reasons, but also because a shorter list of top-k (e.g., 5, 10) contexts usually leads to higher accuracy of generation.

---

## The Research Consensus: 5-10 is the Sweet Spot

Multiple studies converge on this finding:

According to Xu et al. (2024b), selecting the top 5 to 10 chunks typically yields strong performance, while retrieving more than 20 chunks leads to diminished results.

The optimal number of chunked context k is around 10 for long document QA tasks.

**Why does performance degrade beyond ~10-20 chunks?**

1. **Lost in the middle**: LLMs struggle to attend to information in the middle of the context
2. **Signal-to-noise ratio**: More chunks = more irrelevant content diluting the useful information
3. **Attention saturation**: Even with 128K context windows, the model can't equally attend to everything

---

## Context Window Budget Calculation

Before choosing k, do the math:

```python
def calculate_retrieval_budget(
    context_window: int,
    system_prompt_tokens: int,
    query_tokens: int,
    response_budget: int,
    chunk_size: int,
    safety_margin: float = 0.9  # Leave 10% buffer
) -> int:
    """Calculate how many chunks can fit in context."""
    
    available = int(context_window * safety_margin)
    used = system_prompt_tokens + query_tokens + response_budget
    remaining = available - used
    
    max_chunks = remaining // chunk_size
    
    return max_chunks

# Example: GPT-4o-mini with 128K context
max_k = calculate_retrieval_budget(
    context_window=128_000,
    system_prompt_tokens=500,
    query_tokens=50,
    response_budget=1000,
    chunk_size=512
)
print(f"Maximum chunks that fit: {max_k}")  # ~220 chunks

# But you shouldn't use all of them!
recommended_k = min(max_k, 10)  # Cap at research-backed optimal
```

**Key insight**: Just because you CAN fit 200 chunks doesn't mean you SHOULD. The performance quickly saturates with increased k in practice.

---

## The Chunk Size × Top-K Interaction

These parameters are interdependent:

|Chunk Size|Typical Top-K|Total Context|Trade-off|
|---|---|---|---|
|128 tokens|10-20|1,280-2,560|Granular but may miss context|
|256 tokens|5-10|1,280-2,560|Balanced|
|512 tokens|3-7|1,536-3,584|More context per chunk|
|1024 tokens|2-5|2,048-5,120|Full paragraphs/sections|

A small chunk_size, like 128, yields more granular chunks. This granularity, however, presents a risk: vital information might not be among the top retrieved chunks, especially if the similarity_top_k setting is as restrictive as 2.

**Rule of thumb**: Smaller chunks require higher k to capture sufficient context.

---

## Dynamic vs. Static Top-K

### Static Top-K (Naive Approach)

```python
# Always retrieve exactly 5 chunks
results = collection.query(query_embedding, n_results=5)
```

Problems:

- Simple factual queries might need only 1 chunk
- Complex analytical queries might need 15
- One-size-fits-all wastes tokens or misses information

### Dynamic Top-K Strategies

**Strategy 1: Query Complexity Classification**

A dynamic paradigm through training a cross-encoder that adeptly adjusts the retrieval breadth in real-time. By evaluating the intricacy of each query, the system predicts the most appropriate top-k value for retrieval.

```python
def estimate_query_complexity(query: str) -> str:
    """Classify query complexity to determine k."""
    
    # Simple heuristics (production would use a classifier)
    word_count = len(query.split())
    has_comparison = any(w in query.lower() for w in ["compare", "difference", "vs", "versus"])
    has_aggregation = any(w in query.lower() for w in ["all", "every", "list", "summarize"])
    
    if has_aggregation:
        return "high"  # Needs many chunks
    elif has_comparison:
        return "medium"  # Needs chunks from multiple topics
    elif word_count < 10:
        return "low"  # Likely a specific fact
    else:
        return "medium"

def get_dynamic_k(complexity: str) -> int:
    return {"low": 3, "medium": 7, "high": 15}[complexity]
```

**Strategy 2: Score-Based Cutoff**

Instead of fixed k, retrieve until scores drop below a threshold:

```python
def retrieve_with_threshold(
    collection,
    query_embedding,
    max_k: int = 20,
    min_score: float = 0.7,
    min_results: int = 2
) -> list:
    """Retrieve chunks above score threshold."""
    
    results = collection.query(
        query_embedding,
        n_results=max_k,
        include=["distances"]  # ChromaDB returns distances, not similarities
    )
    
    # Convert distance to similarity (for cosine)
    # ChromaDB distance = 1 - cosine_similarity for cosine space
    similarities = [1 - d for d in results["distances"][0]]
    
    # Filter by threshold, but ensure minimum results
    filtered = []
    for i, (doc, score) in enumerate(zip(results["documents"][0], similarities)):
        if score >= min_score or len(filtered) < min_results:
            filtered.append({"content": doc, "score": score})
    
    return filtered
```

---

## The Reranking Pattern: Retrieve More, Use Less

With reranking, you will have a higher top K retrieval, then rerank the documents and use the top N for generation.

This is the standard production pattern:

```
Query → Retrieve top-50 (broad net) → Rerank → Keep top-5 (precision)
```

Why this works:

1. **Bi-encoder retrieval is fast but imprecise** — casting a wide net is cheap
2. **Cross-encoder reranking is slow but accurate** — worth it for small candidate set
3. **Final k to LLM stays small** — maintains generation quality

```python
from sentence_transformers import CrossEncoder

def retrieve_with_rerank(
    query: str,
    collection,
    embed_model,
    rerank_model: CrossEncoder,
    initial_k: int = 50,
    final_k: int = 5
) -> list:
    """Two-stage retrieval: broad retrieval + precise reranking."""
    
    # Stage 1: Fast bi-encoder retrieval (cast wide net)
    query_embedding = embed_model.encode(query)
    candidates = collection.query(query_embedding, n_results=initial_k)
    
    # Stage 2: Slow cross-encoder reranking (precision)
    pairs = [(query, doc) for doc in candidates["documents"][0]]
    rerank_scores = rerank_model.predict(pairs)
    
    # Sort by rerank score, keep top-N
    ranked = sorted(
        zip(candidates["documents"][0], rerank_scores),
        key=lambda x: x[1],
        reverse=True
    )
    
    return [doc for doc, score in ranked[:final_k]]
```

NVIDIA standardized their RAG pipeline evaluation with retrieval top-k: 10 (number of retrieved contexts for generation).

---

## Adjacent Chunk Retrieval: The "Neighbor" Pattern

When performing retrieval, you could retrieve the top K = 2 chunks, and for each retrieval chunk, retrieve the adjacent chunks as well. If when analyzing your retrievals you notice that the model often misses important information because it's in the adjacent chunk, this could be a good strategy to try.

This addresses a fundamental chunking problem: relevant information often spans chunk boundaries.

```python
def retrieve_with_neighbors(
    collection,
    query_embedding,
    k: int = 3,
    neighbor_window: int = 1  # 1 chunk before and after
) -> list:
    """Retrieve chunks plus their neighbors."""
    
    # Get initial matches with metadata
    results = collection.query(
        query_embedding,
        n_results=k,
        include=["metadatas", "documents"]
    )
    
    expanded_chunks = []
    seen_ids = set()
    
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        doc_id = meta.get("document_id")
        chunk_idx = meta.get("chunk_index")
        
        # Get neighbor indices
        neighbor_indices = range(
            max(0, chunk_idx - neighbor_window),
            chunk_idx + neighbor_window + 1
        )
        
        for idx in neighbor_indices:
            chunk_id = f"{doc_id}_{idx}"
            if chunk_id not in seen_ids:
                # Fetch neighbor chunk from collection
                neighbor = get_chunk_by_index(collection, doc_id, idx)
                if neighbor:
                    expanded_chunks.append(neighbor)
                    seen_ids.add(chunk_id)
    
    return expanded_chunks
```

---

## Small-to-Big Retrieval

"Small-to-big" is a RAG technique which involves chunking small, retrieving big. This approach can help the model focus on specific parts of the document while still providing context.

The idea: embed small chunks for precise matching, but return larger chunks for context.

```python
# Index structure:
# - Small chunks (256 tokens) with embeddings
# - Each small chunk links to its parent big chunk (1024 tokens)

def small_to_big_retrieve(
    collection,  # Contains small chunks
    big_chunk_store,  # Contains parent chunks
    query_embedding,
    k: int = 5
) -> list:
    """Retrieve on small chunks, return big chunks."""
    
    # Search small chunks
    small_results = collection.query(query_embedding, n_results=k * 2)
    
    # Get unique parent chunk IDs
    parent_ids = set()
    for meta in small_results["metadatas"][0]:
        parent_ids.add(meta["parent_chunk_id"])
    
    # Fetch big chunks (deduplicated)
    big_chunks = []
    for parent_id in list(parent_ids)[:k]:
        big_chunk = big_chunk_store.get(parent_id)
        big_chunks.append(big_chunk)
    
    return big_chunks
```

One reason we want to embed and index smaller chunks is due to the fact that current embedding models are not keeping up with LLMs in terms of context length. Another reason is that there can actually be retrieval benefits in having multiple granular embedding representations compared to a single document-level embedding for a document.

---

## When NOT to Retrieve

Sometimes retrieval isn't needed at all.

Not all queries are created equal — some don't even need retrieval because the large language model already knows the answer. For example, if you ask "Who is Messi?" the LLM's got you covered. No retrieval needed!

Production systems often classify queries first:

```python
def needs_retrieval(query: str, llm_client) -> bool:
    """Determine if query needs RAG or direct LLM answer."""
    
    classification_prompt = """
    Classify if this query requires external document retrieval:
    - "RETRIEVAL" if it asks about specific documents, proprietary data, or recent events
    - "DIRECT" if it's general knowledge the model likely knows
    
    Query: {query}
    Classification:
    """
    
    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": classification_prompt.format(query=query)}],
        max_tokens=10
    )
    
    return "RETRIEVAL" in response.choices[0].message.content.upper()
```

---

## Lost in the Middle: Position Matters

Accuracy drops 10-20+ percentage points when relevant information sits in the middle of long contexts rather than at the beginning or end. Models exhibit primacy bias (strong performance with information at the start) and recency bias (strong performance at the end), but tend to struggle with middle sections.

**Implication for top-k**: Even if you retrieve k=10, the order you present them matters.

Wang et al. recommend the "reverse" method, where documents are arranged in ascending order of relevance. Liu et al. (2024) found that this approach — putting relevant information at the start or end — boosts performance.

```python
def format_context_with_positioning(chunks: list, scores: list) -> str:
    """Position chunks to minimize lost-in-the-middle effect."""
    
    # Sort by score (highest first)
    sorted_chunks = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    
    # Interleave: most relevant at start AND end
    # Less relevant in middle
    n = len(sorted_chunks)
    reordered = []
    
    for i, (chunk, score) in enumerate(sorted_chunks):
        if i % 2 == 0:
            reordered.insert(0, chunk)  # Add to front
        else:
            reordered.append(chunk)  # Add to back
    
    return "\n\n---\n\n".join(reordered)
```

---

## Practical Guidelines

### Starting Point Configuration

|Corpus Size|Chunk Size|Initial K|With Reranking|
|---|---|---|---|
|< 100 docs|512|5|Not needed|
|100-1000 docs|512|5-7|20 → 5|
|1000+ docs|256-512|10|50 → 10|

### When to Increase K

- Complex queries requiring information synthesis
- Comparison questions (need chunks from multiple topics)
- Summarization tasks
- When you have a reranker to filter

### When to Decrease K

- Factual lookup questions (specific answer expected)
- Tight latency requirements
- Limited context window budget
- High-quality dense corpus (most chunks are relevant)

### Red Flags That K Is Wrong

|Symptom|Likely Cause|Fix|
|---|---|---|
|Answers miss obvious information|K too low|Increase k or use reranking|
|Answers include contradictory info|K too high, noisy results|Decrease k or add score threshold|
|LLM says "based on the documents" for wrong info|Irrelevant chunks retrieved|Better retrieval, not more k|
|Response latency too high|K too high for context size|Reduce k, use smaller model|

---

## Key Takeaways

1. **5-10 is the research-backed sweet spot** — More chunks rarely helps, often hurts
2. **Chunk size and k are coupled** — Smaller chunks need higher k
3. **Reranking decouples retrieval breadth from generation precision** — Retrieve 50, rerank to 5
4. **Position matters** — Put most relevant chunks at start or end, not middle
5. **Dynamic k beats static k** — Adjust based on query complexity
6. **Not every query needs retrieval** — Classify first, retrieve if needed