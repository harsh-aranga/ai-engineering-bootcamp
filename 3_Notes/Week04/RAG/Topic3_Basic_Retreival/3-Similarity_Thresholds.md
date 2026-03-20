# Similarity Thresholds: Minimum Score to Include

## The Problem with Pure Top-K

If you set top_k to 5, you'll get the five most similar source content, regardless of their relevance. While easy to implement, this can include poor matches just because they made the cutoff.

Top-k retrieval has a fundamental flaw: it always returns k results, even if none of them are actually relevant to the query. Ask a question completely outside your document corpus, and you'll still get 5 chunks — they'll just be garbage.

Similarity retrieval with threshold adds a quality check by setting a minimum allowed similarity score between vectors. Any results with a similarity score below the threshold gets filtered out, even if it would have made the top_k cutoff.

---

## Understanding Score Types: Distance vs. Similarity

This is where most bugs originate. **Different vector databases return different things.**

Chroma uses distance metrics to measure how dissimilar a result is from a query. A distance of 0 indicates that the two items are identical, while larger distances indicate greater dissimilarity.

Some systems use "distance" instead of "similarity": Similarity: 1.0 = perfect match, 0.0 = no relation (higher is better). Distance: 0.0 = perfect match, 1.0 = no relation (lower is better).

### The Conversion

For cosine metrics with normalized embeddings:

```python
# If your DB returns DISTANCE (ChromaDB default)
similarity = 1 - distance

# If your DB returns SIMILARITY (some configs)
# Use directly - higher is better
```

Scores represent distance; for similarity, use 1 - score (for normalized embeddings).

### Common Confusion in LangChain + ChromaDB

The score_threshold used in LangChain is NOT the similarity score (cosine similarity). Instead it is the cosine distance, where cosine_distance = 1 - cosine_similarity. Use 0.25 which is 1 - 0.75.

This is a notorious gotcha. If you want to filter for similarity ≥ 0.75:

- **LlamaIndex**: Set `similarity_cutoff=0.75` (uses similarity)
- **LangChain + ChromaDB**: Set `score_threshold=0.25` (uses distance)

---

## The Three Distance Metrics

### 1. Cosine Similarity/Distance

Cosine cares about direction (the angle between vectors), ignoring their length.

- **Range**: -1 to +1 (similarity), 0 to 2 (distance)
- **Interpretation**:
    - Similarity 1.0 = identical direction
    - Similarity 0.0 = orthogonal (unrelated)
    - Similarity -1.0 = opposite direction

For text, many embeddings are normalized to length=1, so dot product becomes basically the same as cosine similarity.

### 2. L2 (Euclidean) Distance

L2 cares about absolute distance, including magnitude differences.

- **Range**: 0 to ∞
- **Lower is better**
- **Problem**: L2 might complain about tiny coordinate differences that don't really matter if the overall direction is the same.

### 3. Dot Product (Inner Product)

- **Range**: -∞ to +∞
- **For normalized vectors**: Equivalent to cosine similarity
- **For unnormalized vectors**: Includes magnitude information

OpenAI embeddings are normalized to length 1, which means that cosine similarity can be computed slightly faster using just a dot product. Cosine similarity and Euclidean distance will result in the identical rankings.

---

## What Scores Actually Look Like in Practice

### OpenAI Embedding Models

While cosine similarity has a range from -1.0 to 1.0, users of the OpenAI embedding API will typically not see values less than 0.4.

This is crucial: the theoretical range and practical range are different.

|Cosine Similarity|Interpretation|
|---|---|
|0.90+|Near-exact semantic match|
|0.80-0.90|Strong relevance|
|0.70-0.80|Moderate relevance|
|0.60-0.70|Weak relevance|
|0.50-0.60|Tangentially related|
|< 0.50|Likely irrelevant|

0.9+: Perfect match, exactly what you're looking for.

### Model-Specific Score Ranges

Different embedding models produce different score distributions:

When using "text-embedding-ada-002" the relevance scores could provide relevance of .70 or above, and now with "text-embedding-3-small" we get relevance scores around 0.4.

