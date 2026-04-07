"""
This script corresponds to Day 3-4->Day 2->Experiments->
Build a SimpleRAG class:
Success Criteria:

Retrieves top-k relevant chunks for a question
Formats context into a clear prompt for the LLM
LLM generates answer based on retrieved context
Returns sources with scores (for transparency)
Handles "no relevant results" — doesn't hallucinate, admits uncertainty
query_with_history incorporates previous Q&A for follow-up questions
Tracks token usage
Tested with at least 10 questions — verify answers are grounded in retrieved content
"""

import json
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from openai import OpenAI, BadRequestError, APIError
from openai.types.responses import Response

from common.config import get_config
from common.logger import get_logger

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")

client = chromadb.PersistentClient(path="./chroma-db")
openai_client = OpenAI(api_key=open_ai_key)

documents = [
    # Messaging & Streaming (1-10)
    "Kafka uses a commit log architecture where messages are appended sequentially to partitions, enabling high throughput and replay capability.",
    "Consumer groups in Kafka allow horizontal scaling by distributing partitions across multiple consumers, with each partition consumed by exactly one consumer in the group.",
    "Kafka's retention policy can be time-based or size-based, allowing consumers to replay historical messages within the retention window.",
    "Message ordering in Kafka is guaranteed only within a single partition, not across partitions in a topic.",
    "Kafka producers can choose between at-most-once, at-least-once, and exactly-once delivery semantics based on acks configuration and idempotent settings.",
    "Dead letter queues capture messages that fail processing after multiple retries, preventing poison messages from blocking the pipeline.",
    "Backpressure mechanisms prevent fast producers from overwhelming slow consumers by signaling upstream to reduce message rate.",
    "Event-driven architectures decouple producers from consumers, allowing independent scaling and deployment of each component.",
    "Message brokers like RabbitMQ use exchanges and bindings to route messages to queues based on routing keys and patterns.",
    "Pub/sub systems broadcast messages to all subscribers, while message queues deliver each message to exactly one consumer.",

    # Fault Tolerance (11-20)
    "Circuit breakers prevent cascading failures by failing fast when a downstream service is unhealthy, allowing the system to degrade gracefully.",
    "The bulkhead pattern isolates failures by partitioning resources, preventing a failure in one component from consuming all available resources.",
    "Retry strategies with exponential backoff prevent thundering herd problems when recovering from transient failures.",
    "Idempotency keys ensure that retried operations produce the same result, making it safe to retry failed requests without side effects.",
    "Health checks and heartbeats allow load balancers and orchestrators to detect unhealthy instances and route traffic away from them.",
    "Chaos engineering intentionally injects failures into production systems to verify resilience and discover weaknesses before real outages.",
    "Graceful degradation allows a system to continue operating with reduced functionality when some components are unavailable.",
    "Timeouts prevent indefinite blocking on slow or unresponsive services, freeing resources for other requests.",
    "Failover strategies like active-passive or active-active determine how traffic shifts when a primary instance becomes unavailable.",
    "The saga pattern manages distributed transactions by coordinating a sequence of local transactions with compensating actions for rollback.",

    # Consistency & Consensus (21-30)
    "The CAP theorem states that a distributed system can only guarantee two of three properties: consistency, availability, and partition tolerance.",
    "Strong consistency ensures all nodes see the same data at the same time, at the cost of higher latency and reduced availability.",
    "Eventual consistency allows temporary inconsistencies between replicas, with guarantees that all replicas converge given sufficient time.",
    "Paxos achieves consensus among distributed nodes by requiring a majority quorum to agree on a value before committing.",
    "Raft simplifies consensus by electing a leader that coordinates all writes, making the algorithm easier to understand than Paxos.",
    "Vector clocks track causality between events in distributed systems, allowing detection of concurrent updates and conflicts.",
    "Quorum reads and writes (R + W > N) ensure consistency by requiring overlap between read and write replica sets.",
    "Two-phase commit (2PC) coordinates atomic transactions across multiple nodes but blocks if the coordinator fails during the protocol.",
    "CRDTs (Conflict-free Replicated Data Types) allow concurrent updates without coordination by designing data structures that merge automatically.",
    "Linearizability provides the illusion that operations happen instantaneously at some point between invocation and response.",

    # Data Partitioning & Distribution (31-40)
    "Consistent hashing minimizes key redistribution when nodes join or leave a cluster, making it ideal for distributed caches like Redis Cluster.",
    "Range partitioning assigns contiguous key ranges to different nodes, enabling efficient range queries but risking hotspots on popular ranges.",
    "Hash partitioning distributes keys uniformly across nodes using a hash function, preventing hotspots but making range queries expensive.",
    "Replication factor determines how many copies of data exist across nodes, trading storage cost for fault tolerance and read throughput.",
    "Leader-follower replication routes all writes through a single leader while followers serve read requests and provide redundancy.",
    "Multi-leader replication allows writes at multiple nodes simultaneously, improving write availability but requiring conflict resolution.",
    "Sharding splits a database horizontally across multiple servers, with each shard holding a subset of the total data.",
    "Virtual nodes improve load distribution in consistent hashing by assigning multiple hash ring positions to each physical node.",
    "Cross-shard queries require scatter-gather operations that fan out to multiple shards and aggregate results, increasing latency.",
    "Rebalancing redistributes data when nodes are added or removed, requiring careful orchestration to avoid performance degradation.",

    # Caching & Performance (41-50)
    "Cache-aside pattern has the application check the cache before the database, populating the cache on misses.",
    "Write-through caching writes data to both cache and database synchronously, ensuring consistency at the cost of write latency.",
    "Write-behind caching batches writes to the database asynchronously, improving write performance but risking data loss on cache failure.",
    "Cache invalidation is one of the hardest problems in computer science, requiring careful strategies to prevent serving stale data.",
    "TTL (time-to-live) automatically expires cached entries after a duration, balancing freshness against cache hit rate.",
    "CDNs cache static content at edge locations geographically close to users, reducing latency and backend load.",
    "Read replicas offload read traffic from the primary database, improving read throughput but introducing replication lag.",
    "Connection pooling reuses database connections across requests, avoiding the overhead of establishing new connections.",
    "Load balancing distributes incoming requests across multiple servers using algorithms like round-robin, least-connections, or weighted routing.",
    "Rate limiting protects services from being overwhelmed by restricting the number of requests a client can make in a time window."
]

