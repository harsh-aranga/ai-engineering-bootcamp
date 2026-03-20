# Note 4: Embedding Model Migration — Blue-Green for Vector Indexes

## The Embedding Compatibility Problem

This is the most critical concept in embedding migration:

```python
# text-embedding-ada-002
embedding_ada = openai.embeddings.create(
    input="What is machine learning?",
    model="text-embedding-ada-002"
)
# Returns: [0.023, -0.041, 0.018, ...] (1536 dimensions)

# text-embedding-3-small
embedding_3small = openai.embeddings.create(
    input="What is machine learning?",
    model="text-embedding-3-small"
)
# Returns: [0.015, -0.033, 0.022, ...] (1536 dimensions)

# SAME dimensionality. COMPLETELY DIFFERENT vector spaces.
```

**Why they're incompatible:**

|Property|text-embedding-ada-002|text-embedding-3-small|
|---|---|---|
|Dimensions|1536|1536|
|Training data|Different|Different|
|Vector space|Space A|Space B|
|Cosine similarity between them|**Meaningless**|**Meaningless**|

The vectors exist in different mathematical spaces. Comparing them is like comparing GPS coordinates from two different map projections — the numbers look similar, but they don't mean the same thing.

**The practical problem:**

```python
# Your index was built with ada-002
index.add(document_embeddings)  # All ada-002 vectors

# User query comes in
query_embedding = embed(query, model="text-embedding-3-small")  # New model

# This search returns GARBAGE
results = index.search(query_embedding)  # Comparing apples to oranges
```

---

## Why Migrate Embedding Models?

Migration is painful, so you need a good reason. Here are the valid ones:

### 1. Better Models Released

```
text-embedding-ada-002 (2022):
  - MIRACL average: 31.4%
  - MTEB average: 61.0%

text-embedding-3-small (2024):
  - MIRACL average: 44.0% (+13 points)
  - MTEB average: 62.3% (+1.3 points)
  - 5× cheaper
```

Newer models often provide better retrieval quality, especially for multilingual content.

### 2. Cost Reduction

Current pricing (as of March 2026):

|Model|Price per 1M tokens|Relative Cost|
|---|---|---|
|text-embedding-ada-002|$0.10|5×|
|text-embedding-3-small|$0.02|1× (baseline)|
|text-embedding-3-large|$0.13|6.5×|

For a 10M document corpus at 500 tokens/doc:

- ada-002: 5B tokens × $0.10/1M = **$500**
- 3-small: 5B tokens × $0.02/1M = **$100**

Migration pays for itself if you reindex frequently.

### 3. Provider Change

Switching from OpenAI to Cohere, or to an open-source model like BGE:

```python
# Before: OpenAI
embedding = openai.embeddings.create(input=text, model="text-embedding-3-small")

# After: Cohere
embedding = cohere.embed(texts=[text], model="embed-english-v3.0")

# Different models, different spaces — must reindex
```

### 4. Dimension Reduction

Trade accuracy for speed and storage:

```python
# Full 1536 dimensions
embedding = openai.embeddings.create(
    input=text,
    model="text-embedding-3-small"
)  # 1536 floats × 4 bytes = 6KB per document

# Reduced to 512 dimensions (text-embedding-3 supports this)
embedding = openai.embeddings.create(
    input=text,
    model="text-embedding-3-small",
    dimensions=512  # Matryoshka representation learning
)  # 512 floats × 4 bytes = 2KB per document

# 3× less storage, faster search, slightly lower accuracy
```

---

## Migration is NOT Incremental

You cannot do this:

```python
# WRONG: Mixing old and new embeddings in same index
for new_doc in new_documents:
    embedding = embed(new_doc, model="text-embedding-3-small")  # New model
    index.add(embedding)  # Index has ada-002 vectors!
    
# Result: New docs won't be found by old queries,
#         old docs won't be found by new queries
```

**Embedding migration is all-or-nothing:**

- Every document must be re-embedded with the new model
- Every vector in the index must be from the same model
- The query embedding must use the same model as the index

This is why blue-green deployment matters — you need a complete parallel index.

---

## Blue-Green Deployment for Embeddings

The same pattern used for zero-downtime application deployments:

```
Phase 1: Current State
┌─────────────────────────────────────────────────────────────┐
│  Index: ada-002                                              │
│  ██████████████████████████████████████████████████████████ │
│  All traffic → ada-002 index                                │
│  Query embedding: ada-002                                    │
└─────────────────────────────────────────────────────────────┘

Phase 2: Build New Index (Parallel)
┌─────────────────────────────────────────────────────────────┐
│  Index: ada-002 (BLUE - Production)                         │
│  ██████████████████████████████████████████████████████████ │
│  All traffic still here                                      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Index: 3-small (GREEN - Building)                          │
│  ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│  Reindexing in progress... 35% complete                      │
└─────────────────────────────────────────────────────────────┘

Phase 3: Test New Index
┌─────────────────────────────────────────────────────────────┐
│  Index: ada-002 (BLUE - Production)                         │
│  All traffic still here                                      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Index: 3-small (GREEN - Testing)                           │
│  ██████████████████████████████████████████████████████████ │
│  Running evaluation suite...                                 │
│  Recall@10: 0.92 (was 0.89 with ada-002) ✓                  │
└─────────────────────────────────────────────────────────────┘

Phase 4: Switch Traffic
┌─────────────────────────────────────────────────────────────┐
│  Index: ada-002 (BLUE - Standby)                            │
│  Kept for rollback                                           │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Index: 3-small (GREEN - Production)                        │
│  ██████████████████████████████████████████████████████████ │
│  All traffic → 3-small index                                │
│  Query embedding: 3-small                                    │
└─────────────────────────────────────────────────────────────┘

Phase 5: Delete Old Index (After Confidence)
┌─────────────────────────────────────────────────────────────┐
│  Index: 3-small (Production)                                │
│  ██████████████████████████████████████████████████████████ │
│  ada-002 index deleted after 14-day rollback period         │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation: Reindexing Process

```python
# reindex.py

import os
import time
from dataclasses import dataclass
from typing import Iterator, List, Optional
import logging
from tqdm import tqdm

logger = logging.getLogger(__name__)


@dataclass
class ReindexConfig:
    """Configuration for reindexing job."""
    source_collection: str      # Where documents live
    target_index_name: str      # New index name
    embedding_model: str        # e.g., "text-embedding-3-small"
    batch_size: int = 100       # Documents per batch
    rate_limit_delay: float = 0.1  # Seconds between batches
    checkpoint_every: int = 1000   # Save progress every N docs


@dataclass
class ReindexProgress:
    """Track reindexing progress for resume capability."""
    total_documents: int
    processed_documents: int
    last_document_id: Optional[str]
    started_at: float
    
    @property
    def percent_complete(self) -> float:
        if self.total_documents == 0:
            return 100.0
        return (self.processed_documents / self.total_documents) * 100
    
    @property
    def estimated_remaining_seconds(self) -> float:
        if self.processed_documents == 0:
            return float('inf')
        elapsed = time.time() - self.started_at
        rate = self.processed_documents / elapsed
        remaining = self.total_documents - self.processed_documents
        return remaining / rate


