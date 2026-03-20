# Embedding at Index Time: When and How

## The Core Question

When you add chunks to a vector store, embeddings must be generated. You have two choices:

1. **Let the vector store embed** — pass text, it calls the embedding model internally
2. **Pre-compute embeddings** — embed externally, pass vectors directly

This isn't just an API preference — it affects performance, cost, error handling, and pipeline architecture.

---

## Two Approaches

### Approach 1: Vector Store Handles Embedding

Embedding functions can be linked to a collection and used whenever you call add, update, upsert or query.

```python
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# Configure embedding function on collection
collection = client.create_collection(
    name="my_docs",
    embedding_function=OpenAIEmbeddingFunction(
        model_name="text-embedding-3-small"
    )
)

# Just pass documents — ChromaDB embeds automatically
collection.add(
    ids=["doc1", "doc2"],
    documents=["First document text", "Second document text"]
)
```

**Pros**:

- Simple API — fewer lines of code
- Consistent embedding at add and query time (same function used for both)
- No need to manage embedding vectors yourself

**Cons**:

- Less control over batching
- Harder to debug embedding failures
- Can't pre-compute or cache embeddings
- Tight coupling between indexing and embedding

### Approach 2: Pre-Compute Embeddings Externally

ChromaDB lets you supply pre-computed embeddings directly using the embeddings parameter in collection.add().

```python
from openai import OpenAI

client = OpenAI()

# Step 1: Embed externally
def embed_batch(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    return [item.embedding for item in response.data]

# Step 2: Pass embeddings directly to ChromaDB
chunks = ["First chunk", "Second chunk", "Third chunk"]
embeddings = embed_batch(chunks)

collection.add(
    ids=["c1", "c2", "c3"],
    embeddings=embeddings,
    documents=chunks  # Optional: store text for retrieval
)
```

**Pros**:

- Full control over batching, retries, rate limiting
- Can pre-compute and cache embeddings
- Easier to debug (separate embedding from storage)
- Can parallelize embedding across workers
- Works with any embedding provider

**Cons**:

- More code
- Must ensure same embedding model at query time
- Manual management of embedding dimensions

---

## Why Pre-Compute? The Performance Case

This is the most common reason for slow addition. Some embedding functions are slower than others.

When ChromaDB embeds internally, each `add()` call blocks until embedding completes. For large batches:

```
add(100 docs) → embed 100 docs (slow) → insert to HNSW (fast) → return
```

If embedding takes 30 seconds and insertion takes 1 second, you're waiting 31 seconds with no visibility into progress.

With pre-computed embeddings:

```
embed_batch(100 docs) → 30 seconds (can show progress, retry failures)
add(100 docs with embeddings) → 1 second
```

You get:

- Progress visibility
- Granular error handling
- Ability to checkpoint and resume
- Separation of concerns

---

## Batching: The Key to Efficiency

### Why Batch?

Embedding APIs accept multiple texts in one call. Single-text calls are wasteful:

```python
# BAD: One API call per chunk (slow, expensive overhead)
for chunk in chunks:
    embedding = embed(chunk)  # Network round-trip each time
    collection.add(ids=[chunk.id], embeddings=[embedding], ...)

# GOOD: Batch API calls
batch_size = 100
for i in range(0, len(chunks), batch_size):
    batch = chunks[i:i+batch_size]
    embeddings = embed_batch([c.text for c in batch])  # One API call
    collection.add(
        ids=[c.id for c in batch],
        embeddings=embeddings,
        ...
    )
```

### Optimal Batch Size

There's no universal answer — it depends on:

1. **API limits**: A single batch may include up to 50,000 requests, and a batch input file can be up to 200 MB in size. Note that /v1/embeddings batches are also restricted to a maximum of 50,000 embedding inputs across all requests in the batch.
    
2. **Token limits**: Each embedding model has a max input token limit per text. `text-embedding-3-small` allows 8191 tokens per input.
    
3. **Rate limits**: Tokens per minute (TPM) and requests per minute (RPM) caps.
    
4. **Memory**: Larger batches use more RAM.
    

**Practical guidance**:

- Start with 100 chunks per batch
- Monitor for rate limit errors, adjust down if needed
- For very large corpora, consider OpenAI's Batch API (discussed below)

---

## Implementation: Robust Embedding Pipeline

Here's a production-ready embedding function with batching and retries:

```python
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai

client = OpenAI()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError))
)
def embed_batch(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """Embed a batch of texts with retry logic."""
    response = client.embeddings.create(
        model=model,
        input=texts
    )
    # Response order matches input order
    return [item.embedding for item in response.data]


def embed_chunks(
    chunks: list[dict],
    batch_size: int = 100,
    model: str = "text-embedding-3-small"
) -> list[list[float]]:
    """Embed chunks in batches with progress tracking."""
    all_embeddings = []
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        texts = [c["content"] for c in batch]
        
        try:
            embeddings = embed_batch(texts, model=model)
            all_embeddings.extend(embeddings)
            print(f"Embedded {i + len(batch)}/{len(chunks)} chunks")
        except Exception as e:
            print(f"Failed batch starting at {i}: {e}")
            raise
    
    return all_embeddings
```