metadatas = [
    # Messaging & Streaming (1-10)
    {"source": "kafka-docs", "category": "messaging"},
    {"source": "kafka-docs", "category": "messaging"},
    {"source": "kafka-docs", "category": "messaging"},
    {"source": "kafka-docs", "category": "messaging"},
    {"source": "kafka-docs", "category": "messaging"},
    {"source": "messaging-patterns", "category": "messaging"},
    {"source": "messaging-patterns", "category": "messaging"},
    {"source": "event-driven-arch", "category": "messaging"},
    {"source": "rabbitmq-docs", "category": "messaging"},
    {"source": "messaging-patterns", "category": "messaging"},

    # Fault Tolerance (11-20)
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "chaos-engineering", "category": "fault-tolerance"},
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "resilience-patterns", "category": "fault-tolerance"},
    {"source": "distributed-transactions", "category": "fault-tolerance"},

    # Consistency & Consensus (21-30)
    {"source": "distributed-theory", "category": "consistency"},
    {"source": "distributed-theory", "category": "consistency"},
    {"source": "distributed-theory", "category": "consistency"},
    {"source": "consensus-algorithms", "category": "consistency"},
    {"source": "consensus-algorithms", "category": "consistency"},
    {"source": "distributed-theory", "category": "consistency"},
    {"source": "distributed-theory", "category": "consistency"},
    {"source": "distributed-transactions", "category": "consistency"},
    {"source": "distributed-theory", "category": "consistency"},
    {"source": "distributed-theory", "category": "consistency"},

    # Data Partitioning & Distribution (31-40)
    {"source": "system-design", "category": "partitioning"},
    {"source": "system-design", "category": "partitioning"},
    {"source": "system-design", "category": "partitioning"},
    {"source": "system-design", "category": "partitioning"},
    {"source": "replication-patterns", "category": "partitioning"},
    {"source": "replication-patterns", "category": "partitioning"},
    {"source": "system-design", "category": "partitioning"},
    {"source": "system-design", "category": "partitioning"},
    {"source": "system-design", "category": "partitioning"},
    {"source": "system-design", "category": "partitioning"},

    # Caching & Performance (41-50)
    {"source": "caching-patterns", "category": "performance"},
    {"source": "caching-patterns", "category": "performance"},
    {"source": "caching-patterns", "category": "performance"},
    {"source": "caching-patterns", "category": "performance"},
    {"source": "caching-patterns", "category": "performance"},
    {"source": "cdn-architecture", "category": "performance"},
    {"source": "database-scaling", "category": "performance"},
    {"source": "database-scaling", "category": "performance"},
    {"source": "system-design", "category": "performance"},
    {"source": "system-design", "category": "performance"},
]

