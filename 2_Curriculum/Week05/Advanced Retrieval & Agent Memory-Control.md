# Week 5: Parallel Tracks — Advanced Retrieval + Agent Memory & Control

> **Track:** Parallel (RAG + Agents) **Time:** 2 hours/day (1 hour RAG + 1 hour Agents) **Goal:** Upgrade RAG retrieval quality with hybrid search, reranking, and query transformation. Add persistence, memory, and human oversight to agents.

---

## Overview

### RAG Track (1 hour/day)

|Days|Topic|Output|
|---|---|---|
|1-2|Hybrid Search|BM25 + dense vectors working|
|3-4|Reranking|Mini Challenge complete|
|5-6|Query Transformation|Mini Challenge complete|
|7|Mini Build|RAG v2 (improved retrieval)|

### Agent Track (1 hour/day)

|Days|Topic|Output|
|---|---|---|
|1-2|State Management & Checkpointing|Persistent state working|
|3-4|Memory Systems|Mini Challenge complete|
|5-6|Human-in-the-Loop|Mini Challenge complete|
|7|Mini Build|Agent with Memory + Checkpointing|

---

# RAG TRACK

---

## Days 1-2 (RAG): Hybrid Search

### Why This Matters

Dense vector search (embeddings) is great for semantic similarity but fails on:

- Exact keyword matches ("error code ABC123")
- Rare terms not well-represented in embeddings
- Precise phrases where word order matters

BM25 (keyword search) is great for exact matches but fails on:

- Synonyms ("car" vs. "automobile")
- Paraphrases (same meaning, different words)
- Conceptual similarity

Hybrid search combines both: retrieve candidates using both methods, then merge. This catches what either method alone would miss.

### What to Learn

**Core Concepts:**

- **BM25**: Term frequency, inverse document frequency, sparse retrieval
- **Dense retrieval**: Embedding similarity, what you've been doing
- **Fusion strategies**: How to merge two ranked lists (RRF, weighted sum)
- **Reciprocal Rank Fusion (RRF)**: The most common fusion method
- **When hybrid beats single-method**: The failure modes each covers

**The Hybrid Pipeline:**

```
[Query] ──┬──> [BM25 Search] ────> [Top K sparse results]──┐
          │                                                 │
          └──> [Dense Search] ───> [Top K dense results]───┼──> [Fusion] ──> [Final Top K]
```

**Practical Skills:**

- Implement BM25 search (using rank-bm25 or similar)
- Combine BM25 + dense results
- Tune the balance between sparse and dense

### Resources

**Primary:**

- rank-bm25 library: https://github.com/dorianbrown/rank_bm25
- Pinecone Hybrid Search Guide: https://www.pinecone.io/learn/hybrid-search-intro/
- Weaviate Hybrid Search: https://weaviate.io/developers/weaviate/search/hybrid

**Secondary:**

- Search: "reciprocal rank fusion explained"
- Search: "BM25 algorithm explained"

### Day 1 Tasks (1 hour)

**First 30 min — Learn:**

1. Read about BM25 — understand TF-IDF basics (15 min)
2. Read Pinecone hybrid search guide (15 min)

**Next 30 min — Experiment:**

1. Install: `pip install rank-bm25`
2. Take your Week 4 chunks
3. Create a BM25 index from chunk texts
4. Query with BM25 — see what it retrieves
5. Compare: Same query, BM25 results vs. dense results. Where do they differ?

### Day 2 Tasks (1 hour)

**First 30 min — Learn:**

1. Read about Reciprocal Rank Fusion — the math is simple (15 min)
2. Understand: Why RRF works better than simple score averaging (10 min)
3. Think: What ratio of BM25 vs. dense would you start with? (5 min)

**Next 30 min — Experiment:**

1. Implement RRF: Given two ranked lists, produce a fused ranking
2. Test on 5 queries: Get BM25 top-10, dense top-10, fuse them
3. For each query: Did fusion find something neither method found alone?
4. Edge case: What if a document appears in both lists? (It should rank higher)

### 5 Things to Ponder (Hybrid Search)