---

## Handling Partial Failures

What happens when chunk #47 in a 100-chunk batch fails (e.g., content filter triggered)?

### Option A: Fail the Whole Batch

```python
try:
    embeddings = embed_batch(chunks)
except Exception:
    # All 100 chunks failed — retry or abort
    raise
```

**Pros**: Simple, consistent state **Cons**: Wasteful — 99 good chunks lost

### Option B: Retry with Smaller Batches

```python
def embed_with_fallback(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    try:
        return embed_batch(texts)
    except openai.BadRequestError:
        # Likely content filter on one item — try smaller batches
        if len(texts) == 1:
            # Single item failed — return empty or placeholder
            return [[0.0] * 1536]  # Or raise
        
        mid = len(texts) // 2
        left = embed_with_fallback(texts[:mid], batch_size)
        right = embed_with_fallback(texts[mid:], batch_size)
        return left + right
```

**Pros**: Recovers most embeddings **Cons**: More complex, slower on failure

### Option C: Skip and Log Failed Items

```python
def embed_with_skip(texts: list[str]) -> tuple[list[list[float]], list[int]]:
    """Returns embeddings and indices of failed items."""
    embeddings = []
    failed_indices = []
    
    for i, text in enumerate(texts):
        try:
            result = embed_batch([text])
            embeddings.append(result[0])
        except Exception as e:
            print(f"Skipping item {i}: {e}")
            failed_indices.append(i)
            embeddings.append(None)
    
    return embeddings, failed_indices
```

**Pros**: Maximum recovery **Cons**: Slow (single-item calls), inconsistent results

**Recommendation**: Start with Option A. If you hit content filter issues frequently, implement Option B.

---

## OpenAI Batch API: For Large-Scale Indexing

For massive indexing jobs (10k+ documents), OpenAI offers an asynchronous Batch API:

Process jobs asynchronously with Batch API. The service is ideal for processing jobs that don't require immediate responses. Compared to using standard endpoints directly, Batch API has: Better cost efficiency: 50% cost discount compared to synchronous APIs. Higher rate limits: Substantially more headroom compared to the synchronous APIs. Fast completion times: Each batch completes within 24 hours (and often more quickly).

### How It Works

1. Create a JSONL file with all embedding requests
2. Upload the file to OpenAI
3. Create a batch job
4. Poll for completion (usually 10-30 minutes for moderate batches)
5. Download results

```python
from openai import OpenAI
import json

client = OpenAI()

# Step 1: Create JSONL file
def create_batch_file(chunks: list[dict], output_path: str):
    with open(output_path, "w") as f:
        for i, chunk in enumerate(chunks):
            request = {
                "custom_id": f"chunk_{i}",
                "method": "POST",
                "url": "/v1/embeddings",
                "body": {
                    "model": "text-embedding-3-small",
                    "input": chunk["content"]
                }
            }
            f.write(json.dumps(request) + "\n")

# Step 2: Upload and create batch
def submit_batch(file_path: str) -> str:
    batch_file = client.files.create(
        file=open(file_path, "rb"),
        purpose="batch"
    )
    
    batch = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/embeddings",
        completion_window="24h"
    )
    
    return batch.id

# Step 3: Poll for completion
def wait_for_batch(batch_id: str) -> dict:
    import time
    
    while True:
        batch = client.batches.retrieve(batch_id)
        print(f"Status: {batch.status}")
        
        if batch.status == "completed":
            return batch
        elif batch.status in ["failed", "expired", "cancelled"]:
            raise Exception(f"Batch failed: {batch.status}")
        
        time.sleep(30)  # Poll every 30 seconds

# Step 4: Download results
def get_batch_results(batch: dict) -> list[list[float]]:
    result_file = client.files.content(batch.output_file_id)
    
    embeddings = {}
    for line in result_file.text.strip().split("\n"):
        result = json.loads(line)
        custom_id = result["custom_id"]
        embedding = result["response"]["body"]["data"][0]["embedding"]
        embeddings[custom_id] = embedding
    
    # Return in order
    return [embeddings[f"chunk_{i}"] for i in range(len(embeddings))]
```

### When to Use Batch API

|Scenario|Use Batch API?|
|---|---|
|< 1,000 chunks|No — synchronous is fine|
|1,000 - 10,000 chunks|Maybe — if cost matters|
|> 10,000 chunks|Yes — 50% cost savings add up|
|Real-time indexing|No — need immediate results|
|Nightly batch job|Yes — perfect use case|

Batch jobs are half the price of individual API calls, which is beneficial if you need to embed a large amount of text.

---

## Query-Time Embedding: Don't Forget This

Embedding happens at two times:

1. **Index time**: When you add chunks to the vector store
2. **Query time**: When you search

