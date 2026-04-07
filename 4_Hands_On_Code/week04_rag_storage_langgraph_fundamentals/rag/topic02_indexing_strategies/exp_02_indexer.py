"""
This script corresponds to Day 3-4->Day 2->Experiments->
Build an Indexer class:
Success Criteria:

Generates deterministic IDs (same content = same ID)
Batches embedding calls (doesn't call API once per chunk)
Handles duplicates via upsert (no duplicate entries)
delete_by_source removes all chunks with matching source metadata
reindex_source atomically replaces old with new
Returns useful stats (how many indexed, skipped, errored)
Handles API errors gracefully (doesn't crash on rate limit)
Tested with 50+ chunks from your Week 3 document processor
"""

import hashlib
import json
from typing import Any

import chromadb
from chromadb import GetResult
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction, EmbeddingFunction, \
    SentenceTransformerEmbeddingFunction

from common.config import get_config
from common.logger import get_logger

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")

client = chromadb.PersistentClient(path="./chroma-db")

documents = [
    "Kafka uses a commit log architecture where messages are appended sequentially to partitions, enabling high throughput and replay capability.",
    "Circuit breakers prevent cascading failures by failing fast when a downstream service is unhealthy, allowing the system to degrade gracefully.",
    "Consistent hashing minimizes key redistribution when nodes join or leave a cluster, making it ideal for distributed caches like Redis Cluster.",
    "The CAP theorem states that a distributed system can only guarantee two of three properties: consistency, availability, and partition tolerance.",
    "Event sourcing stores state changes as a sequence of events rather than current state, enabling full audit trails and temporal queries."
]

metadatas = [
    {"source": "kafka-docs", "category": "messaging"},
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "system-design", "category": "partitioning"},
    {"source": "distributed-theory", "category": "fundamentals"},
    {"source": "event-driven-arch", "category": "patterns"}
]


def get_id_for_documents(doc_for_hash: str, metadata_for_hash: dict) -> str:
    """
    Generate ids for document and metadata passed by deterministic hashing
    :param metadata_for_hash:
    :param doc_for_hash:
    :return:
    """
    return hashlib.sha256(
        f"{doc_for_hash} {json.dumps(metadata_for_hash, sort_keys=True)}".encode("utf-8")
    ).hexdigest()


class Indexer:
    def __init__(
            self,
            collection_name: str,
            embedding_model: str = "text-embedding-3-small",
            batch_size: int = 100
    ):
        """
        Handles indexing of document chunks into vector store.
        """
        self._batch_size = batch_size
        openai_embedding_function = OpenAIEmbeddingFunction(api_key=open_ai_key, model_name=embedding_model)
        self._collection = client.get_or_create_collection(name=collection_name, embedding_function=openai_embedding_function)


    def index_chunks(self, chunks: list[dict]) -> dict:
        """
        Index chunks with deduplication.

        Args:
            chunks: List of {"content": str, "metadata": dict}

        Returns:
            {"indexed": int, "skipped_duplicates": int, "errors": int}
        """
        indexed = 0
        skipped_duplicates = 0
        errors = 0
        curr_batch = 0

        seen_ids = set()
        list_of_ids = []
        list_of_docs = []
        list_of_metadata = []

        for item in chunks:
            chunk_content = item.get("content")
            chunk_metadata = item.get("metadata")
            hash_id_of_doc = get_id_for_documents(chunk_content, chunk_metadata)
            if hash_id_of_doc in seen_ids:
                skipped_duplicates += 1
            else:
                seen_ids.add(hash_id_of_doc)
                list_of_ids.append(hash_id_of_doc)
                list_of_docs.append(chunk_content)
                list_of_metadata.append(chunk_metadata)
                curr_batch += 1

            if curr_batch >= self._batch_size:
                try:
                    self._collection.add(ids=list_of_ids, documents=list_of_docs, metadatas=list_of_metadata)
                    indexed += curr_batch
                except Exception as e:
                    logger.exception(f"Exception adding docs to chroma")
                    errors += curr_batch
                list_of_ids.clear()
                list_of_docs.clear()
                list_of_metadata.clear()
                curr_batch = 0

        if curr_batch > 0:
            try:
                self._collection.add(ids=list_of_ids, documents=list_of_docs, metadatas=list_of_metadata)
                indexed += curr_batch
            except Exception as e:
                logger.exception(f"Exception adding docs to chroma")
                errors += curr_batch

        result = {
            "indexed": indexed,
            "skipped_duplicates": skipped_duplicates,
            "errors": errors
        }

        return result

    def delete_by_source(self, source: str) -> int:
        """Delete all chunks from a specific source file."""
        delete_result = self._collection.delete(where={"source": source})
        return delete_result.get("deleted", 0)

    def reindex_source(self, source: str, chunks: list[dict]) -> dict:
        """Delete old chunks from source and index new ones."""
        deleted_count = self.delete_by_source(source)
        index_result = self.index_chunks(chunks)

        return_value = {
            "deleted": deleted_count,
            **index_result
        }

        return return_value

    def get_docs(self) -> GetResult:
        return self._collection.get(include=["documents", "metadatas"])


if __name__ == "__main__":
    list_input = []
    for cont, md in zip(documents, metadatas):
        list_input.append({
            "content": cont,
            "metadata": md
        })

    indexer = Indexer(collection_name="bootcamp-indexer-collection")
    logger.info(f"Indexing Results: {indexer.index_chunks(list_input)}")

    count_deleted = indexer.delete_by_source("kafka-docs")
    logger.info(f"Deletion Results: {count_deleted}")

    reindexing_results = indexer.reindex_source("resilience-patterns", [{
        "content": "Circuit breakers prevent cascading failures by failing fast when a downstream service is unhealthy, allowing the system to degrade gracefully.",
        "metadata": {"source": "resilience-patterns", "category": "fault-tolerance"}}
    ])

    logger.info(f"Reindexing results: {reindexing_results}")

    final_result = indexer.get_docs()

    result_list = [
        f"{doc_id} -> {doc} -> {metd}"
        for doc_id, doc, metd in zip(final_result["ids"], final_result["documents"], final_result["metadatas"])
    ]

    logger.info("Final result \n%s", "\n".join(result_list))