class EmbeddingReindexer:
    """
    Reindex documents with a new embedding model.
    
    Features:
    - Batch processing with rate limiting
    - Progress tracking and checkpointing
    - Resume capability after interruption
    - Parallel index building (doesn't affect production)
    """
    
    def __init__(
        self,
        document_store,      # Your document storage
        vector_store,        # Your vector store (ChromaDB, Pinecone, etc.)
        embedding_client,    # Your embedding client
        config: ReindexConfig,
    ):
        self.document_store = document_store
        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.config = config
        
        self._progress: Optional[ReindexProgress] = None
    
    def run(self, resume_from: Optional[str] = None) -> ReindexProgress:
        """
        Run the reindexing job.
        
        Args:
            resume_from: Document ID to resume from (for interrupted jobs)
        
        Returns:
            Final progress state
        """
        # Count total documents
        total_docs = self.document_store.count(self.config.source_collection)
        
        self._progress = ReindexProgress(
            total_documents=total_docs,
            processed_documents=0,
            last_document_id=resume_from,
            started_at=time.time(),
        )
        
        logger.info(
            f"Starting reindex: {total_docs} documents, "
            f"model={self.config.embedding_model}"
        )
        
        # Create new index (doesn't affect existing index)
        self.vector_store.create_index(
            name=self.config.target_index_name,
            dimension=self._get_embedding_dimension(),
        )
        
        # Process in batches
        for batch in tqdm(
            self._document_batches(resume_from),
            total=total_docs // self.config.batch_size,
            desc="Reindexing",
        ):
            self._process_batch(batch)
            
            # Rate limiting
            time.sleep(self.config.rate_limit_delay)
            
            # Checkpoint
            if self._progress.processed_documents % self.config.checkpoint_every == 0:
                self._save_checkpoint()
        
        logger.info(
            f"Reindex complete: {self._progress.processed_documents} documents "
            f"in {time.time() - self._progress.started_at:.1f}s"
        )
        
        return self._progress
    
    def _document_batches(
        self,
        start_after: Optional[str] = None,
    ) -> Iterator[List[dict]]:
        """Yield batches of documents."""
        cursor = start_after
        
        while True:
            batch = self.document_store.get_batch(
                collection=self.config.source_collection,
                limit=self.config.batch_size,
                after=cursor,
            )
            
            if not batch:
                break
            
            yield batch
            cursor = batch[-1]["id"]
    
    def _process_batch(self, documents: List[dict]) -> None:
        """Embed and index a batch of documents."""
        # Extract text content
        texts = [doc["content"] for doc in documents]
        doc_ids = [doc["id"] for doc in documents]
        
        # Generate embeddings
        embeddings = self.embedding_client.embed_batch(
            texts=texts,
            model=self.config.embedding_model,
        )
        
        # Add to new index
        self.vector_store.add(
            index_name=self.config.target_index_name,
            ids=doc_ids,
            embeddings=embeddings,
            metadata=[doc.get("metadata", {}) for doc in documents],
        )
        
        # Update progress
        self._progress.processed_documents += len(documents)
        self._progress.last_document_id = doc_ids[-1]
    
    def _get_embedding_dimension(self) -> int:
        """Get dimension for the embedding model."""
        # Could also call API to check, but these are well-known
        dimensions = {
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
        }
        return dimensions.get(self.config.embedding_model, 1536)
    
    def _save_checkpoint(self) -> None:
        """Save progress for resume capability."""
        checkpoint = {
            "processed": self._progress.processed_documents,
            "last_id": self._progress.last_document_id,
            "target_index": self.config.target_index_name,
        }
        # Save to file or database
        logger.debug(f"Checkpoint: {checkpoint}")
```

**Usage:**

```python
config = ReindexConfig(
    source_collection="documents",
    target_index_name="documents_3small_v1",  # New index
    embedding_model="text-embedding-3-small",
    batch_size=100,
)

reindexer = EmbeddingReindexer(
    document_store=document_store,
    vector_store=vector_store,
    embedding_client=embedding_client,
    config=config,
)

# Run reindexing (can take hours for large corpora)
progress = reindexer.run()

# Or resume from checkpoint
progress = reindexer.run(resume_from="doc_50000")
```

---

## Testing the New Index

Before switching traffic, validate the new index:

```python
# test_new_index.py

from dataclasses import dataclass
from typing import List, Dict
import json


@dataclass
class RetrievalTestCase:
    """A test case for retrieval evaluation."""
    query: str
    relevant_doc_ids: List[str]  # Ground truth


def evaluate_index(
    index_name: str,
    embedding_model: str,
    test_cases: List[RetrievalTestCase],
    k_values: List[int] = [1, 5, 10],
) -> Dict[str, float]:
    """
    Evaluate retrieval quality on the new index.
    
    Returns metrics: Recall@K, MRR, Hit Rate
    """
    results = {f"recall@{k}": 0.0 for k in k_values}
    results["mrr"] = 0.0
    results["hit_rate"] = 0.0
    
    for test_case in test_cases:
        # Query the index with new embedding model
        query_embedding = embed(test_case.query, model=embedding_model)
        
        retrieved = vector_store.search(
            index_name=index_name,
            query_vector=query_embedding,
            top_k=max(k_values),
        )
        
        retrieved_ids = [r["id"] for r in retrieved]
        relevant_set = set(test_case.relevant_doc_ids)
        
        # Calculate Recall@K for each K
        for k in k_values:
            retrieved_at_k = set(retrieved_ids[:k])
            recall = len(retrieved_at_k & relevant_set) / len(relevant_set)
            results[f"recall@{k}"] += recall
        
        # Calculate MRR (Mean Reciprocal Rank)
        for rank, doc_id in enumerate(retrieved_ids, 1):
            if doc_id in relevant_set:
                results["mrr"] += 1.0 / rank
                break
        
        # Hit Rate (at least one relevant in top K)
        if relevant_set & set(retrieved_ids[:k_values[-1]]):
            results["hit_rate"] += 1
    
    # Average across test cases
    n = len(test_cases)
    for key in results:
        results[key] /= n
    
    return results