doc_ids = [
    # Messaging & Streaming (1-10)
    "msg-001",
    "msg-002",
    "msg-003",
    "msg-004",
    "msg-005",
    "msg-006",
    "msg-007",
    "msg-008",
    "msg-009",
    "msg-010",

    # Fault Tolerance (11-20)
    "ft-001",
    "ft-002",
    "ft-003",
    "ft-004",
    "ft-005",
    "ft-006",
    "ft-007",
    "ft-008",
    "ft-009",
    "ft-010",

    # Consistency & Consensus (21-30)
    "cons-001",
    "cons-002",
    "cons-003",
    "cons-004",
    "cons-005",
    "cons-006",
    "cons-007",
    "cons-008",
    "cons-009",
    "cons-010",

    # Data Partitioning & Distribution (31-40)
    "part-001",
    "part-002",
    "part-003",
    "part-004",
    "part-005",
    "part-006",
    "part-007",
    "part-008",
    "part-009",
    "part-010",

    # Caching & Performance (41-50)
    "perf-001",
    "perf-002",
    "perf-003",
    "perf-004",
    "perf-005",
    "perf-006",
    "perf-007",
    "perf-008",
    "perf-009",
    "perf-010",
]

def create_chroma_collection(name: str) -> Collection:
    """
    namesake with passed embedding function
    :param name:
    :return:
    """
    return client.get_or_create_collection(name=name)


def init_chroma_collection_with_docs(collection:Collection) -> None:
    """
    Namesake
    :param collection:
    :return:
    """
    collection.add(documents=documents, ids=doc_ids, metadatas=metadatas)


