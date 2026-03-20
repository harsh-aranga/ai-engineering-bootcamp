# Bi-Encoders: Encode Query and Document Separately

## What is a Bi-Encoder?

A bi-encoder is a neural network architecture that encodes two pieces of text **independently** into fixed-size vector embeddings, then compares those vectors to determine similarity.

```
┌─────────────┐                      ┌─────────────┐
│    Query    │                      │  Document   │
└──────┬──────┘                      └──────┬──────┘
       │                                    │
       ▼                                    ▼
┌──────────────┐                    ┌──────────────┐
│   Encoder    │                    │   Encoder    │
│  (same model)│                    │  (same model)│
└──────┬───────┘                    └──────┬───────┘
       │                                    │
       ▼                                    ▼
   [384-dim]                           [384-dim]
   embedding                           embedding
       │                                    │
       └────────────┬───────────────────────┘
                    │
                    ▼
            cosine_similarity()
                    │
                    ▼
              0.0 to 1.0
```

The key insight: **both texts pass through the same encoder model, but at different times**. The document can be encoded offline (before any query arrives), and the query is encoded at search time.

---

## Why Bi-Encoders Enable Scale

The magic of bi-encoders is the **decoupling** of encoding and comparison:

|Phase|When It Happens|What Happens|Cost|
|---|---|---|---|
|**Index time** (offline)|Once, when you add documents|Encode all documents → store vectors|O(n) encodings, done once|
|**Query time** (online)|Every search request|Encode query → ANN search over stored vectors|O(1) encoding + O(log n) search|

This is why you can search millions of documents in milliseconds — the expensive encoding of documents already happened. At query time, you only encode one query and run approximate nearest neighbor (ANN) search.

### The Numbers

For a corpus of 1 million documents:

- **Bi-encoder:** 1 query encoding + ANN search ≈ 10-50ms
- **Naive pairwise comparison:** 1 million comparisons ≈ hours

---

## How Bi-Encoders Are Trained

Bi-encoders learn to place semantically similar texts close together in vector space through **contrastive learning**:

1. Take a (query, relevant_document) pair — these should be close
2. Take (query, irrelevant_document) pairs — these should be far apart
3. Train the encoder to minimize distance for positives, maximize for negatives

Common loss functions:

- **Cosine similarity loss:** Directly optimizes cosine similarity between pairs
- **Triplet loss:** (anchor, positive, negative) — push positive closer than negative
- **Multiple Negatives Ranking Loss:** Efficient batch-wise contrastive learning

The result: an encoder that maps semantically similar texts to nearby vectors.

---

## The Fundamental Limitation

Here's the critical constraint that sets up the need for reranking:

**The bi-encoder encodes the document without knowing what question will be asked.**

When you embed a document at index time:

- You don't know what queries users will send
- You must compress _all possible meanings_ of the document into one vector
- Nuance specific to any particular question gets lost

### Example

Document: _"Apple released the M3 chip in late 2023, delivering 20% faster CPU performance than M2."_

This document is relevant to:

- "When did Apple release M3?"
- "How much faster is M3 than M2?"
- "What chips did Apple release in 2023?"

But the bi-encoder produces **one embedding** that must work for all these queries. It can't emphasize "late 2023" for the timing question or "20% faster" for the performance question — it has to generalize across all possible questions.

---

## Bi-Encoder in Code

Using `sentence-transformers` (the standard library for this):

```python
from sentence_transformers import SentenceTransformer, util

# Load a bi-encoder model
model = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1')

# Your document corpus
documents = [
    "Python is a programming language known for readability.",
    "Machine learning models learn patterns from data.",
    "The Eiffel Tower is located in Paris, France.",
    "Neural networks are inspired by biological neurons.",
]

# Index time: encode all documents (do this once, store the vectors)
doc_embeddings = model.encode(documents, convert_to_tensor=True)

# Query time: encode the query
query = "What is Python?"
query_embedding = model.encode(query, convert_to_tensor=True)

# Compare: find most similar documents
similarities = util.cos_sim(query_embedding, doc_embeddings)
print(similarities)
# tensor([[0.6821, 0.2134, 0.0891, 0.2567]])
#          ↑ highest — Python doc is most similar
```

### Retrieving Top-K

```python
# Get top-k results with scores
top_k = 2
hits = util.semantic_search(query_embedding, doc_embeddings, top_k=top_k)[0]

for hit in hits:
    print(f"Score: {hit['score']:.4f} | {documents[hit['corpus_id']]}")
    
# Score: 0.6821 | Python is a programming language known for readability.
# Score: 0.2567 | Neural networks are inspired by biological neurons.
```

---

## Common Bi-Encoder Models

|Model|Dimensions|Speed|Use Case|
|---|---|---|---|
|`all-MiniLM-L6-v2`|384|Very fast|General purpose, good balance|
|`all-mpnet-base-v2`|768|Medium|Higher quality, general purpose|
|`multi-qa-MiniLM-L6-cos-v1`|384|Very fast|Optimized for Q&A retrieval|
|`multi-qa-mpnet-base-dot-v1`|768|Medium|Higher quality Q&A retrieval|
|OpenAI `text-embedding-3-small`|1536|API call|High quality, production-ready|
|OpenAI `text-embedding-3-large`|3072|API call|Highest quality from OpenAI|

---

## Bi-Encoder vs. Cross-Encoder: The Trade-off

|Aspect|Bi-Encoder|Cross-Encoder|
|---|---|---|
|**Encoding**|Query and doc encoded separately|Query and doc encoded together|
|**Pre-computation**|✅ Documents can be indexed offline|❌ Must process each pair at query time|
|**Speed**|Fast (milliseconds for millions)|Slow (seconds for hundreds)|
|**Accuracy**|Good but limited by compression|Higher (sees both texts together)|
|**Scalability**|Scales to billions|Only practical for small candidate sets|
|**Output**|Embedding vectors|Single relevance score|
|**Use in RAG**|Initial retrieval|Reranking|

---

## Why This Matters for Reranking

The bi-encoder's limitation — encoding documents without query context — is precisely why reranking exists.

**The two-stage pattern:**

1. **Bi-encoder retrieves candidates:** Fast, scalable, but some noise
2. **Cross-encoder reranks candidates:** Slow, but sees query+doc together — higher accuracy

The bi-encoder's job isn't to be perfect. It's to be **fast enough to search millions of documents** and **good enough to include the relevant ones in the top-100**.

The cross-encoder then does the precision work on that smaller set.

---

## Key Takeaways

1. **Bi-encoders encode texts independently** — documents are embedded offline, queries at search time
    
2. **Speed comes from decoupling** — encoding and comparison are separate steps, enabling pre-computation
    
3. **The limitation is information compression** — all meanings of a document squeezed into one vector, without knowing the query
    
4. **This limitation justifies reranking** — cross-encoders see query+doc together, recovering the nuance that bi-encoders lose
    
5. **Bi-encoders are the retrieval workhorse** — every vector search you do in RAG uses a bi-encoder under the hood