**Critical**: You must use the **same embedding model** at both times.

```python
# Index time
collection = client.create_collection(
    name="my_docs",
    embedding_function=OpenAIEmbeddingFunction(model_name="text-embedding-3-small")
)
collection.add(documents=["..."])

# Query time — MUST use same model
results = collection.query(query_texts=["my query"])  # Uses collection's EF

# OR if you pre-computed embeddings:
query_embedding = embed_batch(["my query"])[0]
results = collection.query(query_embeddings=[query_embedding])
```

If you use `text-embedding-3-small` at index time and `text-embedding-3-large` at query time, similarity scores will be meaningless — the vector spaces are incompatible.

**Store the model name in metadata** so you can verify compatibility:

```python
collection = client.create_collection(
    name="my_docs",
    metadata={"embedding_model": "text-embedding-3-small"}
)
```

---

## Embedding Dimensions and Storage

Different models produce different vector dimensions:

|Model|Dimensions|Storage per Vector|
|---|---|---|
|text-embedding-3-small|1536|~6 KB|
|text-embedding-3-large|3072|~12 KB|
|all-MiniLM-L6-v2 (default)|384|~1.5 KB|

For 100,000 chunks:

- `text-embedding-3-small`: ~600 MB
- `text-embedding-3-large`: ~1.2 GB
- `all-MiniLM-L6-v2`: ~150 MB

OpenAI's newer models support dimension reduction:

```python
response = client.embeddings.create(
    model="text-embedding-3-large",
    input="some text",
    dimensions=1024  # Reduce from 3072 to 1024
)
```

Based on performance reviews of various embedding algorithms and dimensions from OpenAI documentation, text-embedding-3-large with a dimension size of 1024 keeps the embeddings relatively small without a significant performance dip.

---

## Practical Indexer Implementation

Putting it all together for your `Indexer` class:

```python
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import chromadb
import hashlib

class Indexer:
    def __init__(
        self,
        collection_name: str,
        embedding_model: str = "text-embedding-3-small",
        batch_size: int = 100
    ):
        self.openai = OpenAI()
        self.chroma = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.chroma.get_or_create_collection(
            name=collection_name,
            metadata={"embedding_model": embedding_model}
        )
        self.embedding_model = embedding_model
        self.batch_size = batch_size
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=60))
    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self.openai.embeddings.create(
            model=self.embedding_model,
            input=texts
        )
        return [item.embedding for item in response.data]
    
    def _generate_id(self, content: str, source: str) -> str:
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"{source}__{content_hash}"
    
    def index_chunks(self, chunks: list[dict]) -> dict:
        """
        Index chunks with deduplication.
        
        Args:
            chunks: List of {"content": str, "metadata": dict}
                    metadata must include "source" key
        
        Returns:
            {"indexed": int, "skipped_duplicates": int, "errors": int}
        """
        stats = {"indexed": 0, "skipped_duplicates": 0, "errors": 0}
        
        # Generate IDs
        ids = [self._generate_id(c["content"], c["metadata"]["source"]) for c in chunks]
        
        # Check for existing
        existing = set(self.collection.get(ids=ids, include=[])["ids"])
        
        # Filter to new chunks only
        new_chunks = []
        new_ids = []
        for chunk, id in zip(chunks, ids):
            if id in existing:
                stats["skipped_duplicates"] += 1
            else:
                new_chunks.append(chunk)
                new_ids.append(id)
        
        if not new_chunks:
            return stats
        
        # Embed in batches
        all_embeddings = []
        for i in range(0, len(new_chunks), self.batch_size):
            batch = new_chunks[i:i+self.batch_size]
            texts = [c["content"] for c in batch]
            
            try:
                embeddings = self._embed_batch(texts)
                all_embeddings.extend(embeddings)
            except Exception as e:
                print(f"Embedding error at batch {i}: {e}")
                stats["errors"] += len(batch)
                # Fill with None to maintain index alignment
                all_embeddings.extend([None] * len(batch))
        
        # Filter out failed embeddings
        successful = [
            (id, chunk, emb) 
            for id, chunk, emb in zip(new_ids, new_chunks, all_embeddings)
            if emb is not None
        ]
        
        if successful:
            self.collection.add(
                ids=[s[0] for s in successful],
                embeddings=[s[2] for s in successful],
                documents=[s[1]["content"] for s in successful],
                metadatas=[s[1]["metadata"] for s in successful]
            )
            stats["indexed"] = len(successful)
        
        return stats
```

---

## Key Takeaways

1. **Pre-compute embeddings for production** — gives you control over batching, retries, and progress tracking
    
2. **Batch aggressively** — single-item API calls waste network overhead
    
3. **Use Batch API for large jobs** — 50% cost savings, higher rate limits
    
4. **Same model at index and query time** — store model name in metadata
    
5. **Handle failures gracefully** — don't lose 99 good embeddings because of 1 bad one
    
6. **Consider dimension reduction** — `text-embedding-3-large` at 1024 dims is a good balance
    

---
