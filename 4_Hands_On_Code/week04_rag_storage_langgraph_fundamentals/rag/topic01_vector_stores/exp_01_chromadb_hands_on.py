"""
This script corresponds to the entire experiments requirements of day 1 and 2
"""

from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction, EmbeddingFunction, \
    SentenceTransformerEmbeddingFunction

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")

client = chromadb.PersistentClient(path="./chroma-db")

documents = [
    "Kafka uses a commit log architecture where messages are appended sequentially to partitions, enabling high throughput and replay capability.",
    "Circuit breakers prevent cascading failures by failing fast when a downstream service is unhealthy, allowing the system to degrade gracefully.",
    "Consistent hashing minimizes key redistribution when nodes join or leave a cluster, making it ideal for distributed caches like Redis Cluster.",
    "The CAP theorem states that a distributed system can only guarantee two of three properties: consistency, availability, and partition tolerance.",
    "Event sourcing stores state changes as a sequence of events rather than current state, enabling full audit trails and temporal queries.",
    "Leader election algorithms like Raft ensure only one node coordinates writes at a time, preventing split-brain scenarios in distributed databases.",
    "Backpressure mechanisms protect systems from being overwhelmed by slowing down producers when consumers cannot keep up with the message rate.",
    "Idempotency keys allow safe retries of API calls by ensuring the same request processed multiple times produces the same result.",
    "Bloom filters provide space-efficient probabilistic membership testing, useful for checking if a key exists before hitting disk or network.",
    "Vector clocks track causality in distributed systems by maintaining a logical timestamp per node, helping detect concurrent updates."
]

ids = [f"doc{i}" for i in range(1, 11)]

metadatas = [
    {"source": "kafka-docs", "category": "messaging"},
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "system-design", "category": "partitioning"},
    {"source": "distributed-theory", "category": "fundamentals"},
    {"source": "event-driven-arch", "category": "patterns"},
    {"source": "consensus-algorithms", "category": "coordination"},
    {"source": "reactive-systems", "category": "flow-control"},
    {"source": "api-design", "category": "reliability"},
    {"source": "probabilistic-ds", "category": "data-structures"},
    {"source": "distributed-theory", "category": "coordination"}
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

def chroma_db_orchestrator(collection:Collection) -> None:
    """
    Orchestrator for this script
    :param collection:
    :return:
    """
    add_documents_to_chroma_store(docs=documents, doc_ids=ids,
                                  metadata_list=metadatas, collection=collection)

    # 1. Simple semantic search — no filters
    query_chroma_store(["How does Kafka handle high throughput?"], collection=collection)

    # 2. Another simple query — different topic
    query_chroma_store(["What happens when a service goes down?"], collection=collection)

    # 3. Multiple results
    query_chroma_store(["distributed systems coordination"], collection=collection, n_results=3)

    # 4. Metadata filter — exact match on category
    query_chroma_store(["prevent system overload"], collection=collection,
                       where={"category": "flow-control"})

    # 5. Metadata filter — exact match on source
    query_chroma_store(["consensus and leaders"], collection=collection,
                       where={"source": "consensus-algorithms"})

    # 6. Metadata filter — $in operator (match any of these categories)
    query_chroma_store(["how to handle failures"], collection=collection,
                       where={"category": {"$in": ["fault-tolerance", "reliability"]}})

    # 7. where_document — contains specific word
    query_chroma_store(["data storage patterns"], collection=collection,
                       where_document={"$contains": "events"})

    # 8. Combined — metadata + where_document
    query_chroma_store(["system design concept"], collection=collection,
                       where={"category": "fundamentals"},
                       where_document={"$contains": "distributed"})

    # 9. Metadata filter — $ne (not equal)
    query_chroma_store(["messaging patterns"], collection=collection,
                       where={"category": {"$ne": "data-structures"}}, n_results=2)

    # 10. Multiple conditions with $and
    query_chroma_store(["reliability patterns"], collection=collection,
                       where={"$and": [{"category": "coordination"}, {"source": "distributed-theory"}]})

if __name__ == "__main__":

    # openai_embedding_function = OpenAIEmbeddingFunction(api_key=open_ai_key, model_name="text-embedding-3-small")
    # openai_powered_collection = create_chroma_collection("openai-collection", openai_embedding_function)
    #
    # sentence_transformer_embedding_function = SentenceTransformerEmbeddingFunction(model_name="all-mpnet-base-v2")
    # sentence_transformer_collection = create_chroma_collection(name="sentence-transformer-collection",
    #                                                            embedding_function=sentence_transformer_embedding_function)

    default_embedding_collection = create_chroma_collection("default-collection")


    # chroma_db_orchestrator(sentence_transformer_collection)

    try:
        default_embedding_collection.add(documents=documents, metadatas=metadatas, ids=ids)
        logger.info(f"Total count of documents: {default_embedding_collection.count()}")
    except Exception as e:
        logger.info("Error adding documents")