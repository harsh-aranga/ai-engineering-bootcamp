# Document IDs: Deterministic vs Random, Deduplication

## Why IDs Matter More Than You Think

Every chunk you store in a vector database needs an ID. This isn't just bookkeeping — your ID strategy determines:

1. **Can you update without duplicates?** (upsert behavior)
2. **Can you find and delete related chunks?** (orphan cleanup)
3. **Can you detect if content already exists?** (deduplication)
4. **Can you resume a failed indexing run?** (idempotency)

Get this wrong and you'll have duplicate chunks, orphaned data, or indexes that balloon with garbage on every re-run.

---

## The Two Approaches

### Random IDs

Generate a unique identifier with no relationship to the content.

```python
import uuid

chunk_id = str(uuid.uuid4())  # e.g., "550e8400-e29b-41d4-a716-446655440000"
```

**Properties**:

- Guaranteed unique (practically)
- No relationship between ID and content
- Same content indexed twice → two different IDs → duplicates

### Deterministic IDs

Generate an identifier that's derived from the content or source, so the same input always produces the same ID.

```python
import hashlib

def deterministic_id(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]

chunk_id = deterministic_id("This is my chunk text")  
# Always returns the same hash for the same text
```

**Properties**:

- Reproducible: same content → same ID
- Enables upsert: re-indexing same content updates rather than duplicates
- Enables deduplication: can check if content already exists before embedding

---

## ID Strategy Options

Chroma is unopinionated about document IDs and delegates those decisions to the user. This frees users to build semantics around their IDs.

Here are the common strategies:

### 1. Random UUIDs

```python
import uuid

def random_uuid() -> str:
    return str(uuid.uuid4())
```

**Use when**: You have external tracking of what's indexed, or you always delete-and-rebuild.

**Problem**: Run your indexer twice → double the chunks. No built-in deduplication.

### 2. Content Hash (SHA256)

```python
import hashlib

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]
```

**Use when**: You want exact deduplication — identical text = same ID.

**Caveat**: It is also possible to use the document as basis for the hash, the downside of that is that when the document changes, and you have a semantic around the text as relating to the hash, you may need to update the hash.

If someone fixes a typo, hash changes, old chunk orphaned.

### 3. Source + Position (Composite ID)

```python
def composite_id(source_file: str, chunk_index: int) -> str:
    return f"{source_file}__chunk_{chunk_index}"

# Example: "docs/guide.pdf__chunk_0", "docs/guide.pdf__chunk_1"
```

**Use when**: You want to find all chunks from a source (for deletion/update).

**Caveat**: Position-based IDs break when content shifts (as we discussed earlier).

### 4. Source + Content Hash (Hybrid)

```python
def hybrid_id(source_file: str, content: str) -> str:
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"{source_file}__{content_hash}"

# Example: "docs/guide.pdf__a1b2c3d4e5f6"
```

**Use when**: You want both source traceability AND content-based deduplication.

**This is often the best general-purpose approach.**

### 5. ULIDs (Sortable UUIDs)

```python
from ulid import ULID

def ulid_id() -> str:
    return str(ULID())
```

ULIDs are a variant of UUIDs that are lexicographically sortable. They are also 128 bits long, like UUIDs, but they are encoded in a way that makes them sortable. This can be useful if you need predictable ordering of your documents.

**Use when**: You care about insertion order or time-based queries.

---

## Deduplication: The Core Problem

