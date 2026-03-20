# Cross-Encoders: Encode Query + Document Together

## What is a Cross-Encoder?

A cross-encoder is a transformer model that takes a query and a document **together as a single input**, processes them jointly through all layers, and outputs a **relevance score** (typically 0 to 1).

```
┌─────────────────────────────────────┐
│  [CLS] query [SEP] document [SEP]  │
└──────────────────┬──────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │   Transformer   │
         │  (BERT-based)   │
         │                 │
         │  Full attention │
         │  across both    │
         │  query & doc    │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  Classification │
         │     Head        │
         └────────┬────────┘
                  │
                  ▼
            Relevance Score
              (0.0 - 1.0)
```

The key difference from bi-encoders: **no embeddings are produced**. You get a score, not a vector. This means you can't pre-compute anything — every (query, document) pair requires a full forward pass through the model.

---

## Why Cross-Encoders Are More Accurate

### The Attention Advantage

In a bi-encoder, the query and document never "see" each other. Each is embedded independently.

In a cross-encoder, every token in the query can **attend to every token in the document** (and vice versa). The transformer's self-attention mechanism operates over the concatenated sequence.

This means the model can learn patterns like:

- "When the query asks about _price_, pay attention to numbers in the document"
- "When the query is a _how-to_ question, focus on procedural language"
- "This document mentions the query terms but in a different context — not relevant"

These nuanced, **query-specific** relevance signals are impossible to capture when query and document are encoded separately.

### Information Flow Comparison

|Bi-Encoder|Cross-Encoder|
|---|---|
|Query tokens attend only to query tokens|Query tokens attend to query + document tokens|
|Document tokens attend only to document tokens|Document tokens attend to document + query tokens|
|Comparison happens _after_ encoding (cosine similarity)|Comparison happens _during_ encoding (attention)|
|Information loss from compression|Full information preserved|

### What the Model Actually Sees

**Bi-encoder input (separate):**

```
Input 1: "What is the capital of France?"
Input 2: "Paris is the capital and most populous city of France."
```

These become two independent vectors, then compared.

**Cross-encoder input (joint):**

```
[CLS] What is the capital of France? [SEP] Paris is the capital and most populous city of France. [SEP]
```

This single sequence flows through the transformer, allowing "capital" in the query to directly attend to "capital" and "Paris" in the document.

---

## Why Cross-Encoders Don't Scale

The accuracy advantage comes with a massive scalability cost.

### The Math

For a corpus of **N documents** and **Q queries**:

|Approach|Computations Required|
|---|---|
|Bi-encoder|N document encodings (once) + Q query encodings|
|Cross-encoder|N × Q full forward passes|

**Example:**

- 1 million documents, 1,000 queries
- Bi-encoder: 1,000,000 + 1,000 = ~1M encodings total
- Cross-encoder: 1,000,000 × 1,000 = **1 billion** forward passes

This is why cross-encoders are **only used for reranking** — you first reduce the candidate set to 50-200 documents using a bi-encoder, then rerank that small set.

### Latency Comparison

|Model|Time per (query, doc) pair|Time to score 100 docs|
|---|---|---|
|Bi-encoder similarity|~0.1ms|~10ms|
|Cross-encoder (MiniLM)|~10-30ms|~1-3 seconds|
|Cross-encoder (large)|~50-100ms|~5-10 seconds|

---

## Cross-Encoder Architecture

Most cross-encoders are based on BERT or similar encoder-only transformers, fine-tuned for relevance scoring.

### The Standard Setup

```
Input:  [CLS] query_tokens [SEP] document_tokens [SEP]
          ↓
      BERT/RoBERTa/DistilBERT (12-24 layers)
          ↓
      [CLS] token embedding (captures full sequence meaning)
          ↓
      Linear classification head
          ↓
      Sigmoid activation → score ∈ [0, 1]
```

The `[CLS]` token is special — after passing through all transformer layers, it aggregates information from the entire concatenated sequence. This makes it ideal for sequence-level classification tasks like relevance scoring.

### Training

Cross-encoders are trained on labeled (query, document, relevance) triples:

- **MS MARCO:** ~500K queries with relevant passages from Bing
- **Natural Questions:** Question-answer pairs from Google Search
- **Domain-specific datasets:** Medical, legal, scientific corpora

The training objective is typically binary cross-entropy:

- Relevant pairs should score close to 1
- Irrelevant pairs should score close to 0

---

## Cross-Encoder in Code

Using `sentence-transformers`:

```python
from sentence_transformers import CrossEncoder

# Load a pre-trained cross-encoder
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# Score a single (query, document) pair
query = "What is the capital of France?"
document = "Paris is the capital and most populous city of France."

score = model.predict([(query, document)])
print(f"Relevance score: {score[0]:.4f}")
# Relevance score: 0.9847

# Score multiple pairs at once (batched)
pairs = [
    ("What is the capital of France?", "Paris is the capital of France."),
    ("What is the capital of France?", "Berlin is the capital of Germany."),
    ("What is the capital of France?", "French cuisine is world-renowned."),
]

scores = model.predict(pairs)
for pair, score in zip(pairs, scores):
    print(f"Score: {score:.4f} | Doc: {pair[1][:50]}...")
    
# Score: 0.9847 | Doc: Paris is the capital of France....
# Score: 0.0023 | Doc: Berlin is the capital of Germany....
# Score: 0.0156 | Doc: French cuisine is world-renowned....
```

