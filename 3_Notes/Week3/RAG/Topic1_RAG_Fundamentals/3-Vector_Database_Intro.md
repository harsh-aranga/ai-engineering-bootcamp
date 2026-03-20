## Vector Databases: Conceptual Notes

---

### What Problem Do They Solve?

You have millions of document chunks, each represented as a 768-dimension embedding vector. User query comes in, you embed it, now you need to find the most similar vectors.

**The naive approach:** Compare query vector against all million vectors, compute similarity for each, sort, return top-k.

**The problem:** This is O(n) per query. At scale (millions/billions of vectors), this takes seconds or minutes. Unacceptable for real-time applications.

**Vector databases exist to make similarity search fast** — sub-second retrieval over millions of vectors.

---

### What Is Similarity Search?

Given a query vector, find the k vectors in your collection that are "closest" to it.

**"Closest" means:** Smallest distance (or highest similarity) according to some metric.

**Common metrics:**

|Metric|What It Measures|Range|Used When|
|---|---|---|---|
|Cosine similarity|Angle between vectors|-1 to 1|Most common for text embeddings|
|Euclidean distance (L2)|Straight-line distance|0 to ∞|When magnitude matters|
|Dot product|Combination of angle + magnitude|-∞ to ∞|When vectors are normalized, equivalent to cosine|

For text embeddings, cosine similarity is standard. Most embedding models normalize vectors, so cosine and dot product become equivalent.

---

### Why Not Just Use a Regular Database?

Traditional databases are optimized for exact match and range queries:

```sql
SELECT * FROM users WHERE age > 25 AND city = 'Chennai'
```

This works because you can build B-tree indexes on `age` and `city`. The index structure maps directly to the query type.

**Vectors don't work this way.** There's no natural ordering. You can't say "all vectors where dimension 47 is between 0.3 and 0.5" — that's meaningless semantically.

You need indexes designed for high-dimensional similarity, not equality or range.

---

### How Vector Databases Make It Fast

They use **Approximate Nearest Neighbor (ANN)** algorithms. The key tradeoff:

**Exact search:** 100% accurate, slow (check everything) **Approximate search:** 95-99% accurate, fast (check a subset intelligently)

For RAG, approximate is fine. If the true top-5 results are [A, B, C, D, E] and you get [A, B, C, E, F], that's usually good enough.

**The main ANN approaches:**

**1. HNSW (Hierarchical Navigable Small World)**

Think of it like a skip list for vectors. Build a graph where similar vectors are connected. To search, start at a random entry point, greedily move toward the query vector by following edges to more similar neighbors.

```
Layer 2:    A -------- D -------- G        (sparse, long jumps)
Layer 1:    A --- C --- D --- F --- G      (medium density)  
Layer 0:    A-B-C-D-E-F-G-H-I-J-K          (all vectors, short edges)
```

Search starts at top layer (fast, coarse), descends to lower layers (slower, precise).

**Tradeoff:** High memory (stores graph structure), very fast queries.

**2. IVF (Inverted File Index)**

Cluster vectors into buckets (using k-means or similar). At query time, find the closest cluster centers, then only search within those clusters.

```
Cluster 1: [vec_a, vec_b, vec_c, ...]
Cluster 2: [vec_d, vec_e, vec_f, ...]
...
Cluster 100: [vec_x, vec_y, vec_z, ...]

Query → Find closest 5 clusters → Search only those ~5% of vectors
```

**Tradeoff:** Lower memory than HNSW, but need to tune number of clusters and probes.

**3. Product Quantization (PQ)**

Compress vectors to reduce memory. Split 768-dim vector into 96 sub-vectors of 8 dims each. Quantize each sub-vector to a small codebook. Store compressed representation.

**Tradeoff:** Much lower memory, some accuracy loss, often combined with IVF.

---

### What Vector Databases Actually Store

Not just vectors. A typical record:

```json
{
  "id": "chunk_4521",
  "vector": [0.23, -0.87, 0.45, ...],  // 768 floats
  "metadata": {
    "source": "product_manual_v2.pdf",
    "page": 47,
    "section": "troubleshooting",
    "product_version": "2.7",
    "last_updated": "2024-01-15"
  },
  "text": "To reset the device, hold the power button..."  // optional, for display
}
```

**Metadata enables filtering:**

"Find similar vectors, but only from `source = 'product_manual_v2.pdf'`"

This is **filtered search** — apply metadata filters first (or during), then similarity search on the subset. Critical for production RAG.

---

### Vector Database vs Vector Index vs Vector Library

These terms get confused:

|Term|What It Is|Example|
|---|---|---|
|Vector library|ANN algorithm implementation, in-memory|FAISS, Annoy, hnswlib|
|Vector database|Full system with persistence, CRUD, filtering, scaling|Pinecone, Weaviate, Qdrant, Milvus|
|Vector index|The data structure enabling fast search|HNSW index, IVF index|

**ChromaDB** (which you'll use in Week 4) is a lightweight vector database — it wraps an index, adds persistence, metadata filtering, and a simple API.

**FAISS** is a library — you manage persistence, metadata, and scaling yourself.

For learning RAG, start with a database (ChromaDB). For production at scale, you'll evaluate managed options (Pinecone) or self-hosted (Qdrant, Milvus).

---

### Key Parameters You'll Encounter

When you configure a vector database, you'll see these:

|Parameter|What It Controls|
|---|---|
|`dimension`|Vector size (must match your embedding model)|
|`metric`|Distance function (cosine, L2, dot product)|
|`ef_construction` / `m` (HNSW)|Build-time quality vs speed tradeoff|
|`ef_search` (HNSW)|Query-time accuracy vs speed tradeoff|
|`nlist` (IVF)|Number of clusters|
|`nprobe` (IVF)|Clusters to search at query time|

Higher values = more accurate, slower. You tune these based on your latency/accuracy requirements.

---

### The Mental Model

Think of a vector database as:

```
Traditional DB:  "Give me rows WHERE condition = true"  → Exact match
Vector DB:       "Give me rows CLOSEST TO this point"   → Similarity match
```

Both need indexes to be fast. Different query types require different index structures.

---

# PQ - Analogy

**The Problem:**

Storing millions of 768-dimension vectors = massive memory. PQ compresses vectors to reduce storage.

**The Nose Analogy:**

**Without PQ:** Store exact measurements for every person's nose.

```
Person 1 nose: length=5.237cm, width=3.891cm, angle=52.4°, ...
Person 2 nose: length=4.102cm, width=2.956cm, angle=61.2°, ...
```

Precise, but tons of data.

**With PQ:** Create a catalog of ~256 "typical nose types" from your data.

```
Nose catalog:
  Type A: short, narrow, upturned
  Type B: long, wide, straight
  Type C: medium, narrow, hooked
  ... 253 more types
```

Now store:

```
Person 1: nose=B
Person 2: nose=A
```

---

**What You Gain:** ~32x storage reduction.

**What You Lose:** Exact data. You can't reconstruct Person 1's nose as exactly 5.237cm — you only know it was "Type B."

---

**Key Points:**

- Codebook = the catalog (shared across all vectors)
- Compressed vector = just the category labels
- Lossy compression — like JPEG, you can't recover original
- Categories are learned from data (clustering), not human-defined

---

**When This Matters:**

Billion-scale vector databases where memory is the bottleneck. Not something you configure for typical RAG projects.