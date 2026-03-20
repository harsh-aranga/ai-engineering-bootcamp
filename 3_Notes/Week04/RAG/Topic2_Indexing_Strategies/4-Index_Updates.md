# Index Updates: Add, Update, Delete

## The Four Operations

ChromaDB (and most vector stores) provide four core operations for managing data:

|Operation|Behavior|If ID Exists|If ID Missing|
|---|---|---|---|
|`add`|Insert new records|Error (logged, ignored)|Inserts|
|`update`|Modify existing records|Updates|Error (logged, ignored)|
|`upsert`|Insert or update|Updates|Inserts|
|`delete`|Remove records|Deletes|No-op|

Understanding when to use each is critical for building a correct indexing pipeline.

---

## Add: Insert New Records Only

```python
collection.add(
    ids=["chunk_1", "chunk_2"],
    embeddings=[[0.1, 0.2, ...], [0.3, 0.4, ...]],
    documents=["First chunk text", "Second chunk text"],
    metadatas=[{"source": "doc_A"}, {"source": "doc_A"}]
)
```

### Behavior

Each document must have a unique associated id. Trying to .add the same ID twice will result in only the initial value being stored.

If you call `add` with an ID that already exists:

- The new data is **ignored**
- An error is logged (not raised)
- The original data remains unchanged

### When to Use Add

- **Initial bulk load**: First-time indexing of a corpus
- **Guaranteed new data**: When you're certain IDs don't exist (e.g., after a delete)
- **Strict insert semantics**: When duplicates indicate a bug you want to catch

### Gotcha: Silent Failures

`add` doesn't raise an exception for duplicate IDs — it just logs and ignores. This can mask bugs:

```python
# First run
collection.add(ids=["doc_1"], documents=["Original content"])

# Second run (maybe script restarted)
collection.add(ids=["doc_1"], documents=["Updated content"])

# doc_1 still has "Original content" — the update was silently ignored!
```

If you want insert-or-update semantics, use `upsert`.

---

## Update: Modify Existing Records Only

```python
collection.update(
    ids=["chunk_1"],
    documents=["Updated chunk text"],
    metadatas=[{"source": "doc_A", "version": 2}]
)
```

### Behavior

If an id is not found in the collection, an error will be logged and the update will be ignored. If documents are supplied without corresponding embeddings, the embeddings will be recomputed with the collection's embedding function.

Key points:

- Only updates **existing** IDs
- Missing IDs are logged and skipped (not inserted)
- If you provide new `documents` without `embeddings`, ChromaDB re-embeds automatically (if collection has an embedding function)
- If you provide new `embeddings`, they must match collection dimensionality

### Partial Updates

You can update specific fields without touching others:

```python
# Update only metadata, keep document and embedding unchanged
collection.update(
    ids=["chunk_1"],
    metadatas=[{"reviewed": True}]
)

# Update only document (embedding auto-recomputed)
collection.update(
    ids=["chunk_1"],
    documents=["Corrected text with typo fixed"]
)

# Update only embedding (document unchanged)
collection.update(
    ids=["chunk_1"],
    embeddings=[[0.5, 0.6, ...]]
)
```

### When to Use Update

- **Metadata-only changes**: Updating tags, timestamps, status flags
- **Known existing records**: When you're certain the ID exists
- **Strict update semantics**: When updating a non-existent ID indicates a bug

---

## Upsert: Insert or Update (The Safe Default)

```python
collection.upsert(
    ids=["chunk_1", "chunk_new"],
    embeddings=[[0.1, 0.2, ...], [0.3, 0.4, ...]],
    documents=["Updated existing chunk", "Brand new chunk"],
    metadatas=[{"source": "doc_A"}, {"source": "doc_B"}]
)
```

### Behavior

Chroma also supports an upsert operation, which updates existing items, or adds them if they don't yet exist. If an id is not present in the collection, the corresponding items will be created as per add. Items with existing ids will be updated as per update.

This is the **idempotent** operation:

- Same input, same result, no matter how many times you run it
- Existing IDs → updated
- New IDs → inserted

### When to Use Upsert

- **Incremental indexing**: Re-running pipeline on same data should be safe
- **Unknown state**: When you don't know if IDs exist
- **Idempotent pipelines**: CI/CD, scheduled jobs, retry scenarios
- **Most production use cases**: Unless you have specific reason to use add/update

### Upsert Is Almost Always What You Want

For indexing pipelines, `upsert` is the default choice because:

1. **Safe re-runs**: Script crashes mid-batch, you restart — already-processed chunks get updated (same data), new chunks get added
2. **No pre-check needed**: Don't need to query existing IDs first
3. **Handles both cases**: New documents and updated documents in same call

```python
def index_chunks(chunks: list[dict], collection):
    """Idempotent indexing — safe to re-run."""
    ids = [generate_id(c["content"], c["source"]) for c in chunks]
    embeddings = embed_batch([c["content"] for c in chunks])
    
    # Upsert: doesn't matter if some exist, some don't
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=[c["content"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks]
    )
```