1. BM25 finds "error code XYZ123" perfectly. Dense search misses it entirely (the code isn't semantically meaningful). Without hybrid, your RAG fails on technical queries. What other query types might BM25 save?
    
2. You fuse BM25 and dense with 50/50 weight. For some queries, BM25 is clearly better. For others, dense is clearly better. How might you dynamically adjust the weight based on the query?
    
3. BM25 requires a text index (inverted index). Dense requires a vector index. You're now maintaining two indexes. What's the operational cost? When is it worth it?
    
4. Your chunks are code snippets. BM25 matches on function names and keywords. Dense matches on "what the code does." Which is more useful for "find code that sorts a list"? Which for "find the merge_accounts function"?
    
5. RRF uses rank position, not scores. A document ranked #1 with score 0.99 and one ranked #1 with score 0.51 are treated the same. Is this a feature or a bug? When might you want score-based fusion instead?
    

---

## Days 3-4 (RAG): Reranking

### Why This Matters

Initial retrieval (BM25 or dense) is fast but coarse. It uses bi-encoders: query and document are encoded separately, then compared. This is efficient but loses nuance.

Reranking uses cross-encoders: query and document are encoded together, allowing deep interaction. It's slower but much more accurate.

Pattern: Retrieve many (fast, coarse) → Rerank few (slow, precise)

### What to Learn

**Core Concepts:**

- **Bi-encoder**: Encode query and doc separately, compare vectors (fast, used for retrieval)
- **Cross-encoder**: Encode query+doc together, output relevance score (slow, used for reranking)
- **Two-stage retrieval**: Retrieve top-100 with bi-encoder, rerank to top-10 with cross-encoder
- **Reranking models**: Cohere Rerank, BGE Reranker, cross-encoder models from sentence-transformers

**The Reranking Pipeline:**

```
[Query] → [Initial Retrieval (top 50-100)] → [Reranker] → [Reranked top 5-10] → [LLM]
```

**Practical Skills:**

- Integrate a reranker into your pipeline
- Choose how many to retrieve vs. how many to rerank
- Measure the improvement reranking provides

### Resources

**Primary:**

- Cohere Rerank: https://docs.cohere.com/docs/rerank-2
- Sentence Transformers Cross-Encoders: https://www.sbert.net/docs/cross_encoder/usage/usage.html
- BGE Reranker: https://huggingface.co/BAAI/bge-reranker-base

**Secondary:**

- Search: "cross encoder vs bi encoder"
- Search: "reranking for RAG"

### Day 3 Tasks (1 hour)

**First 30 min — Learn:**

1. Read about bi-encoder vs. cross-encoder — understand the difference (15 min)
2. Read Cohere Rerank docs or sentence-transformers cross-encoder docs (15 min)

**Next 30 min — Experiment:**

1. Choose a reranker:
    - Option A: Cohere Rerank API (easy, requires API key)
    - Option B: sentence-transformers cross-encoder (free, local)
    - Option C: BGE Reranker from HuggingFace (free, local)
2. Take a query and your top-20 retrieved chunks
3. Run through reranker — see the new ordering
4. Compare: Did clearly relevant chunks move up? Did irrelevant ones move down?

### Day 4 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build a `Reranker` class:

```python
class Reranker:
    def __init__(
        self,
        model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",  # or "cohere" for API
        top_k: int = 5
    ):
        """
        Reranks retrieved documents for relevance to query.
        """
        pass
    
    def rerank(
        self,
        query: str,
        documents: list[dict],  # [{"content": str, "metadata": dict, "score": float}]
    ) -> list[dict]:
        """
        Rerank documents and return top_k most relevant.
        
        Returns documents with updated scores and rankings.
        """
        pass
```

**Success Criteria:**

- [ ] Takes query + list of documents, returns reranked list
- [ ] Works with at least one reranker model (local or API)
- [ ] Returns top_k documents with new relevance scores
- [ ] Preserves metadata through reranking
- [ ] Handles edge cases: empty list, fewer docs than top_k
- [ ] Tested: Compare retrieval-only vs. retrieval+reranking on 5 queries
- [ ] Measurable improvement on at least 3/5 queries

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Reranking)

1. You retrieve top-100, rerank to top-5. The cross-encoder runs 100 times per query. If the cross-encoder takes 50ms per document, that's 5 seconds per query. How do you balance quality vs. latency? What's the minimum retrieval set you can rerank?
    
