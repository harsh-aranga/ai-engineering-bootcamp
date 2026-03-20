# Collections/Indexes: Organizing Vectors into Logical Groups

## The Core Concept

A **collection** is to a vector database what a **table** is to a relational database — a logical container for related vectors.

```
Vector Database
├── Collection: "support_tickets"
│   ├── vectors from support docs
│   └── embedding model: text-embedding-3-small
│
├── Collection: "product_catalog"
│   ├── vectors from product descriptions
│   └── embedding model: text-embedding-3-small
│
└── Collection: "image_search"
    ├── vectors from product images
    └── embedding model: clip-vit-base
```

---

## Why Separate Collections?

### 1. Different Embedding Models = Different Collections

This is the hard rule. Vectors from different embedding models **cannot** be compared meaningfully — their dimensions represent different things.

```python
# These produce incompatible vectors
openai_vec = openai.embed("red sneakers")      # 1536 dims, trained on text
clip_vec = clip.embed(sneaker_image)            # 512 dims, trained on images

# Cosine similarity between them is meaningless
```

Even same-dimensionality models trained differently aren't comparable. Keep them separate.

### 2. Different Domains = Easier Management

```python
# Separate by domain
support_collection = client.get_or_create_collection("support_docs")
legal_collection = client.get_or_create_collection("legal_contracts")

# vs. one giant collection with metadata filtering
# (works, but harder to manage, version, delete)
```

Separate collections let you:

- Delete/rebuild one domain without touching others
- Apply different HNSW parameters per use case
- Track storage/costs per domain

### 3. Access Control

Some vector databases support collection-level permissions. Easier than row-level metadata filtering for multi-tenant systems.

---

## ChromaDB Collection Basics

```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

# Create with specific settings
collection = client.create_collection(
    name="support_docs",
    metadata={
        "hnsw:space": "cosine",          # Distance metric
        "hnsw:M": 16,                     # HNSW connections per node
        "description": "Customer support documentation"
    },
    embedding_function=my_embedding_fn    # Tied to this collection
)

# Get existing
collection = client.get_collection("support_docs")

# Get or create (idempotent)
collection = client.get_or_create_collection("support_docs")

# List all
client.list_collections()

# Delete
client.delete_collection("support_docs")
```

---

## Collection vs Index: Terminology

Different vector databases use different terms:

|Database|"Table" Equivalent|Notes|
|---|---|---|
|ChromaDB|Collection|Contains vectors + documents + metadata|
|Pinecone|Index|One index per "project," namespaces within|
|Qdrant|Collection|Similar to ChromaDB|
|Weaviate|Class|Schema-based, more structured|
|pgvector|Table + Index|Regular Postgres table with HNSW/IVF index on vector column|

**Pinecone quirk:** Pinecone uses "namespaces" within an index for logical separation, rather than multiple indexes. Namespaces share the same embedding dimension but can be queried/deleted independently.

```python
# Pinecone namespaces (conceptually similar to collections)
index.upsert(vectors=[...], namespace="support_docs")
index.upsert(vectors=[...], namespace="legal_docs")

# Query specific namespace
index.query(vector=[...], namespace="support_docs", top_k=5)
```

---

## Practical Guidelines

|Scenario|Recommendation|
|---|---|
|Different embedding models|Separate collections (mandatory)|
|Same model, different domains|Separate collections (cleaner)|
|Same model, same domain, multi-tenant|Metadata filtering OR namespaces|
|Need different HNSW params|Separate collections|
|Want to A/B test retrieval|Separate collections|

---

## What Gets Configured at Collection Level

In ChromaDB, these are set at creation and can't change:

- **Embedding dimensionality** — locked after first vector added
- **Distance metric** — cosine, L2, or inner product
- **HNSW parameters** — M, ef_construction

These can be updated:

- **Collection name** — `collection.modify(name="new_name")`
- **Collection metadata** — `collection.modify(metadata={...})`

---

## Summary

Collections are just logical buckets. The key rules:

1. **One embedding model per collection** — non-negotiable
2. **Dimensionality locked at first insert** — can't mix 1536-dim and 3072-dim
3. **Distance metric chosen upfront** — cosine vs L2 vs dot product
4. **Use multiple collections** when domains are distinct or you need different configs

Don't overthink it — if you'd put it in a separate database table, put it in a separate collection.