**Critical**: A threshold of 0.7 that worked perfectly for `ada-002` will filter out everything with `text-embedding-3-small`. **Thresholds are model-specific and must be recalibrated when changing models.**

---

## Setting Thresholds: No Universal Answer

The choice of the similarity threshold is an important consideration, as it determines the balance between precision and recall. A higher threshold will result in fewer, but more relevant, recommendations, while a lower threshold will provide more recommendations, but with potentially lower relevance.

### The Trade-off

|Threshold|Effect|
|---|---|
|Too high (e.g., 0.9)|Miss relevant documents (low recall)|
|Too low (e.g., 0.3)|Include irrelevant noise (low precision)|
|"Right" value|Depends on your corpus, model, and use case|

### Empirical Calibration Process

There's no formula — you must measure:

```python
def calibrate_threshold(
    collection,
    test_queries: list[dict],  # [{"query": str, "relevant_doc_ids": set}, ...]
    embedding_model,
    thresholds: list[float] = [0.5, 0.6, 0.7, 0.8, 0.9]
) -> dict:
    """
    Find optimal threshold for your specific corpus + model.
    
    Returns precision/recall at each threshold.
    """
    results = {}
    
    for threshold in thresholds:
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        
        for test_case in test_queries:
            query = test_case["query"]
            relevant_ids = test_case["relevant_doc_ids"]
            
            # Retrieve with threshold
            query_embedding = embedding_model.encode(query)
            retrieved = collection.query(
                query_embedding,
                n_results=20,
                include=["distances", "metadatas"]
            )
            
            # Filter by threshold (convert distance to similarity)
            retrieved_ids = set()
            for doc_id, distance in zip(
                [m["doc_id"] for m in retrieved["metadatas"][0]],
                retrieved["distances"][0]
            ):
                similarity = 1 - distance  # For cosine distance
                if similarity >= threshold:
                    retrieved_ids.add(doc_id)
            
            # Calculate metrics
            true_positives += len(retrieved_ids & relevant_ids)
            false_positives += len(retrieved_ids - relevant_ids)
            false_negatives += len(relevant_ids - retrieved_ids)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        results[threshold] = {
            "precision": precision,
            "recall": recall,
            "f1": f1
        }
    
    return results
```

---

## Implementation Patterns

### Pattern 1: Threshold Only

Filter purely by score, no k limit:

```python
def retrieve_by_threshold(
    collection,
    query_embedding,
    min_similarity: float = 0.7,
    max_results: int = 50  # Safety cap
) -> list:
    """Retrieve all chunks above similarity threshold."""
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=max_results,
        include=["documents", "distances", "metadatas"]
    )
    
    filtered = []
    for doc, dist, meta in zip(
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0]
    ):
        similarity = 1 - dist  # Assuming cosine distance
        if similarity >= min_similarity:
            filtered.append({
                "content": doc,
                "similarity": similarity,
                "metadata": meta
            })
    
    return filtered
```

**Problem**: Might return 0 results or 50 results — unpredictable for LLM context budgeting.

### Pattern 2: Top-K with Threshold Floor

A common strategy would be to set a lower bound threshold for similarity scores, but ensure at least N retrievals are returned regardless.

```python
def retrieve_with_threshold_and_minimum(
    collection,
    query_embedding,
    k: int = 5,
    min_similarity: float = 0.6,
    guaranteed_minimum: int = 2
) -> list:
    """
    Retrieve top-k above threshold, but always return at least N results.
    
    This prevents:
    - Returning garbage when threshold filters everything (guaranteed min)
    - Returning irrelevant results that happen to be "top" (threshold filter)
    """
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "distances", "metadatas"]
    )
    
    all_results = []
    above_threshold = []
    
    for doc, dist, meta in zip(
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0]
    ):
        similarity = 1 - dist
        result = {"content": doc, "similarity": similarity, "metadata": meta}
        all_results.append(result)
        
        if similarity >= min_similarity:
            above_threshold.append(result)
    
    # Return threshold-filtered results, but at least guaranteed_minimum
    if len(above_threshold) >= guaranteed_minimum:
        return above_threshold
    else:
        # Fall back to top-N if threshold filters too aggressively
        return sorted(all_results, key=lambda x: x["similarity"], reverse=True)[:guaranteed_minimum]
```