2. Your initial retrieval returns a relevant document at position #87. You only rerank top-50. That document never gets seen by the reranker. How do you decide how many to retrieve for reranking?
    
3. Cross-encoders are trained on specific datasets (MS MARCO, etc.). Your domain is medical records. The cross-encoder might not understand medical relevance. Would you fine-tune? Use a different model? Something else?
    
4. You add reranking to your RAG. Quality improves but latency doubles. Users complain about slow responses. How would you architect for both quality and speed? (Hint: Async? Caching? Streaming first results?)
    
5. Reranking reorders your chunks. But what if the most relevant information is spread across chunks #3, #7, and #12? Reranking doesn't merge them. What's still missing from your retrieval pipeline?
    

---

## Days 5-6 (RAG): Query Transformation

### Why This Matters

User queries are messy. Document language is different. The gap between them kills retrieval:

- User: "how do I fix login problems" → Docs: "authentication troubleshooting procedures"
- User: "what's the deal with refunds" → Docs: "return policy and reimbursement guidelines"

Query transformation bridges this gap by rewriting queries to match document language.

### What to Learn

**Core Concepts:**

- **HyDE (Hypothetical Document Embeddings)**: Generate a hypothetical answer, embed that instead of the query
- **Query expansion**: Add synonyms, related terms to the query
- **Query rewriting**: Use LLM to rephrase query in document language
- **Multi-query**: Generate multiple query variations, retrieve for each, merge results
- **Step-back prompting**: For complex queries, ask a more general question first

**Query Transformation Techniques:**

```
[User Query] → [Transformation] → [Better Query] → [Retrieval]

HyDE:        "what's the return policy" → LLM generates hypothetical answer → embed that
Expansion:   "return policy" → "return policy OR refund policy OR exchange policy"
Rewriting:   "how do I fix login" → "authentication troubleshooting steps"
Multi-query: "ML best practices" → ["machine learning best practices", "ML tips", "AI guidelines"]
```

**Practical Skills:**

- Implement HyDE
- Implement query expansion/rewriting
- Know when each technique helps most

### Resources

**Primary:**

- HyDE Paper: https://arxiv.org/abs/2212.10496 (read abstract + method section)
- LangChain Query Transformation: https://python.langchain.com/docs/how_to/query_multi_step/
- LlamaIndex Query Transformations: https://docs.llamaindex.ai/en/stable/optimizing/advanced_retrieval/query_transformations/

**Secondary:**

- Search: "HyDE retrieval augmented generation"
- Search: "query expansion techniques"

### Day 5 Tasks (1 hour)

**First 30 min — Learn:**

1. Read HyDE paper abstract and understand the core idea (10 min)
2. Read about query rewriting and expansion (10 min)
3. Think: Which technique would help which type of query? (10 min)

**Next 30 min — Experiment:**

1. Implement simple HyDE:
    - Take a query
    - Ask LLM: "Write a short paragraph that would answer this question: {query}"
    - Embed the hypothetical answer instead of the query
    - Compare retrieval results: query embedding vs. HyDE embedding
2. Try on 3 different queries — note where HyDE helps, where it doesn't

### Day 6 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build a `QueryTransformer` class:

```python
class QueryTransformer:
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        pass
    
    def hyde(self, query: str) -> str:
        """
        Generate hypothetical document for query.
        Returns text to embed instead of query.
        """
        pass
    
    def expand(self, query: str) -> list[str]:
        """
        Generate query variations/expansions.
        Returns list of queries to search with.
        """
        pass
    
    def rewrite_for_retrieval(self, query: str) -> str:
        """
        Rewrite casual query into retrieval-optimized form.
        """
        pass
    
    def multi_query(self, query: str, n: int = 3) -> list[str]:
        """
        Generate n different query perspectives.
        """
        pass
```

**Success Criteria:**

- [ ] `hyde()` generates relevant hypothetical answers
- [ ] `expand()` produces useful query variations (not just synonyms)
- [ ] `rewrite_for_retrieval()` transforms casual queries to document-style
- [ ] `multi_query()` generates genuinely different perspectives
- [ ] Each method tested on 3 queries
- [ ] At least one method shows clear retrieval improvement vs. original query
- [ ] Handles edge cases: very short queries, questions vs. statements

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Query Transformation)