You have 1000 documents. You run your indexer. You run it again tomorrow (maybe some docs changed, maybe they didn't). What happens?

### Without Deduplication (Random IDs)

```
Run 1: 1000 docs → 5000 chunks indexed
Run 2: 1000 docs → 5000 NEW chunks indexed (duplicates)
Run 3: 1000 docs → 5000 NEW chunks indexed (more duplicates)

Total: 15,000 chunks (only 5000 are valid)
```

Your vector store is now 3x the size it should be, and queries return duplicate results.

### With Deduplication (Deterministic IDs + Upsert)

```
Run 1: 1000 docs → 5000 chunks indexed
Run 2: 1000 docs → 5000 chunks upserted (no new entries, IDs match)
Run 3: 1000 docs → 5000 chunks upserted (still no growth)

Total: 5000 chunks
```

Same content produces same IDs. Upsert updates existing entries instead of creating new ones.

---

## How Deduplication Works in Practice

### Strategy 1: ID-Based Deduplication (Let the DB Handle It)

Generate deterministic IDs. Use `upsert` instead of `add`. The vector store handles duplicates.

```python
def index_chunks(chunks: list[dict], collection):
    ids = [deterministic_id(c["content"]) for c in chunks]
    embeddings = embed_batch([c["content"] for c in chunks])
    
    # Upsert: if ID exists, update. If not, insert.
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=[c["content"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks]
    )
```

Note that if you provide an ID which is not present, ChromaDB will consider it as an add operation.

So `upsert` is safe: new content gets added, existing content gets updated.

### Strategy 2: Pre-Check Deduplication (Avoid Embedding Costs)

Embedding API calls cost money. If content already exists, why re-embed?

```python
def index_with_precheck(chunks: list[dict], collection):
    ids = [deterministic_id(c["content"]) for c in chunks]
    
    # Check which IDs already exist
    existing = collection.get(ids=ids, include=[])  # Just get IDs, no data
    existing_ids = set(existing["ids"])
    
    # Filter to only new chunks
    new_chunks = [c for c, id in zip(chunks, ids) if id not in existing_ids]
    new_ids = [id for id in ids if id not in existing_ids]
    
    if not new_chunks:
        return {"indexed": 0, "skipped": len(chunks)}
    
    # Only embed and store new content
    embeddings = embed_batch([c["content"] for c in new_chunks])
    collection.add(
        ids=new_ids,
        embeddings=embeddings,
        documents=[c["content"] for c in new_chunks],
        metadatas=[c["metadata"] for c in new_chunks]
    )
    
    return {"indexed": len(new_chunks), "skipped": len(existing_ids)}
```

**Tradeoff**: Extra `get` call per batch vs. embedding cost savings.

Worth it when:

- Embedding is expensive (large batches, premium models)
- Re-runs are common (CI/CD pipelines, scheduled jobs)
- Most content is unchanged between runs

### Strategy 3: Hash-Based Change Detection (Document Level)

Track document hashes separately. Only re-process documents that changed.

```python
class DocumentTracker:
    def __init__(self):
        self.doc_hashes = {}  # doc_id -> hash
    
    def has_changed(self, doc_id: str, content: str) -> bool:
        current_hash = hashlib.sha256(content.encode()).hexdigest()
        stored_hash = self.doc_hashes.get(doc_id)
        
        if stored_hash != current_hash:
            self.doc_hashes[doc_id] = current_hash
            return True
        return False

# Usage
tracker = DocumentTracker()

for doc in documents:
    if tracker.has_changed(doc.id, doc.content):
        # Document changed → re-chunk, re-embed, re-index
        chunks = chunk_document(doc)
        index_chunks(chunks, collection)
    # else: skip entirely
```

This is what LlamaIndex's `IngestionPipeline` does under the hood with its document store.

---

## Choosing Your Strategy: Decision Matrix

|Scenario|ID Strategy|Deduplication Method|
|---|---|---|
|One-time bulk load, never re-run|Random UUID|None needed|
|Periodic re-indexing, same corpus|Content hash|Upsert|
|Need to delete by source file|Source + position|Delete by source, then re-add|
|Incremental updates, cost-sensitive|Source + content hash|Pre-check before embedding|
|Mixed: some updates, some new|Hybrid ID|Document-level change detection|

---

## Implementation: Putting It Together

Here's a practical `ChunkIDGenerator` that supports multiple strategies:

```python
import hashlib
import uuid
from enum import Enum
from typing import Callable

class IDStrategy(Enum):
    RANDOM = "random"
    CONTENT_HASH = "content_hash"
    SOURCE_POSITION = "source_position"
    SOURCE_CONTENT = "source_content"

class ChunkIDGenerator:
    def __init__(self, strategy: IDStrategy = IDStrategy.SOURCE_CONTENT):
        self.strategy = strategy
    
    def generate(
        self, 
        content: str, 
        source_id: str = None, 
        position: int = None
    ) -> str:
        if self.strategy == IDStrategy.RANDOM:
            return str(uuid.uuid4())
        
        elif self.strategy == IDStrategy.CONTENT_HASH:
            return self._hash(content)
        
        elif self.strategy == IDStrategy.SOURCE_POSITION:
            if source_id is None or position is None:
                raise ValueError("SOURCE_POSITION requires source_id and position")
            return f"{source_id}__chunk_{position}"
        
        elif self.strategy == IDStrategy.SOURCE_CONTENT:
            if source_id is None:
                raise ValueError("SOURCE_CONTENT requires source_id")
            content_hash = self._hash(content)[:12]
            return f"{source_id}__{content_hash}"
        
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

# Usage
gen = ChunkIDGenerator(IDStrategy.SOURCE_CONTENT)

chunks = [
    {"content": "First chunk text", "source": "doc_123"},
    {"content": "Second chunk text", "source": "doc_123"},
]

ids = [
    gen.generate(c["content"], source_id=c["source"]) 
    for c in chunks
]
# ['doc_123__a1b2c3d4e5f6', 'doc_123__f6e5d4c3b2a1']
```

---

## Edge Cases and Gotchas

### 1. Whitespace Sensitivity

```python
text1 = "Hello world"
text2 = "Hello  world"  # extra space

hash(text1) != hash(text2)  # Different IDs!
```

**Solution**: Normalize before hashing.

```python
def normalize(text: str) -> str:
    return " ".join(text.split())  # Collapse whitespace

def content_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()[:16]
```

### 2. Encoding Issues

```python
text = "café"
text.encode()  # Works in UTF-8
text.encode("ascii")  # Fails!
```

**Solution**: Always specify encoding.

```python
hashlib.sha256(text.encode("utf-8")).hexdigest()
```

### 3. Hash Collisions

SHA256 truncated to 16 characters = 64 bits of entropy. Collision probability is low but non-zero at scale.

For 1 million documents: collision probability ≈ 0.00000003%

For 1 billion documents: collision probability ≈ 0.003%

**Solution**: If you're at that scale, use longer hashes or UUIDs.

### 4. The "Same Text, Different Source" Problem

Two documents contain identical paragraphs. With pure content hashing:

```python
# From doc_A.pdf
chunk_1 = "Copyright 2024. All rights reserved."

# From doc_B.pdf (same boilerplate)
chunk_2 = "Copyright 2024. All rights reserved."

content_hash(chunk_1) == content_hash(chunk_2)  # Same ID!
```

Second chunk overwrites first. You lose source tracking.

**Solution**: Include source in the ID.

```python
def source_aware_id(content: str, source: str) -> str:
    combined = f"{source}::{content}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]
```

---

## Key Takeaways

1. **Random IDs = no deduplication**. Fine for one-time loads, dangerous for re-runs.
    
2. **Content hash = exact deduplication**. Same text → same ID → upsert works.
    
3. **Include source in ID** if you need to delete/update by source document.
    
4. **Normalize before hashing**. Whitespace and encoding can create false misses.
    
5. **Pre-check before embedding** if you're cost-sensitive and expect many duplicates.
    
6. **The hybrid approach (source + content hash)** is usually the best default for production pipelines.
    

---