---

## Delete: Remove Records

### Delete by ID

```python
# Delete specific IDs
collection.delete(ids=["chunk_1", "chunk_2", "chunk_3"])
```

If an ID doesn't exist, it's silently ignored (no error).

### Delete by Filter (Where Clause)

```python
# Delete all chunks from a specific source
collection.delete(where={"source": "doc_A.pdf"})

# Delete all chunks with a specific tag
collection.delete(where={"status": "deprecated"})

# Delete with compound filter
collection.delete(where={
    "$and": [
        {"source": "doc_A.pdf"},
        {"version": {"$lt": 3}}
    ]
})
```

Chroma supports deleting items from a collection by id using .delete. The embeddings, documents, and metadata associated with each item will be deleted. ⚠️ Naturally, this is a destructive operation, and cannot be undone. .delete also supports the where filter.

### When to Use Delete

- **Document removal**: Source document deleted, remove all its chunks
- **Document update**: Delete old chunks before adding new ones (the pattern we discussed)
- **Cleanup**: Remove stale, deprecated, or test data
- **Selective pruning**: Remove chunks matching certain criteria

---

## Common Patterns

### Pattern 1: Document Update (Delete + Add)

The cleanest way to handle document updates — no orphans, no complexity:

```python
def update_document(doc_id: str, chunks: list[dict], collection):
    """Replace all chunks for a document."""
    
    # Step 1: Delete all existing chunks from this source
    collection.delete(where={"source_id": doc_id})
    
    # Step 2: Add new chunks
    ids = [f"{doc_id}__{i}" for i in range(len(chunks))]
    embeddings = embed_batch([c["content"] for c in chunks])
    
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=[c["content"] for c in chunks],
        metadatas=[{"source_id": doc_id, **c["metadata"]} for c in chunks]
    )
```

Why not `upsert` here? Because upsert doesn't delete orphans. If old document had 10 chunks and new has 5, upsert updates chunks 0-4 but leaves chunks 5-9 orphaned.

### Pattern 2: Incremental Indexing (Upsert with Deduplication)

For re-running pipelines where documents may or may not have changed:

```python
def incremental_index(documents: list[Document], collection, tracker: DocumentTracker):
    """Index only changed documents."""
    
    for doc in documents:
        if not tracker.has_changed(doc.id, doc.content):
            continue  # Skip unchanged documents
        
        # Document changed — delete old chunks, add new
        collection.delete(where={"source_id": doc.id})
        
        chunks = chunk_document(doc)
        ids = [generate_id(c["content"], doc.id) for c in chunks]
        embeddings = embed_batch([c["content"] for c in chunks])
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=[c["content"] for c in chunks],
            metadatas=[{"source_id": doc.id} for c in chunks]
        )
        
        tracker.mark_indexed(doc.id, doc.content)
```

### Pattern 3: Metadata-Only Update

When you need to update metadata without re-embedding:

```python
def mark_chunks_reviewed(chunk_ids: list[str], reviewer: str, collection):
    """Update metadata without touching embeddings."""
    
    collection.update(
        ids=chunk_ids,
        metadatas=[{
            "reviewed": True,
            "reviewer": reviewer,
            "reviewed_at": datetime.now().isoformat()
        } for _ in chunk_ids]
    )
```

### Pattern 4: Bulk Delete by Source

When a source document is deleted:

```python
def remove_document(doc_id: str, collection):
    """Remove all chunks from a deleted document."""
    
    # Get count before (for logging)
    existing = collection.get(where={"source_id": doc_id}, include=[])
    count = len(existing["ids"])
    
    # Delete
    collection.delete(where={"source_id": doc_id})
    
    return {"deleted": count}
```

---

## Operation Comparison Matrix

|Scenario|Operation|Why|
|---|---|---|
|First-time bulk load|`add`|Clean slate, no duplicates expected|
|Re-running same pipeline|`upsert`|Idempotent, handles both new and existing|
|Document content changed|`delete` + `add`|Cleans orphans, fresh chunks|
|Metadata update only|`update`|Preserves embeddings, fast|
|Document deleted from source|`delete` with `where`|Remove all related chunks|
|Unknown if ID exists|`upsert`|Safe for both cases|

---

## Performance Considerations

### HNSW Index Updates

If you are trying to add 1000s or even 10,000s of documents at once and depending on how much data is already in your collection Chroma (specifically the HNSW graph updates) can become a bottleneck.

HNSW index updates are expensive. When you add/update/upsert:

1. New vectors are inserted into the graph
2. Edges are recalculated for nearest neighbors
3. Graph may need rebalancing

**Tips**:

- Batch your operations (100-1000 items per call)
- For massive initial loads, consider building in batches
- Deletes can fragment the index over time (compaction may be needed)