1. HyDE uses an LLM to generate a hypothetical answer, then embeds that. But if the LLM hallucinates a wrong answer, you're now searching for wrong content. How do you mitigate this risk?
    
2. Multi-query generates 3 variations and retrieves for each. That's 3x the retrieval cost and 3x the embedding cost. When is this worth it? How would you decide dynamically?
    
3. You rewrite "what's the deal with our PTO" → "paid time off policy and procedures." But your company uses "vacation policy" not "PTO" or "paid time off." The rewrite didn't help. How might you incorporate company-specific terminology?
    
4. Query transformation adds an LLM call before retrieval. That's added latency and cost. For a high-traffic application, every millisecond matters. How would you decide when to transform vs. use the original query?
    
5. You combine all techniques: rewrite, then expand, then HyDE each expansion, then multi-query each HyDE output. You now have 27 queries to embed and search. Where's the line between thoroughness and absurdity?
    

---

## Day 7 (RAG): Mini Build — RAG v2 (Improved Retrieval)

### What to Build

Upgrade your Week 4 RAG v1 with the retrieval improvements from this week:

- Hybrid search (BM25 + dense)
- Reranking
- Query transformation

### Specifications

```python
from rag_v2 import RAGv2

# Initialize with advanced retrieval
rag = RAGv2(
    collection_name="my_docs",
    retrieval_mode="hybrid",  # "dense", "sparse", or "hybrid"
    use_reranker=True,
    query_transform="hyde"  # None, "hyde", "expand", "rewrite"
)

# Index documents (same as v1)
rag.index_directory("./documents/")

# Query with advanced retrieval
result = rag.query("how do I fix login issues?")

# Response includes retrieval metadata
print(result["answer"])
print(result["retrieval_info"])
# {
#     "original_query": "how do I fix login issues?",
#     "transformed_query": "authentication troubleshooting procedures...",  # if transformed
#     "bm25_candidates": 50,
#     "dense_candidates": 50,
#     "after_fusion": 30,
#     "after_rerank": 5,
#     "sources": [...]
# }

# Compare modes
result_basic = rag.query("...", retrieval_mode="dense", use_reranker=False, query_transform=None)
result_advanced = rag.query("...", retrieval_mode="hybrid", use_reranker=True, query_transform="hyde")
# See the difference in answer quality
```

### Success Criteria

- [ ] Hybrid search working (BM25 + dense fusion)
- [ ] Reranking integrated (configurable on/off)
- [ ] At least one query transformation method (HyDE recommended)
- [ ] All retrieval modes configurable (can A/B test)
- [ ] Retrieval metadata exposed (see what happened at each stage)
- [ ] Backward compatible with RAG v1 interface
- [ ] Tested on 10 queries across different types (exact match, semantic, casual, technical)
- [ ] Measurable improvement: At least 3 queries where v2 beats v1 clearly
- [ ] Performance tracked: Know the latency cost of each improvement

### Things to Ponder (Post-Build)

1. You now have many retrieval knobs: hybrid ratio, rerank count, transform type. How do you tune these for a specific use case? What's your methodology for finding optimal settings?
    
2. Your RAG v2 is better but slower. V1: 200ms. V2: 800ms. For some applications, V1 is fine. For others, V2 is needed. How would you auto-select based on query complexity?
    
3. You've improved retrieval significantly. But generation (the LLM answer) is still the same. What if retrieval is now perfect but generation still hallucinates? What's next to improve?
    
4. Week 6 is RAG Evaluation. How would you prove that v2 is actually better than v1? What metrics would you use? How would you collect ground truth?
    
5. Your retrieval pipeline is getting complex: transform → hybrid retrieve → fuse → rerank → select top-k. Each step can fail or degrade. How do you monitor this in production? How do you debug when quality drops?
    

---

# AGENT TRACK

---

## Days 1-2 (Agents): State Management & Checkpointing

### Why This Matters

Week 4 agents work for single conversations. But real agents need to:

- Remember what happened across sessions
- Pause mid-task and resume later
- Recover from crashes without losing progress
- Handle long-running tasks that span hours or days

State management and checkpointing enable all of this.

### What to Learn

**Core Concepts:**

- **State in LangGraph**: The TypedDict that flows through your graph
- **Checkpointing**: Saving state at each step, restoring later
- **Persistence backends**: Memory (dev), SQLite (simple), Postgres (production)
- **Thread ID**: Identifying a conversation/session for state lookup
- **Resumption**: Continuing from a checkpoint after pause or crash

**Practical Skills:**

- Configure a checkpointer in LangGraph
- Save and restore agent state
- Handle multiple concurrent conversations (threads)
- Design state that's serializable and restorable

### Resources

**Primary:**

- LangGraph Persistence: https://langchain-ai.github.io/langgraph/concepts/persistence/
- LangGraph Checkpointing: https://langchain-ai.github.io/langgraph/how-tos/persistence/
- LangGraph Memory Store: https://langchain-ai.github.io/langgraph/concepts/memory/

**Secondary:**

- Search: "langgraph sqlite checkpointer"
- Search: "langgraph persistence tutorial"

### Day 1 Tasks (1 hour)

**First 30 min — Learn:**

1. Read LangGraph persistence conceptual guide (15 min)
2. Understand thread_id and how it identifies conversations (10 min)
3. Read about different checkpointer backends (5 min)

**Next 30 min — Experiment:**

1. Take your Week 4 LangGraph agent
2. Add MemorySaver checkpointer (simplest)
3. Run a conversation with a thread_id
4. Stop execution, start a new Python process
5. Resume with same thread_id — verify state is restored

### Day 2 Tasks (1 hour)

**First 30 min — Deepen:**

1. Read about SQLite checkpointer — persistent across restarts (10 min)
2. Understand state serialization — what can/can't be saved (10 min)
3. Think about state design: What should be in state vs. computed fresh? (10 min)

**Next 30 min — Experiment:**

1. Switch to SqliteSaver (persistent)
2. Run a multi-turn conversation
3. Kill the process mid-conversation
4. Restart and resume — verify full history is preserved
5. Run two conversations with different thread_ids — verify isolation

### 5 Things to Ponder (State Management)

1. Your agent state includes `{"messages": [...], "tool_results": [...], "user_preference": "formal"}`. All must be serializable. What happens if you add a non-serializable object (like a database connection) to state? How should you handle external resources?
    
2. You checkpoint after every node. 100-node conversation = 100 checkpoints. Storage grows fast. When would you checkpoint less frequently? What's the tradeoff?
    
3. User starts a conversation Monday, resumes Friday. The world has changed (new data, updated documents). Agent has old context. How do you handle "stale state" in long-running agents?
    
4. Two users accidentally get the same thread_id (bug in your app). Their conversations merge. Chaos ensues. How do you prevent this? How do you design thread_id generation?
    
5. Your agent crashed at step 47 of a 100-step task. You resume from checkpoint. But step 47 was "send email" — which succeeded before crash. Now it sends again. How do you make operations idempotent or prevent double-execution?
    

---

## Days 3-4 (Agents): Memory Systems

### Why This Matters

Checkpointing saves state. But agents also need to _remember_ — across conversations, across time:

- "User prefers short answers" (learned from feedback)
- "We discussed Project X last week" (conversation history)
- "User's company is Acme Corp" (entity information)

Different memory types serve different needs.

### What to Learn

**Core Concepts:**