def compare_indexes(
    old_index: str,
    old_model: str,
    new_index: str,
    new_model: str,
    test_cases: List[RetrievalTestCase],
) -> Dict[str, Dict[str, float]]:
    """
    Compare retrieval quality between old and new index.
    
    Returns metrics for both, plus delta.
    """
    old_metrics = evaluate_index(old_index, old_model, test_cases)
    new_metrics = evaluate_index(new_index, new_model, test_cases)
    
    delta = {
        key: new_metrics[key] - old_metrics[key]
        for key in old_metrics
    }
    
    return {
        "old": old_metrics,
        "new": new_metrics,
        "delta": delta,
    }


# Example usage
test_cases = [
    RetrievalTestCase(
        query="How do I reset my password?",
        relevant_doc_ids=["doc_123", "doc_456"],
    ),
    RetrievalTestCase(
        query="What are the pricing plans?",
        relevant_doc_ids=["doc_789"],
    ),
    # ... more test cases
]

comparison = compare_indexes(
    old_index="documents_ada002",
    old_model="text-embedding-ada-002",
    new_index="documents_3small_v1",
    new_model="text-embedding-3-small",
    test_cases=test_cases,
)

print(json.dumps(comparison, indent=2))
# {
#   "old": {"recall@10": 0.85, "mrr": 0.72, "hit_rate": 0.91},
#   "new": {"recall@10": 0.89, "mrr": 0.78, "hit_rate": 0.94},
#   "delta": {"recall@10": 0.04, "mrr": 0.06, "hit_rate": 0.03}
# }

# Decision: New index is better, proceed with switch
```

**Also do manual spot checks:**

```python
def manual_spot_check(
    new_index: str,
    new_model: str,
    queries: List[str],
):
    """Print results for manual review."""
    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        
        embedding = embed(query, model=new_model)
        results = vector_store.search(
            index_name=new_index,
            query_vector=embedding,
            top_k=5,
        )
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. [Score: {result['score']:.3f}]")
            print(f"   {result['content'][:200]}...")

# Check edge cases, common queries, known problem queries
manual_spot_check(
    new_index="documents_3small_v1",
    new_model="text-embedding-3-small",
    queries=[
        "password reset",
        "billing dispute",
        "API rate limits",
        "cancel subscription",  # Known problem query with old model
    ],
)
```

---

## The Switch: Configuration-Based

Your application code should already be abstracted:

```python
# config/retrieval.yaml
retrieval:
  index_name: documents_ada002        # Change this to switch
  embedding_model: text-embedding-ada-002
  top_k: 10
```

**The switch is just a config change:**

```python
# config/retrieval.yaml (after switch)
retrieval:
  index_name: documents_3small_v1     # New index
  embedding_model: text-embedding-3-small  # Must match!
  top_k: 10
```

**Your retrieval code doesn't change:**

```python
# retriever.py

class Retriever:
    def __init__(self, config: RetrievalConfig):
        self.index_name = config.index_name
        self.embedding_model = config.embedding_model
        self.top_k = config.top_k
    
    def retrieve(self, query: str) -> List[Document]:
        # Embedding model comes from config
        query_embedding = embed(query, model=self.embedding_model)
        
        # Index name comes from config
        results = vector_store.search(
            index_name=self.index_name,
            query_vector=query_embedding,
            top_k=self.top_k,
        )
        
        return results
```

**Switch options:**

1. **Config file change + deployment** — safest, clear audit trail
2. **Environment variable override** — faster, no deployment needed
3. **Feature flag** — gradual rollout possible

```bash
# Option 2: Environment override
export RETRIEVAL_INDEX_NAME=documents_3small_v1
export RETRIEVAL_EMBEDDING_MODEL=text-embedding-3-small
```

---

## Rollback Capability

**The golden rule:** Don't delete the old index until you're confident.

```python
# rollback.py

