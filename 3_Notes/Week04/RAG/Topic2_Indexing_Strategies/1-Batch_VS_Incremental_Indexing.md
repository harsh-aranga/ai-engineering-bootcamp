# Batch Indexing vs Incremental Indexing

## The Core Distinction

**Batch indexing** means processing all your documents in one go — load everything, chunk everything, embed everything, store everything. You typically run this as a scheduled job (nightly, weekly) or when you explicitly trigger a "reindex" operation.

**Incremental indexing** means processing only what changed — detect new, modified, or deleted documents, and update the index accordingly. This happens continuously or on-demand as changes occur.

The tradeoff is simple: batch is simpler to implement but wasteful at scale; incremental is efficient but requires tracking state.

---

## Batch Indexing

### How It Works

```
[All Documents] → Chunk → Embed → Store (replace everything)
```

Every run starts fresh. You don't care what was indexed before — you reprocess the entire corpus.

### When Batch Makes Sense

1. **Initial load**: First time populating your vector store
2. **Small corpus**: Under ~10,000 documents where reprocessing is cheap
3. **Embedding model upgrade**: Old vectors are incompatible with new model anyway
4. **Schema changes**: You changed chunking strategy, metadata structure, etc.
5. **Data integrity reset**: You suspect corruption or drift, want a clean slate

### The Cost Problem

Consider a typical RAG pipeline for a documentation site with 10,000 markdown files: chunking splits documents into ~50,000 text chunks, embedding generates vectors via OpenAI API (~$0.00002 per 1K tokens), and vector store writes insert 50,000 vectors. Cost runs ~$5–10 per run depending on document size, time takes 10–30 minutes with rate limits and API latency, plus significant CPU for chunking and serialization.

Now imagine running this daily. Or worse, running it every time a single document changes.

### Batch Indexing Pseudocode

```python
def batch_index(documents: list[Document], collection: Collection):
    """Nuclear option: wipe and rebuild."""
    
    # Step 1: Clear existing data
    collection.delete(where={})  # Delete everything
    
    # Step 2: Process all documents
    all_chunks = []
    for doc in documents:
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)
    
    # Step 3: Embed in batches (API efficiency)
    embeddings = embed_in_batches(all_chunks, batch_size=100)
    
    # Step 4: Insert all
    collection.add(
        ids=[generate_id(c) for c in all_chunks],
        embeddings=embeddings,
        documents=[c.text for c in all_chunks],
        metadatas=[c.metadata for c in all_chunks]
    )
```

---

## Incremental Indexing

### How It Works

```
[Changed Documents Only] → Detect changes → Chunk → Embed → Upsert/Delete
```

You maintain state about what's already indexed (hashes, timestamps, document IDs) and only process the delta.

### The Core Mechanics

Incremental indexing processes only new or updated data in real time, avoiding the need to reindex the entire dataset. This minimizes resource usage and keeps search indices or databases up-to-date with minimal delay.

To make incremental work, you need:

1. **Document identity**: A stable ID for each source document
2. **Change detection**: Usually a content hash or modification timestamp
3. **Mapping from source to chunks**: Know which chunks came from which document (so you can delete orphans)

### Change Detection Strategies

**Hash-based**: Hash the document content. If hash differs from stored hash, document changed.

```python
import hashlib

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

# On index:
stored_hashes = {"doc_1": "abc123", "doc_2": "def456"}

# On re-run:
current_hash = content_hash(doc.content)
if stored_hashes.get(doc.id) != current_hash:
    # Document is new or modified → re-index it
    pass
```

**Timestamp-based**: Compare file modification time against last index run.

```python
import os
from datetime import datetime

last_index_time = load_last_run_timestamp()

for filepath in document_files:
    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
    if mtime > last_index_time:
        # File changed since last run → re-index
        pass
```

### LlamaIndex's Approach

Using the document.doc_id or node.ref_doc_id as a grounding point, the ingestion pipeline will actively look for duplicate documents. If a duplicate doc_id is detected, and the hash has changed, the document will be re-processed and upserted. If a duplicate doc_id is detected and the hash is unchanged, the node is skipped.

LlamaIndex provides three document management strategies:

`upserts`: Checks if a document is already in the doc store based on its id. If it is not, or if the hash of the document is updated, it will update the document in the doc store and run the transformations. `duplicates_only`: Only checks if the hash of a document is already in the doc store. `upserts_and_delete`: Like the upsert strategy but it will also delete non-existing documents from the doc store.

### Incremental Indexing Pseudocode