- **Conversation memory**: Recent message history (what you've been doing)
- **Summary memory**: Compressed history (long conversations)
- **Entity memory**: Facts about people, places, things mentioned
- **Semantic memory**: Long-term knowledge stored as embeddings (searchable)
- **Memory vs. State**: State is current session, memory spans sessions

**Memory Types:**

```
Conversation: [msg1, msg2, msg3, msg4, msg5]  ← Full recent history
Summary:      "User asked about X, we discussed Y, decided Z"  ← Compressed
Entity:       {"John": "CEO of Acme", "Project X": "due March"}  ← Extracted facts
Semantic:     Vector store of past interactions  ← Searchable
```

**Practical Skills:**

- Implement conversation memory with windowing
- Implement summary memory (compress when too long)
- Extract and store entities
- Design memory architecture for your use case

### Resources

**Primary:**

- LangGraph Memory Guide: https://langchain-ai.github.io/langgraph/concepts/memory/
- LangChain Memory Types: https://python.langchain.com/docs/concepts/memory/
- LangGraph Store: https://langchain-ai.github.io/langgraph/concepts/persistence/#memory-store

**Secondary:**

- Search: "conversational memory LLM"
- Search: "entity extraction memory"

### Day 3 Tasks (1 hour)

**First 30 min — Learn:**

1. Read LangGraph memory concepts (15 min)
2. Understand the difference between short-term (state) and long-term (store) memory (10 min)
3. Read about memory in LangChain — different memory types (5 min)

**Next 30 min — Experiment:**

1. Implement simple conversation memory: Keep last N messages
2. Test: Long conversation that exceeds N — verify old messages drop
3. Implement basic summarization: When history > threshold, summarize old messages
4. Test: Does the agent remember key facts even after summarization?

### Day 4 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build a `MemoryManager` class:

```python
class MemoryManager:
    def __init__(
        self,
        max_messages: int = 20,
        summarize_threshold: int = 15,
        llm_model: str = "gpt-4o-mini"
    ):
        """
        Manages agent memory across conversations.
        """
        pass
    
    def add_message(self, role: str, content: str, thread_id: str) -> None:
        """Add a message to conversation memory."""
        pass
    
    def get_context(self, thread_id: str) -> list[dict]:
        """
        Get memory context for a thread.
        Returns: messages + summary if exists
        """
        pass
    
    def extract_entities(self, messages: list[dict]) -> dict:
        """
        Extract key entities from messages.
        Returns: {"entity_name": "description", ...}
        """
        pass
    
    def search_memory(self, query: str, thread_id: str = None) -> list[dict]:
        """
        Search across past conversations (semantic memory).
        If thread_id provided, search only that thread.
        """
        pass
```

**Success Criteria:**

- [ ] Conversation memory works with windowing (keeps last N)
- [ ] Auto-summarizes when exceeding threshold
- [ ] Entities extracted and stored (at least: names, places, key facts)
- [ ] Semantic search across past conversations works
- [ ] Multiple threads isolated (thread A's memory doesn't leak to thread B)
- [ ] Tested: 30-message conversation, verify summary captures key points
- [ ] Tested: Ask about entity mentioned 20 messages ago — verify recall

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Memory Systems)

1. You summarize messages 1-15 to make room for new ones. The summary loses detail. User asks about something from message #7. Agent doesn't remember. What's the right granularity for summaries?
    
2. Entity extraction: "John mentioned his wife Sarah works at Google." Do you store: John → {wife: Sarah}, Sarah → {employer: Google}, or both? What's your entity schema?
    
3. Semantic memory is a vector store of past interactions. But interactions have timestamps. A fact from 2 years ago might be outdated. How do you handle memory decay/expiration?
    
4. User: "Remember that I hate long responses." This is a preference, not a fact. Where should this go? It should affect ALL future conversations, not just this one. How do you handle user preferences vs. conversation memory?
    
5. Your agent has 1000 past conversations in semantic memory. User asks a new question. You search memory and retrieve 5 relevant past snippets. But one is from a confidential conversation with a different user. How do you handle memory isolation and privacy?
    

---

## Days 5-6 (Agents): Human-in-the-Loop

### Why This Matters

Autonomous agents are powerful but dangerous. They can:

- Send wrong emails
- Delete wrong files
- Make wrong API calls
- Spend wrong money

Human-in-the-loop (HITL) adds checkpoints where humans review/approve before proceeding. Essential for production.

### What to Learn

**Core Concepts:**

- **Interrupts**: Pausing graph execution for human input
- **Approval nodes**: "Stop here, wait for human to approve"
- **Edit nodes**: "Show human the plan, let them modify"
- **Breakpoints**: Programmatic points where execution pauses
- **Resumption**: Continuing after human provides input

**HITL Patterns:**

```
Approval:  Agent plans action → Human approves → Action executes
Edit:      Agent drafts email → Human edits → Email sends
Review:    Agent makes decision → Human reviews → Confirm or override
Escalation: Agent uncertain → Escalate to human → Human decides
```

