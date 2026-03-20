# Index Maintenance: Compaction, Reindexing

## Why Maintenance Matters

Vector indexes (especially HNSW) degrade over time. Unlike traditional B-tree indexes that handle insertions and deletions gracefully, graph-based indexes accumulate "debt" with every mutation. Without maintenance:

- Memory usage grows unbounded
- Query performance degrades
- Search recall (accuracy) drops
- Disk space fills with garbage

Understanding why this happens and how to fix it is essential for production RAG systems.

---

## The HNSW Deletion Problem

HNSW wasn't designed for dynamic datasets. Unlike traditional databases, where data deletions can be handled by simply deleting a row in a table, using HNSW in a vector database often requires a complete rebuild to maintain optimal performance and accuracy.

### Why Deletions Are Hard

HNSW is a layered graph where nodes (vectors) connect to their nearest neighbors. When you delete a node:

1. **Graph connectivity breaks**: Other nodes used that deleted node as a navigation path
2. **Edges become invalid**: Neighbors pointing to the deleted node now point to nothing
3. **Search paths degrade**: Queries that would have traversed through that node now take suboptimal routes

If you delete a 1-node layer, all the subsequent layers that were attached to that 1-node layer get disconnected from the graph and are now in limbo. These disconnections break the index. To fix the graph (repair the connections), you must rebuild the index entirely from scratch.

### Soft Deletes vs Hard Deletes

Hard Deletes: Physically removing the vector and updating the index structure. This is often inefficient or unsupported for graph indexes like HNSW due to the complexity of repairing the graph connectivity. It can lead to index fragmentation or reduced search quality if not handled carefully.

Most vector stores use **soft deletes**:

```
[Vector marked as deleted] → Still in graph → Still uses memory → Filtered at query time
```

Soft deletes mark vectors for removal without altering the index structure immediately. Subsequent compaction or rebuilding removes marked vectors and optimizes the index.

This leads to **fragmentation**: the index contains "ghost" nodes that consume memory and slow queries but return no results.

---

## Understanding Fragmentation

Fragmentation Level - the higher the value the more unnecessary memory and performance hits your HNSW index suffers. It needs to be rebuilt.

### What Causes Fragmentation

1. **Deletions**: Soft-deleted vectors still occupy space
2. **Updates**: Old version soft-deleted, new version inserted
3. **Churn**: Frequent add/delete cycles compound the problem

### Measuring Fragmentation

In ChromaDB, you can inspect fragmentation using the `chromadb-ops` CLI:

```bash
pip install chromadb-ops

# Check index health
chops hnsw info /path/to/persist_dir --collection my_collection
```

This shows:

- **HNSW Raw Total Active Labels**: Vectors actually in use
- **HNSW Raw Allocated Labels**: Total slots allocated (including deleted)
- **Fragmentation Level**: Ratio of wasted space

HNSW Raw Total Active Labels - the total number of active labels in the HNSW index. HNSW Raw Allocated Labels - the total number of allocated labels in the HNSW index.

### When to Worry

- Fragmentation > 20%: Consider maintenance
- Fragmentation > 50%: Rebuild recommended
- Query latency increasing over time: Likely fragmentation

---

## Compaction

Compaction is the process of cleaning up soft-deleted data without fully rebuilding the index.

### How ChromaDB Handles Compaction

On writes: Chroma saves changes durably first, then updates indexes in the background. Compaction materializes new index versions in the background.

ChromaDB uses a Write-Ahead Log (WAL) architecture:

1. **Write path**: Changes go to WAL first (durable)
2. **Background compaction**: WAL entries are merged into the HNSW index
3. **Cleanup**: Old WAL entries are pruned

### WAL Management

wal clean - cleans up the WAL from committed transactions. Recent Chroma version automatically prune the WAL so this is not needed unless you have older version of Chroma or disabled automatic WAL pruning.

For older ChromaDB versions or heavy workloads:

```bash
# Check WAL status
chops db info /path/to/persist_dir

# Clean up committed WAL entries
chops wal clean /path/to/persist_dir

# Commit pending WAL entries to index
chops wal commit /path/to/persist_dir
```

### Vacuum (SQLite Maintenance)

ChromaDB uses SQLite for metadata storage. Like any SQLite database, it benefits from occasional VACUUM:

The SQLite VACUUM command, often recommended for such scenarios, takes an exclusive lock on the database and is potentially quite slow.

```bash
# Vacuum the database (reclaim disk space)
chops wal clean /path/to/persist_dir  # This also VACUUMs
```

**Warning**: VACUUM requires exclusive lock and can be slow for large databases. Run during maintenance windows.

---

## Reindexing (Full Rebuild)

Sometimes compaction isn't enough. A full rebuild creates a fresh, optimized index from scratch.

### When to Rebuild

1. **High fragmentation**: Soft deletes have accumulated significantly
2. **HNSW parameter changes**: You want different `M`, `ef_construction`, or `ef_search` values
3. **Embedding model upgrade**: New model produces incompatible vectors
4. **Corruption**: Index is in an inconsistent state
5. **Performance degradation**: Queries are slow despite compaction

### How to Rebuild in ChromaDB

hnsw rebuild - rebuilds the HNSW index for a given collection and allows the modification of otherwise immutable (construction-only) parameters. Useful command to keep your HNSW index healthy and prevent fragmentation.

```bash
# Rebuild HNSW index for a collection
chops hnsw rebuild /path/to/persist_dir --collection my_collection
```

You can also modify HNSW parameters during rebuild:

```bash
# Rebuild with new parameters
chops hnsw rebuild /path/to/persist_dir \
    --collection my_collection \
    --m 32 \
    --ef-construction 200
```

