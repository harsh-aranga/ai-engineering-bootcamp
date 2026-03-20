# Query Embedding: Same Model as Document Embedding

## The Non-Negotiable Rule

Using a different embedding model for retrieval than the one used for indexing documents is the equivalent of using a map of Paris to navigate the streets of Tokyo — the coordinates are meaningless because the contexts are incompatible.

This is the single most common silent killer in RAG systems. Don't use different embedding models for indexing and querying — this rule is absolute.

---

## Why This Breaks Everything

### The Vector Space Problem

When a user sends a query, the same embedding model encodes the query into a vector. The system then performs a vector similarity search, comparing the query's embedding to the stored document embeddings using techniques such as cosine similarity to retrieve the most semantically relevant documents.

Here's the core issue: **each embedding model creates its own unique vector space**. Model A might represent "machine learning" as `[0.8, 0.2, -0.5, ...]` while Model B represents the exact same phrase as `[-0.1, 0.9, 0.3, ...]`. These vectors aren't just different — they exist in fundamentally incompatible coordinate systems.

Embedding models from various providers (OpenAI, Cohere, Hugging Face, etc.) create different maps of the same information.

### What Goes Wrong

When you embed documents with Model A and queries with Model B:

1. **Similarity scores become meaningless** — high cosine similarity doesn't indicate semantic relevance
2. **Retrieval returns garbage** — you get "completely irrelevant, nonsensical results"
3. **No error is thrown** — the system happily returns results, just wrong ones
4. **Debugging is brutal** — everything looks correct in isolation

---

## The Two-Phase Architecture

Embedding models are used in RAG flows in both indexing (creating the map) and querying (using the compass).

### Phase 1: Indexing (Offline)

```
Documents → Chunk → Embed with Model X → Store vectors in DB
```

### Phase 2: Querying (Runtime)

```
User Query → Embed with Model X (SAME!) → Search DB → Retrieve chunks
```

In a RAG solution, you embed the user query by using the same embedding model as your chunks. Then, you search your database for relevant vectors to return the most semantically relevant chunks.

---

## Symmetric vs. Asymmetric Embedding Models

This is where it gets nuanced. Some models require different **prefixes** for queries vs. documents, but still use the **same underlying model**.

### Asymmetric Models (E5, Cohere embed-v3)

The researchers decided to differentiate these as "query" texts and "passage" texts, prefixing the corresponding data when training the model to better perform on certain retrieval tasks.

Rather than specifying whether an input is a query or document via a parameter, we prefix that information to the input text. For query, we prefix "query:", and for documents, we prefix "passage:".

**Example with E5:**

```python
# Document embedding (at indexing time)
doc_text = "passage: The mitochondria is the powerhouse of the cell."

# Query embedding (at query time)  
query_text = "query: What produces energy in cells?"

# SAME model for both, different prefixes
embedding_model.encode([doc_text])  # Indexing
embedding_model.encode([query_text])  # Querying
```

Each input text should start with "query: " or "passage: ", even for non-English texts.

### Why Asymmetric Design?

We define this to support improved performance for asymmetric semantic search — where we are querying with a smaller chunk of text (a search query) and attempting to retrieve larger chunks (a couple of sentences or paragraphs).

The model learns that queries and passages have different characteristics:

- Queries are short, often questions
- Passages are longer, contain answers
- The prefix tells the model what role this text plays

Such an asymmetric design turns out to be important for retrieval quality.

### Symmetric Models (OpenAI text-embedding-3-*)

OpenAI's models don't require prefixes. You embed queries and documents identically:

```python
# Same process for both
openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=text  # No prefix needed
)
```

---

## When Prefixes Go Wrong

A subtle bug: using the wrong prefix (or forgetting it) with asymmetric models.

```python
# WRONG: Missing prefix
doc_embedding = model.encode("The capital of France is Paris")

# WRONG: Wrong prefix on query  
query_embedding = model.encode("passage: What is the capital of France?")

# CORRECT
doc_embedding = model.encode("passage: The capital of France is Paris")
query_embedding = model.encode("query: What is the capital of France?")
```

Yes, this is how the model is trained, otherwise you will see a performance degradation.

---

## Model Migration: The Re-embedding Problem

In general, you will need to use the same embedding model to embed your data and the vector you're using to query. If you have existing embeddings with a different model provider, you will have to re-embed those using the new model.

### Scenario: You want to upgrade from `text-embedding-ada-002` to `text-embedding-3-large`

**You cannot:**

- Keep old embeddings and query with new model
- Mix embeddings from different models in the same collection
- Gradually migrate while keeping the system running (without careful orchestration)

**You must:**

1. Re-embed ALL documents with the new model
2. Store in a new collection/index
3. Switch queries to new model + new collection atomically
4. Delete old collection

### Cost Implications

Re-embedding isn't free:

- 1M documents × 500 tokens/doc = 500M tokens
- At $0.02/1M tokens (text-embedding-3-small) = $10
- At $0.13/1M tokens (text-embedding-3-large) = $65

For large corpora, model migration is a significant operational decision.

---

## The Reranking Exception

After the initial retrieval, employ a re-ranking step with a specialized cross-encoder model to squeeze out the highest possible accuracy from your results.

Rerankers (cross-encoders) are **allowed** to be different from your embedding model because they work differently:

- **Bi-encoder (embedding model)**: Encodes query and document separately, compares vectors
- **Cross-encoder (reranker)**: Takes query + document together, outputs relevance score directly

```
Stage 1: Embed query → Vector search (Model A) → Top 100 candidates
Stage 2: Rerank with cross-encoder (Model B) → Top 10 final results
```

The reranker doesn't use embeddings from your vector store — it processes raw text pairs. So model mismatch doesn't apply here.

---

## Practical Verification Pattern

Always verify model consistency in your code:

```python
class RAGPipeline:
    def __init__(self, embedding_model: str):
        self.embedding_model = embedding_model
        self._verify_collection_model()
    
    def _verify_collection_model(self):
        """Ensure collection was indexed with same model."""
        collection_metadata = self.vector_store.get_metadata()
        indexed_model = collection_metadata.get("embedding_model")
        
        if indexed_model != self.embedding_model:
            raise ValueError(
                f"Model mismatch! Collection indexed with '{indexed_model}', "
                f"but querying with '{self.embedding_model}'"
            )
    
    def index_documents(self, documents: list[str]):
        """Store model info in collection metadata."""
        embeddings = self._embed(documents)
        self.vector_store.add(
            embeddings=embeddings,
            metadata={"embedding_model": self.embedding_model}
        )
```

---

## Key Takeaways

1. **Same model, always** — This is non-negotiable for the embedding model used in vector search
2. **Prefixes matter for asymmetric models** — "query:" and "passage:" aren't optional decoration
3. **Model upgrades require full re-embedding** — Budget for this operationally and financially
4. **Rerankers are the exception** — Cross-encoders can be different because they don't use stored embeddings
5. **Verify programmatically** — Store model info in collection metadata, check at query time

---

## Things That Will Silently Break

|Mistake|Symptom|Why It's Silent|
|---|---|---|
|Different models for index vs. query|Irrelevant results|No error, just bad similarity scores|
|Missing prefix on asymmetric model|Degraded quality|Results exist, just worse|
|Wrong prefix (passage on query)|Poor retrieval|Vectors computed, just wrong space|
|Mixing model versions (v2 vs v3)|Inconsistent results|May work partially, fails on edge cases|