**Practical Skills:**

- Add interrupt points to LangGraph
- Handle human input and resume
- Design UX for human-in-the-loop (what does human see?)
- Decide when HITL is needed vs. autonomous

### Resources

**Primary:**

- LangGraph Human-in-the-Loop: https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/
- LangGraph Breakpoints: https://langchain-ai.github.io/langgraph/how-tos/breakpoints/
- LangGraph Wait for Input: https://langchain-ai.github.io/langgraph/how-tos/wait-user-input/

**Secondary:**

- Search: "langgraph interrupt human in the loop"
- Search: "agent human approval pattern"

### Day 5 Tasks (1 hour)

**First 30 min — Learn:**

1. Read LangGraph human-in-the-loop concepts (15 min)
2. Understand interrupt() and how to wait for human input (10 min)
3. Read about breakpoints and programmatic pausing (5 min)

**Next 30 min — Experiment:**

1. Add a simple interrupt to your agent before a "dangerous" tool (e.g., send_email)
2. Run a query that triggers the tool
3. Verify: Graph pauses, you can inspect state
4. Provide approval, verify execution continues
5. Provide rejection, verify execution takes alternative path

### Day 6 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Add HITL capabilities to your agent:

```python
def create_hitl_agent(tools: list, dangerous_tools: list[str]) -> StateGraph:
    """
    Creates an agent with human-in-the-loop for dangerous operations.
    
    Args:
        tools: All available tools
        dangerous_tools: Names of tools requiring approval
    
    Behavior:
        - If agent wants to call a dangerous tool, pause for approval
        - Show human: what tool, what arguments, why
        - Human can: approve, reject, or edit arguments
        - On approve: execute tool
        - On reject: agent explains and tries alternative
        - On edit: execute with modified arguments
    """
    pass

# Usage
agent = create_hitl_agent(
    tools=[search, calculate, send_email, delete_file],
    dangerous_tools=["send_email", "delete_file"]
)

result = agent.invoke(
    {"messages": [HumanMessage("Email John that the meeting is cancelled")]},
    config={"configurable": {"thread_id": "123"}}
)
# Agent pauses before send_email

# Human reviews
pending = agent.get_pending_approval("123")
# {"tool": "send_email", "args": {"to": "john@...", "body": "..."}, "reason": "User requested"}

# Human approves
agent.approve("123")  # or agent.reject("123") or agent.edit("123", new_args={...})

# Execution continues
```

**Success Criteria:**

- [ ] Dangerous tools trigger approval pause
- [ ] Human can see: tool name, arguments, agent's reasoning
- [ ] Approve path: tool executes, agent continues
- [ ] Reject path: agent acknowledges, tries alternative
- [ ] Edit path: tool executes with modified arguments
- [ ] State persists during pause (can resume even after restart)
- [ ] Timeout handling: what if human never responds?
- [ ] Tested with at least 2 dangerous tools

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Human-in-the-Loop)

1. Every dangerous action requires approval. User triggers 10 actions. They have to approve 10 times. That's annoying. How do you balance safety with usability? (Hint: Batch approvals? Trust levels? Auto-approve similar?)
    
2. Agent wants to "send email to john@company.com about meeting." Human approves. But the agent actually constructs a different email body than expected (hallucination in a different field). Human approved the action but not the content. How do you make approval granular enough?
    
3. Human-in-the-loop requires a human. It's 3 AM, agent needs approval, no one's there. Task fails. How do you handle async approval? What if approval takes days?
    
4. You categorize tools as "dangerous." But danger is context-dependent. "Delete file" is dangerous. "Delete temp file agent just created" is fine. How do you make danger assessment context-aware?
    
5. Agent pauses for approval. Human sees the plan. Human has a better idea: "Don't email John, call him instead." But "call" isn't a tool. How do you handle human suggestions that go beyond approve/reject/edit?
    

---

## Day 7 (Agents): Mini Build — Agent with Memory + Checkpointing

### What to Build

A production-ready agent that demonstrates:

- Persistent state (survives restarts)
- Memory across conversations
- Human-in-the-loop for sensitive operations

### Specifications