```python
def incremental_index(
    documents: list[Document],
    collection: Collection,
    doc_store: DocumentStore  # Tracks what's indexed
):
    """Smart update: only process what changed."""
    
    current_doc_ids = set()
    
    for doc in documents:
        current_doc_ids.add(doc.id)
        doc_hash = content_hash(doc.content)
        stored_hash = doc_store.get_hash(doc.id)
        
        if stored_hash is None:
            # New document
            index_document(doc, collection)
            doc_store.store_hash(doc.id, doc_hash)
            
        elif stored_hash != doc_hash:
            # Modified document - delete old chunks, add new
            collection.delete(where={"source_id": doc.id})
            index_document(doc, collection)
            doc_store.store_hash(doc.id, doc_hash)
            
        # else: unchanged, skip
    
    # Handle deletions: docs that were indexed but no longer exist
    indexed_doc_ids = doc_store.get_all_doc_ids()
    deleted_ids = indexed_doc_ids - current_doc_ids
    
    for doc_id in deleted_ids:
        collection.delete(where={"source_id": doc_id})
        doc_store.remove(doc_id)
```

---

## The Orphan Problem

This is subtle but critical. When you chunk a document, one document becomes many chunks. If you update that document:

1. Old chunks still exist in the vector store
2. New chunks get added
3. Now you have duplicates (or worse, stale data)

**Solution**: Track the mapping from source document to chunk IDs.

```python
# When indexing:
chunk_ids = []
for i, chunk in enumerate(chunks):
    chunk_id = f"{doc.id}__chunk_{i}"  # Deterministic ID
    chunk_ids.append(chunk_id)

# Store mapping
doc_store.set_chunk_ids(doc.id, chunk_ids)

# When re-indexing same document:
old_chunk_ids = doc_store.get_chunk_ids(doc.id)
collection.delete(ids=old_chunk_ids)  # Remove old chunks
# ... then add new chunks
```

Alternatively, store `source_id` in chunk metadata and delete by filter:

```python
collection.delete(where={"source_id": doc.id})
```

---

## Comparison Matrix

|Aspect|Batch Indexing|Incremental Indexing|
|---|---|---|
|**Implementation complexity**|Simple|Moderate (need state tracking)|
|**Cost per run**|High (full corpus)|Low (delta only)|
|**Latency to searchable**|High (wait for full job)|Low (near real-time possible)|
|**Data freshness**|Stale between runs|Current|
|**Failure recovery**|Restart from scratch|Resume from checkpoint|
|**Consistency guarantees**|Strong (full rebuild)|Requires careful handling|
|**Suitable corpus size**|Small to medium|Any size|

---

## Hybrid Approach: The Practical Middle Ground

Hybrid approaches, like combining daily batches with incremental updates for urgent changes, can mitigate some limitations. For example, a social media platform might batch-index posts overnight but incrementally index trending topics in real time.

Most production systems use both:

- **Incremental** for day-to-day updates (new docs, edits)
- **Batch** for periodic "ground truth" rebuilds (weekly/monthly)
- **Batch** when migration events occur (new embedding model, schema change)

```python
class HybridIndexer:
    def __init__(self, collection, doc_store):
        self.collection = collection
        self.doc_store = doc_store
    
    def incremental_update(self, documents):
        """Called frequently (on change, hourly, etc.)"""
        # ... detect and process changes only
        pass
    
    def full_rebuild(self, documents):
        """Called rarely (weekly, on model upgrade, etc.)"""
        # ... wipe and rebuild
        pass
    
    def should_rebuild(self) -> bool:
        """Heuristics for when incremental isn't enough"""
        # - Too many incremental updates since last rebuild
        # - Index fragmentation detected
        # - Embedding model version changed
        # - Schema version changed
        pass
```

---

## Failure Handling Considerations

Both methods risk data loss or duplication if failures occur mid-process, requiring careful error handling and recovery mechanisms.

**Batch failure**: You've processed 50% of documents, script crashes. Options:

- Restart from scratch (simple, wasteful)
- Checkpoint progress, resume (complex, efficient)

**Incremental failure**: You've processed 3 of 5 changed documents, script crashes. Options:

- Re-run entire incremental (will skip already-processed via hash check)
- Transaction-like approach (only commit state after all operations succeed)

---

## Key Takeaways

1. **Batch is not wrong** — it's the right choice for initial loads, model migrations, and small corpuses
2. **Incremental requires infrastructure** — document store, hash tracking, source-to-chunk mapping
3. **The orphan problem is real** — always clean up old chunks when updating documents
4. **Hybrid is typical in production** — incremental for freshness, periodic batch for consistency
5. **Failure modes differ** — batch fails catastrophically, incremental can partially succeed (which can be worse if not handled)

---