### Pattern 3: Adaptive Threshold

Adjust threshold based on score distribution:

```python
def retrieve_with_adaptive_threshold(
    collection,
    query_embedding,
    k: int = 10,
    drop_ratio: float = 0.3  # Drop if score is 30% below top score
) -> list:
    """
    Use relative threshold based on best match score.
    
    If top result is 0.85, threshold becomes 0.85 * 0.7 = 0.595
    This adapts to query difficulty.
    """
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "distances"]
    )
    
    similarities = [1 - d for d in results["distances"][0]]
    
    if not similarities:
        return []
    
    top_score = max(similarities)
    adaptive_threshold = top_score * (1 - drop_ratio)
    
    filtered = []
    for doc, sim in zip(results["documents"][0], similarities):
        if sim >= adaptive_threshold:
            filtered.append({"content": doc, "similarity": sim})
    
    return filtered
```

**Why this works**: If the best match is only 0.5, absolute threshold of 0.7 would return nothing. Adaptive threshold says "keep results within 30% of the best."

---

## Framework-Specific Implementation

### LlamaIndex

```python
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.query_engine import RetrieverQueryEngine

# Create query engine with threshold
query_engine = RetrieverQueryEngine(
    retriever=retriever,
    response_synthesizer=response_synthesizer,
    node_postprocessors=[
        SimilarityPostprocessor(similarity_cutoff=0.7)  # Uses SIMILARITY (higher = better)
    ]
)
```

Developers can customize the retrieval process, adjusting parameters such as similarity_top_k and similarity_cutoff from LlamaIndex's postprocessor module to refine the results.

### LangChain + ChromaDB

```python
# CAREFUL: LangChain uses DISTANCE for threshold, not similarity!
retriever = vectorstore.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={
        "score_threshold": 0.25,  # This is DISTANCE! 0.25 distance = 0.75 similarity
        "k": 5
    }
)
```

Should include score_threshold: Optional, a floating point value between 0 to 1.

### Raw ChromaDB

```python
# ChromaDB returns distance, not similarity
collection = client.create_collection(
    name="my_collection",
    metadata={"hnsw:space": "cosine"}  # Explicitly set cosine
)

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10,
    include=["distances", "documents"]
)

# Convert and filter manually
for doc, dist in zip(results["documents"][0], results["distances"][0]):
    similarity = 1 - dist
    if similarity >= 0.7:
        # Use this result
        pass
```

---

## The "No Good Results" Problem

What happens when nothing passes the threshold?

### Option 1: Return Nothing, Admit Ignorance

```python
def retrieve_or_admit_ignorance(
    collection,
    query_embedding,
    min_similarity: float = 0.6
) -> tuple[list, bool]:
    """Returns (results, has_relevant_context)."""
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        include=["documents", "distances"]
    )
    
    filtered = []
    for doc, dist in zip(results["documents"][0], results["distances"][0]):
        if (1 - dist) >= min_similarity:
            filtered.append(doc)
    
    has_context = len(filtered) > 0
    return filtered, has_context

# In your RAG pipeline:
chunks, has_context = retrieve_or_admit_ignorance(collection, query_emb)

if has_context:
    prompt = f"Based on the following context:\n{chunks}\n\nAnswer: {query}"
else:
    prompt = f"""The knowledge base doesn't contain information relevant to this question.
    
Question: {query}

Please respond that you don't have information about this topic in the available documents."""
```

### Option 2: Graceful Degradation