```python
from smart_agent import SmartAgent

# Initialize with persistence
agent = SmartAgent(
    model="gpt-4o-mini",
    tools=[search, calculate, send_email, save_note, get_notes],
    dangerous_tools=["send_email"],
    persistence="sqlite",  # "memory" or "sqlite" or "postgres"
    memory_config={
        "max_messages": 20,
        "summarize": True,
        "extract_entities": True
    }
)

# Conversation with memory
result = agent.run(
    "Hi, I'm John from Acme Corp",
    thread_id="user_123"
)

result = agent.run(
    "What company did I say I'm from?",
    thread_id="user_123"
)
# Agent remembers: "You mentioned you're from Acme Corp"

# Dangerous action triggers HITL
result = agent.run(
    "Email sarah@acme.com that John will be late",
    thread_id="user_123"
)
# Returns: {"status": "pending_approval", "action": {...}}

# Approve and continue
agent.approve(thread_id="user_123")
result = agent.get_result(thread_id="user_123")

# Resume after restart
# (restart Python process)
agent = SmartAgent(...)  # Same config
result = agent.run(
    "What did we just do?",
    thread_id="user_123"
)
# Agent remembers: "We sent an email to Sarah about John being late"

# Memory search
memories = agent.search_memories("Acme Corp", thread_id="user_123")
```

### Success Criteria

- [ ] Persistent state: survives Python restart
- [ ] Memory: remembers entities, facts, preferences from earlier in conversation
- [ ] Summarization: handles 30+ message conversations
- [ ] HITL: dangerous tools require approval
- [ ] Multiple threads: isolated conversations
- [ ] Semantic search: find relevant past memories
- [ ] Full conversation flow: multi-turn, tools, approvals, memory
- [ ] Tested: Kill process mid-conversation, resume cleanly
- [ ] Tested: 3 different threads, verify isolation

### Things to Ponder (Post-Build)

1. You have memory (remember past), state (current session), and checkpoints (resume capability). How do these three interact? What's the data flow between them?
    
2. Your agent runs for 1000 users. Each has memory. Storage grows. Cost grows. How do you handle memory at scale? Archiving? Compression? Deletion policies?
    
3. User says "Forget that I mentioned Acme Corp." How do you handle memory deletion requests? Is it truly forgotten or just hidden? What about compliance (GDPR)?
    
4. Your agent with HITL is deployed in a web app. How does the UX work? Websockets for real-time approval? Polling? Email notification? What's the architecture?
    
5. You've built a sophisticated agent. But debugging is hard. Something went wrong in a 50-step conversation with 3 tool calls, 2 approvals, and memory. How do you trace what happened? (Preview: Week 8 observability)
    

---

# WEEK 5 CHECKLIST

## RAG Track Completion Criteria

- [ ] **Hybrid Search:** Can combine BM25 + dense retrieval, understand when each helps
- [ ] **Reranking:** Can integrate cross-encoder, understand the two-stage pattern
- [ ] **Query Transformation:** Can implement HyDE/expansion/rewriting, know when to use each
- [ ] **Mini Build:** RAG v2 with measurably better retrieval than v1

## Agent Track Completion Criteria

- [ ] **State Management:** Can persist state, checkpoint, resume after crash
- [ ] **Memory Systems:** Can implement conversation, summary, entity memory
- [ ] **Human-in-the-Loop:** Can add approval flows for dangerous operations
- [ ] **Mini Build:** Agent with full memory + HITL capabilities

## What's Next

**Week 6:**

- **RAG Track:** RAG Evaluation — metrics, debugging bad retrieval, systematic improvement
- **Agent Track:** Multi-agent patterns — orchestrator, supervisor, peer collaboration; agent evaluation

---

# NOTES SECTION

## RAG Track Notes

### Days 1-2 Notes (Hybrid Search)

### Days 3-4 Notes (Reranking)

### Days 5-6 Notes (Query Transformation)

### Day 7 Notes (RAG v2 Mini Build)

---

## Agent Track Notes

### Days 1-2 Notes (State Management)

### Days 3-4 Notes (Memory Systems)

### Days 5-6 Notes (Human-in-the-Loop)

### Day 7 Notes (Agent Mini Build)