### Reranking Retrieved Results

```python
from sentence_transformers import CrossEncoder, SentenceTransformer, util

# Step 1: Initial retrieval with bi-encoder
bi_encoder = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1')

documents = [
    "Python is a high-level programming language.",
    "Machine learning uses algorithms to learn from data.",
    "The Python snake is found in tropical regions.",
    "TensorFlow is a machine learning framework written in Python.",
    "Data science combines statistics and programming.",
]

query = "Python machine learning libraries"
query_embedding = bi_encoder.encode(query, convert_to_tensor=True)
doc_embeddings = bi_encoder.encode(documents, convert_to_tensor=True)

# Get top-k from bi-encoder
hits = util.semantic_search(query_embedding, doc_embeddings, top_k=5)[0]
print("Bi-encoder ranking:")
for hit in hits:
    print(f"  Score: {hit['score']:.4f} | {documents[hit['corpus_id']]}")

# Step 2: Rerank with cross-encoder
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# Prepare pairs for cross-encoder
pairs = [(query, documents[hit['corpus_id']]) for hit in hits]
cross_scores = cross_encoder.predict(pairs)

# Reorder by cross-encoder scores
reranked = sorted(
    zip(hits, cross_scores), 
    key=lambda x: x[1], 
    reverse=True
)

print("\nCross-encoder reranking:")
for hit, score in reranked:
    print(f"  Score: {score:.4f} | {documents[hit['corpus_id']]}")
```

---

## What Cross-Encoders Learn

Research has shown that cross-encoders learn surprisingly interpretable relevance signals:

### Semantic BM25

A 2025 study found that BERT-based cross-encoders internally compute something resembling a **semantic version of BM25**:

1. **Term frequency:** Attention heads track how often query terms appear in the document
2. **Term saturation:** The model accounts for diminishing returns from repeated terms
3. **Document length normalization:** Longer documents don't get unfair advantages
4. **IDF-like weighting:** Rare terms contribute more to relevance scores

The key difference from literal BM25: the cross-encoder captures **semantic matches**, not just lexical ones. "Car" in the query can match "automobile" in the document.

### What This Means in Practice

Cross-encoders aren't magic — they're learning the same relevance principles that information retrieval has used for decades. But they apply these principles at a semantic level, catching matches that keyword-based systems miss.

---

## Common Cross-Encoder Models

|Model|Parameters|Speed|Quality|Notes|
|---|---|---|---|---|
|`ms-marco-MiniLM-L-6-v2`|22M|Fast|Good|Best speed/quality trade-off|
|`ms-marco-TinyBERT-L-2-v2`|4M|Very fast|Decent|When latency is critical|
|`ms-marco-MiniLM-L-12-v2`|33M|Medium|Better|More accurate than L-6|
|`ms-marco-distilbert-base-v4`|66M|Slower|High|DistilBERT-based|
|BGE Reranker models|Various|Varies|SOTA|See separate notes|
|Cohere Rerank API|N/A|API|Very high|Managed service|

The `ms-marco-*` models are trained on the MS MARCO passage ranking dataset and work well as general-purpose rerankers.

---

## Cross-Encoder Limitations

### 1. No Embeddings = No Pre-computation

You can't build an index. Every query requires scoring all candidate documents from scratch. This is why they're only viable for reranking small candidate sets.

### 2. Sequence Length Limits

Most cross-encoders inherit BERT's 512-token limit. If query + document exceeds this, you must truncate (losing information) or use a model with longer context support.

### 3. Domain Mismatch

A model trained on MS MARCO (web search queries) may not perform well on medical, legal, or highly technical documents. Domain-specific fine-tuning or alternative models may be needed.

### 4. Latency Adds Up

Even "fast" cross-encoders add 1-3 seconds when scoring 100 candidates. For real-time applications, this may be too slow.

---

## Key Takeaways

1. **Cross-encoders process query and document together** — full attention across both, enabling nuanced relevance judgments
    
2. **Output is a score, not an embedding** — no pre-computation possible, every pair needs a forward pass
    
3. **Higher accuracy, lower scalability** — cross-attention captures signals that bi-encoders miss, but at O(N×Q) cost
    
4. **Only viable for reranking** — use after bi-encoder retrieval to refine top-50 to top-100 candidates
    
5. **Internally learn semantic BM25** — same relevance principles as classical IR, but at the semantic level
    
6. **Trade-off is latency for quality** — ~10-100ms per pair vs. ~0.1ms for bi-encoder similarity
    

---

## Connection to Two-Stage Retrieval

The bi-encoder and cross-encoder complement each other:

```
        ┌──────────────────────────────────────────────────┐
        │                 TWO-STAGE RETRIEVAL              │
        ├──────────────────────────────────────────────────┤
        │                                                  │
        │  Stage 1: Bi-Encoder (Recall)                   │
        │  ├── Query → embedding                          │
        │  ├── ANN search over pre-computed doc embeddings│
        │  └── Return top-100 candidates                  │
        │           ↓                                     │
        │  Stage 2: Cross-Encoder (Precision)             │
        │  ├── Score each (query, candidate) pair         │
        │  ├── Reorder by relevance score                 │
        │  └── Return top-5 to top-10                     │
        │                                                  │
        └──────────────────────────────────────────────────┘
```

The bi-encoder maximizes **recall** — making sure relevant documents are in the candidate set. The cross-encoder maximizes **precision** — making sure only the most relevant reach the LLM.