### Manual Rebuild (Nuclear Option)

If tooling fails, you can force a rebuild from the WAL:

Once you remove/rename the UUID dir, restart Chroma and query your collection. Chroma will recreate your collection from the WAL. Depending on how large your collection is, this process can take a while.

```bash
# Find the vector segment UUID
sqlite3 /path/to/db/chroma.sqlite3 \
    "SELECT s.id, c.name FROM segments s JOIN collections c ON s.collection=c.id WHERE s.scope='VECTOR';"

# Rename/remove the segment directory
mv /path/to/persist_dir/UUID_HERE /path/to/persist_dir/UUID_HERE.bak

# Restart ChromaDB — it will rebuild from WAL
```

**Caution**: Back up your persist directory before manual operations.

---

## Orphaned Files

Orphan HNSW Directories - these are directories that are not associated with any collection. They can be safely deleted.

Orphaned files can accumulate from:

- Failed collection deletions
- Crashes during operations
- Windows file locking issues

```bash
# Clean up orphaned segment directories
chops db clean /path/to/persist_dir
```

This command cleans up orphanated HNSW segment subdirectories. The command is particularly useful for Microsoft Windows users where deleting collections may leave behind orphaned vector segment directories due to Windows file locking.

---

## Full-Text Search Index Maintenance

ChromaDB also maintains a Full-Text Search (FTS) index using SQLite FTS5. This occasionally needs maintenance:

```bash
# Rebuild FTS index (useful after tokenizer changes)
chops fts rebuild /path/to/persist_dir

# Change tokenizer during rebuild
chops fts rebuild --tokenizer unicode61 /path/to/persist_dir
```

---

## Maintenance Schedule Recommendations

|Collection Size|Churn Rate|Maintenance Frequency|
|---|---|---|
|< 10K vectors|Low|Rarely (monthly check)|
|10K - 100K|Moderate|Weekly compaction check|
|100K - 1M|High|Weekly compaction, monthly rebuild consideration|
|> 1M|Any|Dedicated maintenance windows, monitoring|

### Practical Maintenance Script

```python
import subprocess
import json
from datetime import datetime

def check_collection_health(persist_dir: str, collection: str) -> dict:
    """Check HNSW index health metrics."""
    result = subprocess.run(
        ["chops", "hnsw", "info", persist_dir, "-c", collection, "--json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

def needs_rebuild(health: dict, fragmentation_threshold: float = 0.3) -> bool:
    """Determine if collection needs rebuilding."""
    active = health.get("active_labels", 0)
    allocated = health.get("allocated_labels", 0)
    
    if allocated == 0:
        return False
    
    fragmentation = 1 - (active / allocated)
    return fragmentation > fragmentation_threshold

def maintenance_check(persist_dir: str, collections: list[str]):
    """Run maintenance check on all collections."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "collections": {}
    }
    
    for collection in collections:
        health = check_collection_health(persist_dir, collection)
        needs_work = needs_rebuild(health)
        
        report["collections"][collection] = {
            "health": health,
            "needs_rebuild": needs_work
        }
        
        if needs_work:
            print(f"⚠️  Collection '{collection}' needs rebuild (fragmentation high)")
        else:
            print(f"✅ Collection '{collection}' is healthy")
    
    return report
```

---

## When to Avoid Maintenance

Don't run maintenance operations:

1. **During peak query load**: Rebuilds consume CPU and memory
2. **Without backups**: Always back up persist directory first
3. **On live production without testing**: Test on staging first
4. **Concurrently with writes**: Some operations require exclusive access

---

## Embedding Model Migration (Special Case)

When upgrading embedding models, you can't just rebuild — old vectors are incompatible with new ones.

**Required steps**:

1. **Create new collection** with new embedding model
2. **Re-embed all source documents** with new model
3. **Index to new collection**
4. **Switch queries to new collection**
5. **Delete old collection**

```python
def migrate_embedding_model(
    old_collection_name: str,
    new_collection_name: str,
    new_embed_fn,
    client
):
    """Migrate collection to new embedding model."""
    
    old_collection = client.get_collection(old_collection_name)
    
    # Create new collection
    new_collection = client.create_collection(
        name=new_collection_name,
        metadata={"embedding_model": "text-embedding-3-large"}  # Track model
    )
    
    # Get all documents from old collection
    # (paginate for large collections)
    batch_size = 1000
    offset = 0
    
    while True:
        results = old_collection.get(
            limit=batch_size,
            offset=offset,
            include=["documents", "metadatas"]
        )
        
        if not results["ids"]:
            break
        
        # Re-embed with new model
        new_embeddings = new_embed_fn(results["documents"])
        
        # Add to new collection
        new_collection.add(
            ids=results["ids"],
            embeddings=new_embeddings,
            documents=results["documents"],
            metadatas=results["metadatas"]
        )
        
        offset += batch_size
        print(f"Migrated {offset} documents...")
    
    print(f"Migration complete. Delete old collection when ready.")
```

---

## Key Takeaways

1. **HNSW indexes degrade with mutations** — soft deletes accumulate, causing fragmentation
    
2. **Compaction cleans without full rebuild** — WAL pruning and vacuum reclaim space incrementally
    
3. **Rebuild when fragmentation is high** — fresh index is optimal, but expensive
    
4. **Monitor index health** — use `chromadb-ops` to track fragmentation levels
    
5. **Schedule maintenance windows** — rebuilds are resource-intensive, plan accordingly
    
6. **Embedding model changes require migration** — can't rebuild, must re-embed everything
    
7. **Always back up before maintenance** — operations can fail or corrupt data
    

---

Ready for the Day 4 Mini Challenge (building the `Indexer` class), or any questions on maintenance first?