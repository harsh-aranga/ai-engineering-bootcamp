# Embeddings Storage: Vectors + Metadata

## What Actually Gets Stored

A vector database doesn't just store vectors — it stores **records** with multiple components:

```
┌─────────────────────────────────────────────────────────────┐
│  RECORD                                                     │
├─────────────────────────────────────────────────────────────┤
│  id:        "chunk_42"                                      │
│  embedding: [0.023, -0.156, 0.891, ..., 0.042]  (1536 dims)│
│  document:  "The quarterly revenue increased by 15%..."     │
│  metadata:  {"source": "q3_report.pdf", "page": 7, ...}     │
└─────────────────────────────────────────────────────────────┘
```

Each component serves a purpose:

|Component|Required?|Purpose|
|---|---|---|
|`id`|Yes|Unique identifier — for updates, deletes, deduplication|
|`embedding`|Yes|The vector — what gets searched|
|`document`|Optional|Original text — returned with results so you don't need a separate lookup|
|`metadata`|Optional|Structured fields — for filtering, context, traceability|

---

## The ChromaDB Mental Model

A collection is the object that stores your embedded documents along with any associated metadata. If you're familiar with relational databases, then you can think of a collection as a table.

```python
collection.add(
    ids=["doc1", "doc2"],
    documents=["This is document1", "This is document2"],
    metadatas=[{"source": "notion"}, {"source": "google-docs"}]
)
```

ChromaDB handles tokenization, embedding, and indexing automatically. You can skip that and add your own embeddings as well.

Two modes of operation:

1. **Pass documents** → ChromaDB embeds them using the collection's embedding function
2. **Pass embeddings directly** → You control embedding, ChromaDB just stores and indexes

---

## Why Metadata Matters (The Real Power)

Vectors enable similarity search. Metadata enables **precision**.

The metadatas argument is optional, but most of the time, it's useful to store metadata with your embeddings. When you query a document, metadata provides you with additional information that can be helpful to better understand the document's contents. You can also filter on metadata fields, just like you would in a relational database query.

### Common Metadata Patterns

**Source tracking:**

```python
{"source": "q3_report.pdf", "page": 7, "chunk_index": 3}
```

→ When results come back, you know exactly where they came from

**Temporal filtering:**

```python
{"created_at": "2024-01-15", "version": "2.1"}
```

→ "Find similar documents, but only from 2024"

**Access control:**

```python
{"department": "engineering", "classification": "internal"}
```

→ Filter results by who should see them

**Content type:**

```python
{"doc_type": "faq", "language": "en"}
```

→ Different retrieval strategies for different content

### Query with Metadata Filter

```python
results = collection.query(
    query_texts=["quarterly revenue growth"],
    n_results=5,
    where={"source": "q3_report.pdf"}  # Vector search + metadata filter
)
```

This is **hybrid filtering**: find the most similar vectors, but only among those matching the metadata constraint.

---

## What Gets Returned

Column values are aligned by index. For query(), ids[q][k] is the k-th match for query q, and aligns with documents[q][k], metadatas[q][k], and distances[q][k] (if included).

```python
results = collection.query(query_texts=["revenue growth"], n_results=2)

# results structure:
{
    'ids': [['doc1', 'doc2']],
    'documents': [['First doc text...', 'Second doc text...']],
    'metadatas': [[{'source': 'q3.pdf'}, {'source': 'q2.pdf'}]],
    'distances': [[0.23, 0.41]]  # Lower = more similar (for L2/cosine)
}
```

When using get or query you can use the include parameter to specify which data you want returned — any of embeddings, documents, metadatas.

---

## Document Storage: Store or Not?

Chroma allows users to store both embeddings and documents, alongside metadata, in collections. Documents and metadata are both optional and depending on your use case you may choose to store them in Chroma or externally, or not at all.

**Store documents in ChromaDB:**

- Simpler architecture — everything in one place
- Allows you to do keyword searches on the documents

**Store documents externally (S3, Postgres, etc.):**

- The database can grow substantially in size because documents are effectively duplicated
- Separation of concerns — vectors for search, documents in document store
- Better for large documents or complex access patterns

**Hybrid approach:** Store just enough in metadata to identify the document, fetch full content from elsewhere:

```python
collection.add(
    ids=["chunk_42"],
    embeddings=[[0.1, 0.2, ...]],
    metadatas=[{"doc_id": "report_123", "chunk_index": 5}]
    # No document stored — look it up by doc_id when needed
)
```

---

## Dimensionality Lock-In

When creating a collection, its dimensionality is determined by the dimensionality of the first embedding added to it. Once the dimensionality is set, it cannot be changed.

```python
collection.add(ids=["id1"], embeddings=[[1, 2, 3]])  # Dimensionality = 3
collection.add(ids=["id2"], embeddings=[[1, 2, 3, 4]])  # ERROR — dimension mismatch
```

**Implication:** If you switch embedding models (say, from 1536-dim to 3072-dim), you need a new collection. You can't mix embeddings from different models in the same collection — and even if you could, the similarity scores would be meaningless.

---

## IDs: Your Deduplication and Update Mechanism

Each document must have a unique associated id. Trying to .add the same ID twice will result in only the initial value being stored.

IDs serve multiple purposes:

1. **Deduplication** — same ID = same record
2. **Updates** — `collection.update(ids=["doc1"], documents=["new content"])`
3. **Deletes** — `collection.delete(ids=["doc1"])`
4. **Correlation** — link back to your source system

Good ID patterns:

```python
# Content-based (deduplication built-in)
id = hashlib.md5(chunk_text.encode()).hexdigest()

# Source-based (traceable)
id = f"{filename}_{page}_{chunk_index}"

# UUID (guaranteed unique, less meaningful)
id = str(uuid.uuid4())
```

---

## Metadata Type Constraints

Metadata is a dictionary of key-value pairs. Keys can be strings, values can be strings, integers, floats, or booleans.

No nested objects. No arrays. If you need complex structure, serialize to JSON string:

```python
# Won't work
metadata = {"tags": ["finance", "q3"]}

# Workaround
metadata = {"tags": '["finance", "q3"]'}  # JSON string, parse on retrieval
```

---

## Summary: The Storage Model

Vector databases store **records**, not just vectors:

|What|Why|
|---|---|
|**Vector**|Enables similarity search|
|**ID**|Enables CRUD operations, deduplication|
|**Document**|Avoids separate lookup, enables keyword search|
|**Metadata**|Enables filtering, provides context, supports access control|

The metadata is where production systems get sophisticated — date filters, source tracking, user scoping, version management. Vectors find similar things; metadata narrows down _which_ similar things you actually want.