### Delete Performance

Deletes by ID are fast (direct lookup). Deletes by `where` clause require scanning:

```python
# Fast: direct ID lookup
collection.delete(ids=["chunk_1", "chunk_2"])

# Slower: requires metadata scan
collection.delete(where={"source_id": "doc_A"})
```

For large collections with frequent source-based deletes, consider:

- Maintaining a separate mapping of source_id → chunk_ids
- Using ID prefixes that encode source (e.g., `doc_A__chunk_0`)

---

## Error Handling

### Add/Update Silent Failures

Both `add` and `update` log errors but don't raise exceptions for missing/duplicate IDs:

```python
# This doesn't raise — just logs a warning
collection.add(ids=["existing_id"], documents=["new content"])

# This also doesn't raise
collection.update(ids=["nonexistent_id"], documents=["content"])
```

If you need to know if operations succeeded:

```python
def verified_add(ids: list[str], collection, **kwargs) -> dict:
    """Add with verification."""
    
    # Check for pre-existing
    existing = collection.get(ids=ids, include=[])
    existing_ids = set(existing["ids"])
    
    new_ids = [id for id in ids if id not in existing_ids]
    
    if not new_ids:
        return {"added": 0, "skipped": len(ids)}
    
    # Filter to only new items
    # ... (filter kwargs to match new_ids)
    
    collection.add(ids=new_ids, **filtered_kwargs)
    
    return {"added": len(new_ids), "skipped": len(ids) - len(new_ids)}
```

### Dimension Mismatch

If the supplied embeddings are not the same dimension as the collection, an exception will be raised.

This one **does** raise — it's a hard error:

```python
# Collection was created with 384-dim embeddings
collection.add(
    ids=["new"],
    embeddings=[[0.1] * 1536]  # Wrong dimension!
)
# Raises: InvalidDimensionException
```

Always verify embedding model consistency.

---

## Putting It Together: Complete Indexer

Here's the `Indexer` class with all operations:

```python
import hashlib
from datetime import datetime
from typing import Optional

class Indexer:
    def __init__(self, collection, embedding_fn, batch_size: int = 100):
        self.collection = collection
        self.embedding_fn = embedding_fn
        self.batch_size = batch_size
    
    def _generate_id(self, content: str, source: str) -> str:
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"{source}__{content_hash}"
    
    def index_chunks(self, chunks: list[dict]) -> dict:
        """
        Index chunks with deduplication via upsert.
        
        Args:
            chunks: List of {"content": str, "metadata": dict}
                    metadata must include "source" key
        """
        stats = {"indexed": 0, "errors": 0}
        
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i+self.batch_size]
            
            ids = [self._generate_id(c["content"], c["metadata"]["source"]) for c in batch]
            
            try:
                embeddings = self.embedding_fn([c["content"] for c in batch])
                
                self.collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=[c["content"] for c in batch],
                    metadatas=[c["metadata"] for c in batch]
                )
                stats["indexed"] += len(batch)
                
            except Exception as e:
                print(f"Error in batch {i}: {e}")
                stats["errors"] += len(batch)
        
        return stats
    
    def delete_by_source(self, source: str) -> int:
        """Delete all chunks from a specific source file."""
        existing = self.collection.get(where={"source": source}, include=[])
        count = len(existing["ids"])
        
        if count > 0:
            self.collection.delete(where={"source": source})
        
        return count
    
    def reindex_source(self, source: str, chunks: list[dict]) -> dict:
        """Delete old chunks from source and index new ones."""
        deleted = self.delete_by_source(source)
        
        # Ensure all chunks have the source set
        for chunk in chunks:
            chunk["metadata"]["source"] = source
        
        result = self.index_chunks(chunks)
        result["deleted"] = deleted
        
        return result
    
    def update_metadata(self, ids: list[str], metadata_updates: dict) -> int:
        """Update metadata for specific chunks without re-embedding."""
        existing = self.collection.get(ids=ids, include=["metadatas"])
        
        # Merge new metadata with existing
        updated_metadatas = []
        for existing_meta in existing["metadatas"]:
            merged = {**(existing_meta or {}), **metadata_updates}
            updated_metadatas.append(merged)
        
        self.collection.update(
            ids=existing["ids"],
            metadatas=updated_metadatas
        )
        
        return len(existing["ids"])
```

---

## Key Takeaways

1. **Use `upsert` by default** — it's idempotent and handles both new and existing IDs
    
2. **Use `delete` + `add` for document updates** — prevents orphaned chunks
    
3. **Use `update` for metadata-only changes** — preserves embeddings, fast
    
4. **`add` and `update` fail silently** — they log but don't raise on ID conflicts
    
5. **Always include source tracking in metadata** — enables `delete(where={"source": ...})`
    
6. **Batch your operations** — 100-1000 items per call for performance
    
7. **Dimension mismatches are hard errors** — ensure consistent embedding model
    

---