```python
def retrieve_with_confidence_tiers(
    collection,
    query_embedding,
    high_confidence: float = 0.8,
    medium_confidence: float = 0.6
) -> dict:
    """Return results with confidence classification."""
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=20,
        include=["documents", "distances"]
    )
    
    high = []
    medium = []
    low = []
    
    for doc, dist in zip(results["documents"][0], results["distances"][0]):
        sim = 1 - dist
        if sim >= high_confidence:
            high.append({"content": doc, "similarity": sim})
        elif sim >= medium_confidence:
            medium.append({"content": doc, "similarity": sim})
        else:
            low.append({"content": doc, "similarity": sim})
    
    return {
        "high_confidence": high,
        "medium_confidence": medium,
        "low_confidence": low,
        "recommendation": "high" if high else ("medium" if medium else "none")
    }
```

Then in your prompt:

- High confidence: "Based on the documents..."
- Medium confidence: "The documents may contain relevant information, but I'm less certain..."
- None: "I don't have reliable information about this topic."

---

## Debugging Score Issues

### Symptom: All Scores Are High

The cosine similarity between embedding vectors consistently yields values above 0.68, even for dissimilar or unrelated texts.

**Possible causes:**

1. **Embedding model bias**: Some models produce "compressed" score ranges
2. **Short texts**: Very short queries/chunks have less discriminative power
3. **Domain similarity**: All your documents are in the same domain

**Diagnosis:**

```python
def diagnose_score_distribution(collection, test_queries: list[str], embedding_model):
    """Understand your score distribution."""
    
    all_scores = []
    
    for query in test_queries:
        query_emb = embedding_model.encode(query)
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=50,
            include=["distances"]
        )
        
        similarities = [1 - d for d in results["distances"][0]]
        all_scores.extend(similarities)
    
    import numpy as np
    print(f"Min: {np.min(all_scores):.3f}")
    print(f"Max: {np.max(all_scores):.3f}")
    print(f"Mean: {np.mean(all_scores):.3f}")
    print(f"Median: {np.median(all_scores):.3f}")
    print(f"Std: {np.std(all_scores):.3f}")
    print(f"25th percentile: {np.percentile(all_scores, 25):.3f}")
    print(f"75th percentile: {np.percentile(all_scores, 75):.3f}")
    
    # Set threshold at ~75th percentile to get top 25% of results
    suggested_threshold = np.percentile(all_scores, 75)
    print(f"\nSuggested threshold (top 25%): {suggested_threshold:.3f}")
```

### Symptom: ChromaDB Returns Inverted Scores

Higher score for the documents that are earlier in the returned list (which the document is more related but has a lower score). Seems more like I should be doing (1-score) to filter more relevant documents.

Lower score represents more similarity.

**Fix**: Always convert ChromaDB distances to similarities:

```python
# ChromaDB with cosine space
similarity = 1 - distance

# Then filter
if similarity >= threshold:  # NOT if distance <= threshold
    include_result()
```

### Symptom: L2 vs Cosine Confusion

ChromaDB uses L2 distance by default, not cosine.

**Fix**: Explicitly set distance metric when creating collection:

```python
collection = client.create_collection(
    name="my_collection",
    metadata={"hnsw:space": "cosine"}  # Options: "l2", "cosine", "ip"
)
```

ChromaDB is great, but its default L2 distance for text embeddings can be "wrong" in the sense that it measures the length difference instead of the angle.

---

## Key Takeaways

1. **Distance ≠ Similarity** — Know what your vector DB returns and convert appropriately
    
2. **Thresholds are model-specific** — Recalibrate when changing embedding models
    
3. **No universal threshold exists** — Must empirically determine for your corpus
    
4. **Combine threshold + top-k + minimum** — Prevents both garbage results and empty results
    
5. **Test with out-of-domain queries** — Your threshold should correctly return nothing for irrelevant questions
    
6. **Score distributions vary** — Diagnose your actual score range before setting thresholds
    
7. **ChromaDB defaults to L2** — Explicitly set `cosine` for text embeddings
    

---

## Quick Reference: Score Interpretation

|Metric|Perfect Match|No Relation|Better When|
|---|---|---|---|
|Cosine Similarity|1.0|0.0|Higher|
|Cosine Distance|0.0|1.0 (or 2.0)|Lower|
|L2 Distance|0.0|Large|Lower|
|Dot Product (normalized)|1.0|0.0|Higher|