class SimpleRAG:
    def __init__(
            self,
            collection_name: str,
            llm_model: str = "gpt-5.4-mini",
            top_k: int = 5
    ):
        """
        Simple RAG implementation: retrieve and generate.
        """
        self._top_k = top_k
        self._llm_model = llm_model
        self._collection_name = collection_name
        self._collection = create_chroma_collection(self._collection_name)
        init_chroma_collection_with_docs(self._collection)

        self._system_message = (
            "You are a question-answering assistant. "
            "Answer using the context provided in the user message. "
            "If conversation history is provided, use it to understand follow-up questions and resolve references like 'it', 'this', or 'that'. "
            "You may explain and synthesize information from the context. "
            "If the context doesn't contain relevant information, say 'I don't have enough information to answer this.' "
            "Do not add facts that aren't supported by the context."
        )

    def __call_open_ai(self, input_to_gpt:str) -> Response | None:
        """
        calls openai gpt api and gets response
        """
        try:
            response = openai_client.responses.create(
                model=self._llm_model,
                input=input_to_gpt,
                max_output_tokens=1000,
                temperature=0.5,
                instructions=self._system_message
            )

            if response is not None:
                logger.info("Response created successfully")
                return response

        except BadRequestError as e:
            logger.exception("Bad request: prompt/model/params issue")
        except APIError as e:
            logger.exception("OpenAI server/API error")
        except Exception as e:
            logger.exception("Unexpected failure")

    def __query_chroma_store(self, query_texts: list[str]) -> list[dict[str, Any]]:
        """
        namesake
        :param query_texts:
        :return:
        """
        results = self._collection.query(
            query_texts=query_texts,
            n_results=self._top_k
        )

        documents_list = results["documents"][0]
        metadatas_list = results["metadatas"][0]
        distances_list = results["distances"][0]

        chroma_return_list = [
            {
                "content": document,
                "metadata": metadata,
                "score": distance

            }
            for document, metadata, distance in zip(documents_list, metadatas_list, distances_list)
        ]

        return chroma_return_list

    def query(self, question: str) -> dict:
        """
        Answer a question using retrieved context.
        Returns:
            {
                "answer": str,
                "sources": [{"content": str, "metadata": dict, "score": float}],
                "tokens_used": int
            }
        """
        fetched_docs = self.__query_chroma_store([question])
        context = "\n\n".join(
            doc["content"]
            for doc in fetched_docs
        )

        prompt = f"""
        Question: {question}

        Context:
        {context}
        """
        response_from_gpt = self.__call_open_ai(prompt)

        answer = {
            "answer": response_from_gpt.output_text,
            "sources": fetched_docs,
            "tokens_used": response_from_gpt.usage.total_tokens
        }

        return answer

    def query_with_history(
            self,
            question: str,
            conversation_history: list[dict]
    ) -> dict:
        """Answer considering conversation history."""
        history_text = "\n".join(
            f"Q: {turn['question']}\nA: {turn['answer']}"
            for turn in conversation_history
        )

        retrieval_query = f"""
            Conversation history:
            {history_text}

            Follow-up question:
            {question}
            """

        fetched_docs = self.__query_chroma_store([retrieval_query])
        context = "\n\n".join(
            doc["content"]
            for doc in fetched_docs
        )

        prompt = f"""
                Conversation_History: {conversation_history}
                Question: {question}

                Context:
                {context}
                """
        response_from_gpt = self.__call_open_ai(prompt)

        answer = {
            "answer": response_from_gpt.output_text,
            "sources": fetched_docs,
            "tokens_used": response_from_gpt.usage.total_tokens
        }

        return answer

if __name__ == "__main__":
    simpleRAG = SimpleRAG(collection_name="simple-rag-collection")

    # grounded_questions = [
    #     "How does Kafka guarantee message ordering?",
    #     "What is a circuit breaker and why is it useful?",
    #     "Explain the CAP theorem",
    #     "How does consistent hashing help with scaling?",
    #     "What's the difference between write-through and write-behind caching?",
    #     "How does Raft achieve consensus?",
    #     "What is the saga pattern used for?",
    #     "How do CDNs reduce latency?"
    # ]
    #
    # uncertain_questions = [
    #     "What is GraphQL and how does it compare to REST?",
    #     "Explain how React hooks work"
    # ]
    #
    # for question_to_send in grounded_questions + uncertain_questions:
    #     logger.info(
    #         f"Answer for question <<{question_to_send}>>:\n"
    #         f"{simpleRAG.query(question_to_send)}\n"
    #     )

    conversation_history_sample = [
        {
            "question": "What is a circuit breaker?",
            "answer": "It prevents cascading failures by failing fast when downstream services are unhealthy."
        },
        {
            "question": "How is it different from retries?",
            "answer": "Retries attempt the operation again, while circuit breakers stop repeated calls when failure is likely."
        }
    ]

    question_to_send_1 = "When should I combine both?"

    logger.info(
            f"Answer for question <<{question_to_send_1}>>:\n"
            f"{ simpleRAG.query_with_history(question_to_send_1, conversation_history_sample)}\n"
        )