class IndexRollbackManager:
    """
    Manage rollback capability for index migrations.
    
    Keeps old index running (read-only) for rollback period.
    """
    
    def __init__(
        self,
        vector_store,
        rollback_period_days: int = 14,
    ):
        self.vector_store = vector_store
        self.rollback_period_days = rollback_period_days
        self._migration_log = []
    
    def record_migration(
        self,
        old_index: str,
        new_index: str,
        old_model: str,
        new_model: str,
    ):
        """Record a migration for potential rollback."""
        self._migration_log.append({
            "timestamp": time.time(),
            "old_index": old_index,
            "new_index": new_index,
            "old_model": old_model,
            "new_model": new_model,
            "status": "active",
        })
        
        # Mark old index as standby (not deleted)
        self.vector_store.set_index_metadata(
            old_index,
            {"status": "standby", "standby_until": time.time() + (86400 * self.rollback_period_days)}
        )
    
    def rollback(self) -> dict:
        """
        Rollback to previous index.
        
        Returns the rollback configuration to apply.
        """
        if not self._migration_log:
            raise ValueError("No migrations to rollback")
        
        last_migration = self._migration_log[-1]
        
        if last_migration["status"] == "rolled_back":
            raise ValueError("Already rolled back")
        
        # Check old index still exists
        old_index = last_migration["old_index"]
        if not self.vector_store.index_exists(old_index):
            raise ValueError(f"Cannot rollback: {old_index} has been deleted")
        
        last_migration["status"] = "rolled_back"
        
        return {
            "index_name": last_migration["old_index"],
            "embedding_model": last_migration["old_model"],
            "action": "Update config to these values",
        }
    
    def cleanup_old_indexes(self):
        """Delete old indexes past their rollback period."""
        now = time.time()
        
        for migration in self._migration_log:
            if migration["status"] != "active":
                continue
            
            old_index = migration["old_index"]
            metadata = self.vector_store.get_index_metadata(old_index)
            
            if metadata.get("standby_until", float("inf")) < now:
                # Past rollback period, safe to delete
                self.vector_store.delete_index(old_index)
                migration["status"] = "cleaned_up"
                logger.info(f"Deleted old index: {old_index}")
```

**Rollback procedure:**

```python
# If new index has problems

# 1. Check old index is still available
manager = IndexRollbackManager(vector_store)
rollback_config = manager.rollback()

# 2. Update configuration
# Either: update config file and deploy
# Or: set environment variables
os.environ["RETRIEVAL_INDEX_NAME"] = rollback_config["index_name"]
os.environ["RETRIEVAL_EMBEDDING_MODEL"] = rollback_config["embedding_model"]

# 3. Traffic immediately goes back to old index
```

---

## Cost and Time Estimation

Before starting a migration, estimate the impact:

```python
# estimate_migration.py

from dataclasses import dataclass


@dataclass
class MigrationEstimate:
    """Estimated cost and time for embedding migration."""
    
    total_documents: int
    avg_tokens_per_doc: int
    
    # Embedding costs
    old_model_price_per_1m: float  # e.g., $0.10 for ada-002
    new_model_price_per_1m: float  # e.g., $0.02 for 3-small
    
    # Processing constraints
    embedding_batch_size: int = 100
    api_rate_limit_rpm: int = 3000  # Requests per minute
    
    @property
    def total_tokens(self) -> int:
        return self.total_documents * self.avg_tokens_per_doc
    
    @property
    def embedding_cost(self) -> float:
        """Cost to generate all new embeddings."""
        return (self.total_tokens / 1_000_000) * self.new_model_price_per_1m
    
    @property
    def monthly_savings(self) -> float:
        """Monthly savings after migration (assuming monthly reindex)."""
        old_cost = (self.total_tokens / 1_000_000) * self.old_model_price_per_1m
        new_cost = (self.total_tokens / 1_000_000) * self.new_model_price_per_1m
        return old_cost - new_cost
    
    @property
    def reindex_time_hours(self) -> float:
        """Estimated time to reindex all documents."""
        total_batches = self.total_documents / self.embedding_batch_size
        batches_per_minute = self.api_rate_limit_rpm / self.embedding_batch_size
        minutes = total_batches / batches_per_minute
        return minutes / 60
    
    @property
    def storage_during_migration(self) -> str:
        """Storage requirement during migration (2x normal)."""
        # Rough estimate: 4 bytes per float, 1536 dimensions
        bytes_per_doc = 1536 * 4
        total_gb = (self.total_documents * bytes_per_doc * 2) / (1024**3)
        return f"{total_gb:.2f} GB"
    
    def summary(self) -> str:
        return f"""
Migration Estimate
==================
Documents: {self.total_documents:,}
Tokens: {self.total_tokens:,}

Costs:
  Embedding generation: ${self.embedding_cost:.2f}
  Monthly savings: ${self.monthly_savings:.2f}
  Payback period: {self.embedding_cost / self.monthly_savings:.1f} months

Time:
  Estimated reindex time: {self.reindex_time_hours:.1f} hours

Storage:
  During migration: {self.storage_during_migration} (2x normal)
"""


