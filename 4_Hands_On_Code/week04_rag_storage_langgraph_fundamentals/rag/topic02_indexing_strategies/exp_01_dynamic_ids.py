"""
This script corresponds to Day 3-4->Day 1->Experiments->
Create a function that generates deterministic IDs from content (hash-based)
Add 5 chunks, note their IDs
Add the same 5 chunks again — verify no duplicates (upsert behavior)
Update one chunk's content — verify the change reflects in queries
"""
import hashlib
import json
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction, EmbeddingFunction, \
    SentenceTransformerEmbeddingFunction

from common.logger import get_logger

logger = get_logger(__file__)

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


def create_chroma_collection(name: str, embedding_function:EmbeddingFunction | None = None) -> Collection:
    """
    namesake with passed embedding function
    :param name:
    :param embedding_function:
    :return:
    """
    return client.get_or_create_collection(name=name, embedding_function=embedding_function)


def add_documents_to_chroma_store(docs:list[str], metadata_list:list[dict[str, Any]], doc_ids:list[str], collection:Collection) -> None:
    """
    Namesake
    :param collection:
    :param docs:
    :param metadata_list:
    :param doc_ids:
    :return:
    """
    collection.add(documents=docs, ids=doc_ids, metadatas=metadata_list)


def query_chroma_store(query_texts:list[str], collection:Collection, n_results:int = 1,
                       where:dict[str, Any] | None = None,
                       where_document:dict[str, Any] | None = None) -> None:
    """
    namesake
    :param collection:
    :param query_texts:
    :param n_results:
    :param where:
    :param where_document:
    :return:
    """
    results = collection.query(
        query_texts=query_texts,
        n_results=n_results,
        where=where,
        where_document=where_document
    )

    logger.info(f"Results for\n Query: <<{query_texts}>> \n Metadata Filter: <<{where}>> \nDoc Filer: <<{where_document}>> \n=> \n{results}")


def get_ids_for_documents(docs_for_hash:list[str], metadatas_for_hash:list[dict[str, Any]]) -> list[str]:
    """
    Generate ids for documents passed by deterministic hashing
    :param metadatas_for_hash:
    :param docs_for_hash:
    :return:
    """
    assert len(docs_for_hash) == len(metadatas_for_hash), "Length of docs and metadata mismatch. Must be of same length"
    list_of_ids = [
        hashlib.sha256(
            f"{doc} {json.dumps(metadata, sort_keys=True)}".encode("utf-8")
        ).hexdigest()
        for doc, metadata in zip(docs_for_hash, metadatas_for_hash)
    ]

    return list_of_ids


def print_docs_with_ids(collection:Collection) -> list[str]:
    """
    Prints all docs from chroma along with their ids
    :param collection:
    :return:
    """
    result = collection.get(include=["documents"])

    result_list = [
        f"{doc_id} -> {doc.split()[:10]}"
        for doc_id, doc in zip(result["ids"], result["documents"])
    ]

    return result_list


def chroma_db_orchestrator(collection:Collection) -> None:
    """
    Orchestrator for this script
    :param collection:
    :return:
    """
    add_documents_to_chroma_store(docs=documents, doc_ids=get_ids_for_documents(documents, metadatas),
                                  metadata_list=metadatas, collection=collection)

    result_1st_run = print_docs_with_ids(collection)
    logger.info("Result after 1st run\n%s", "\n".join(result_1st_run))

    add_documents_to_chroma_store(docs=documents, doc_ids=get_ids_for_documents(documents, metadatas),
                                  metadata_list=metadatas, collection=collection)

    result_2nd_run = print_docs_with_ids(collection)
    logger.info("Result after 2nd run\n%s", "\n".join(result_2nd_run))

    if result_1st_run == result_2nd_run:
        logger.info("Lists match perfectly")
    else:
        raise AssertionError("Lists mismatch")

    peek_id = collection.peek(1).get("ids")[0]

    collection.update([peek_id], documents=["This is changed and updated"])
    result_3rd_run = print_docs_with_ids(collection)
    logger.info("Result after 3rd run\n%s", "\n".join(result_3rd_run))

    # # 1. Simple semantic search — no filters
    # query_chroma_store(["How does Kafka handle high throughput?"], collection=collection)
    #
    # # 2. Another simple query — different topic
    # query_chroma_store(["What happens when a service goes down?"], collection=collection)
    #
    # # 3. Multiple results
    # query_chroma_store(["distributed systems coordination"], collection=collection, n_results=3)

if __name__ == "__main__":

    default_embedding_collection = create_chroma_collection("default-collection")

    chroma_db_orchestrator(default_embedding_collection)