# Example: 1 million documents
estimate = MigrationEstimate(
    total_documents=1_000_000,
    avg_tokens_per_doc=500,
    old_model_price_per_1m=0.10,  # ada-002
    new_model_price_per_1m=0.02,  # 3-small
)

print(estimate.summary())
```

**Output:**

```
Migration Estimate
==================
Documents: 1,000,000
Tokens: 500,000,000

Costs:
  Embedding generation: $10.00
  Monthly savings: $40.00
  Payback period: 0.3 months

Time:
  Estimated reindex time: 5.6 hours

Storage:
  During migration: 11.44 GB (2x normal)
```

**Key considerations:**

|Factor|Impact|
|---|---|
|**Corpus size**|Linear scaling — 10M docs = 10× time and cost|
|**API rate limits**|Bottleneck for large corpora; consider batch API|
|**Token count**|Longer documents = higher embedding cost|
|**Storage**|2× during migration (both indexes live)|
|**Downtime**|Zero with blue-green; testing happens on parallel index|

---

## Complete Migration Checklist

```markdown
## Pre-Migration
- [ ] Estimate cost and time (use MigrationEstimate)
- [ ] Verify storage capacity for 2× index size
- [ ] Prepare test cases for retrieval evaluation
- [ ] Confirm rollback period (14 days recommended)
- [ ] Schedule migration during low-traffic period (for reindexing load)

## Reindexing Phase
- [ ] Create new index with appropriate name (e.g., `docs_3small_v1`)
- [ ] Start reindexing job
- [ ] Monitor progress and API rate limits
- [ ] Verify checkpointing works (test resume)
- [ ] Wait for completion

## Testing Phase
- [ ] Run retrieval evaluation suite
- [ ] Compare metrics: old vs new index
- [ ] Manual spot checks on edge cases
- [ ] Verify no regression on known problem queries
- [ ] Document results

## Switch Phase
- [ ] Update configuration (index_name + embedding_model)
- [ ] Deploy or reload config
- [ ] Verify traffic is hitting new index
- [ ] Monitor retrieval quality metrics
- [ ] Monitor error rates

## Post-Switch
- [ ] Mark old index as standby (not deleted)
- [ ] Set calendar reminder for rollback period end
- [ ] Monitor for issues during rollback period
- [ ] After rollback period: delete old index
- [ ] Document migration in runbook
```

---

## Summary

|Concept|Key Point|
|---|---|
|**Incompatibility**|Same dimensions ≠ compatible; different vector spaces|
|**All-or-nothing**|Can't mix embedding models in same index|
|**Blue-green**|Build new index in parallel, switch traffic, keep old for rollback|
|**Testing**|Run eval suite before switching; compare Recall@K, MRR|
|**Switch**|Configuration change, not code change|
|**Rollback**|Keep old index for 14+ days; instant rollback via config|
|**Cost**|Calculate before starting; payback period matters|

**The key insight:** Embedding migration is a deployment problem, not a code problem. Build infrastructure that lets you switch indexes via configuration, test before switching, and rollback instantly if needed.

---

## What's Next

- **Note 5:** A/B Testing and Shadow Mode — safely testing new models in production