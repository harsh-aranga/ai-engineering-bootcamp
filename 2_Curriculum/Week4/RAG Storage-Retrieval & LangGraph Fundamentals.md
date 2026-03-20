# Week 4: Parallel Tracks — RAG Storage & Retrieval + LangGraph Fundamentals

> **Track:** Parallel (RAG + Agents) **Time:** 2 hours/day (1 hour RAG + 1 hour Agents) **Goal:** Build a working RAG system with vector storage and retrieval. Transition from raw agent code to structured LangGraph workflows.

---

## Overview

### RAG Track (1 hour/day)

| Days | Topic               | Output                         |
| ---- | ------------------- | ------------------------------ |
| 1-2  | Vector Stores       | ChromaDB working locally       |
| 3-4  | Indexing Strategies | Mini Challenge complete        |
| 5-6  | Basic Retrieval     | Mini Challenge complete        |
| 7    | Mini Build          | Working RAG v1 (Q&A over docs) |

### Agent Track (1 hour/day)

|Days|Topic|Output|
|---|---|---|
|1-2|LangGraph Fundamentals|Basic graph running|
|3-4|Agent Loop in LangGraph|Mini Challenge complete|
|5-6|Conditional Logic & Routing|Mini Challenge complete|
|7|Mini Build|LangGraph Agent with 3+ Tools|

---

# RAG TRACK

---

## Days 1-2 (RAG): Vector Stores

### Why This Matters

You have chunks. Now you need to store them somewhere that enables fast similarity search across millions of vectors. Vector stores are purpose-built for this:

- Regular databases: exact match on fields
- Vector databases: "find me the 10 most similar vectors to this query"

Without understanding vector stores, you'll treat them as magic boxes and fail when:

- Retrieval is slow (wrong index type)
- Results are wrong (embedding mismatch)
- Storage costs explode (wrong dimensionality choices)

### What to Learn

**Core Concepts:**

- What vector databases do differently from traditional DBs
- Embeddings storage: vectors + metadata
- Similarity search: approximate nearest neighbor (ANN) algorithms
- Index types: flat (exact), HNSW (fast approximate), IVF (clustered)
- Distance metrics: cosine, euclidean, dot product (and when each matters)
- Collections/indexes: organizing vectors into logical groups

**Vector Store Landscape:**

- **ChromaDB** — Local, simple, great for learning and prototypes
- **Pinecone** — Managed, scalable, production-ready
- **Qdrant** — Open-source, feature-rich, self-hostable
- **Weaviate** — Open-source, supports hybrid search natively
- **pgvector** — Postgres extension, good if you're already on Postgres

**Practical Skills:**

- Set up ChromaDB locally
- Create collections, add vectors, query them
- Understand the tradeoffs between different stores

### Resources

**Primary:**

- ChromaDB Documentation: https://docs.trychroma.com/
- ChromaDB Getting Started: https://docs.trychroma.com/getting-started
- Pinecone Learning Center (conceptual): https://www.pinecone.io/learn/

**Secondary:**

- Search: "HNSW algorithm explained" — understand how approximate search works
- Search: "vector database comparison 2024" — see the landscape

### Day 1 Tasks (1 hour)

**First 30 min — Learn:**

1. Read ChromaDB getting started guide (15 min)
2. Understand: collection, embedding, document, metadata, query (10 min)
3. Read about distance metrics — when to use cosine vs. others (5 min)

**Next 30 min — Experiment:**

1. Install ChromaDB: `pip install chromadb`
2. Create a collection
3. Add 10 documents with embeddings (use OpenAI or sentence-transformers)
4. Query with a test question — see what comes back
5. Inspect the results: What's the similarity score? Does it make sense?

### Day 2 Tasks (1 hour)

**First 30 min — Deepen:**

1. Read about ChromaDB persistence — how to save/load collections (10 min)
2. Read about metadata filtering — query vectors AND filter by metadata (10 min)
3. Explore other vector stores conceptually — skim Pinecone/Qdrant docs (10 min)

**Next 30 min — Experiment:**

1. Create a persistent ChromaDB (survives restarts)
2. Add documents with metadata: `{"source": "file.pdf", "page": 1, "category": "technical"}`
3. Query with metadata filter: "find similar vectors WHERE category = technical"
4. Test: Add same document twice — what happens? How do you handle duplicates?

### 5 Things to Ponder (Vector Stores)

1. You store 1 million vectors of 1536 dimensions (OpenAI ada-002). Each dimension is a 32-bit float. How much storage is that? Now consider 3072 dimensions (text-embedding-3-large). What's the cost implication?
    
2. ChromaDB uses HNSW index by default (approximate nearest neighbor). This means results are fast but might miss the true top-k. When would this approximation be acceptable? When would you need exact search?
    
3. You have vectors from two different embedding models in the same collection (by accident). Query results are garbage. Why? How would you prevent this?
    
4. Your collection has 100K vectors. Queries take 50ms. Fine. Now it has 10M vectors. Queries take 500ms. What changed? What are your options to speed it up?
    
5. You store document chunks with metadata `{"date": "2024-01-15"}`. User asks: "What happened last week?" You need to filter by date, but "last week" is relative. Where does this date interpretation happen — in the vector store or before querying?
    

---

## Days 3-4 (RAG): Indexing Strategies

### Why This Matters

Indexing is how your chunks become searchable. Done wrong:

- You re-embed everything on every update (expensive)
- Duplicates pile up (wasted storage, confusing results)
- Updates don't reflect (stale data)
- Indexing takes forever (blocking your pipeline)

Good indexing strategy = efficient, incremental, deduplicated, fast.

### What to Learn

**Core Concepts:**

- Batch indexing vs. incremental indexing
- Document IDs: deterministic vs. random, deduplication
- Embedding at index time: when and how
- Index updates: add, update, delete
- Index maintenance: compaction, reindexing

**Practical Skills:**

- Design an indexing pipeline that handles updates
- Generate deterministic IDs for deduplication
- Batch embed for efficiency
- Handle failures gracefully (partial indexing)

### Resources

**Primary:**

- ChromaDB Collection Methods: https://docs.trychroma.com/reference/Collection
- LlamaIndex Ingestion Pipeline: https://docs.llamaindex.ai/en/stable/module_guides/loading/ingestion_pipeline/
- OpenAI Embeddings Batching: https://platform.openai.com/docs/guides/embeddings/how-to-get-embeddings

**Secondary:**

- Search: "RAG indexing best practices"
- Search: "document deduplication strategies"

### Day 3 Tasks (1 hour)

**First 30 min — Learn:**

1. Read ChromaDB collection methods — understand add, update, upsert, delete (15 min)
2. Think about IDs: If you add the same chunk twice, should it create two entries or update one? (10 min)
3. Read about batch embedding — sending multiple texts in one API call (5 min)

**Next 30 min — Experiment:**

1. Create a function that generates deterministic IDs from content (hash-based)
2. Add 5 chunks, note their IDs
3. Add the same 5 chunks again — verify no duplicates (upsert behavior)
4. Update one chunk's content — verify the change reflects in queries

### Day 4 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build an `Indexer` class:

```python
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
        pass
    
    def index_chunks(self, chunks: list[dict]) -> dict:
        """
        Index chunks with deduplication.
        
        Args:
            chunks: List of {"content": str, "metadata": dict}
        
        Returns:
            {"indexed": int, "skipped_duplicates": int, "errors": int}
        """
        pass
    
    def delete_by_source(self, source: str) -> int:
        """Delete all chunks from a specific source file."""
        pass
    
    def reindex_source(self, source: str, chunks: list[dict]) -> dict:
        """Delete old chunks from source and index new ones."""
        pass
```

**Success Criteria:**

- [ ] Generates deterministic IDs (same content = same ID)
- [ ] Batches embedding calls (doesn't call API once per chunk)
- [ ] Handles duplicates via upsert (no duplicate entries)
- [ ] `delete_by_source` removes all chunks with matching source metadata
- [ ] `reindex_source` atomically replaces old with new
- [ ] Returns useful stats (how many indexed, skipped, errored)
- [ ] Handles API errors gracefully (doesn't crash on rate limit)
- [ ] Tested with 50+ chunks from your Week 3 document processor

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Indexing)

1. You generate chunk IDs by hashing content. User updates a typo in a document — one character changes. Now it's a "new" chunk with a new ID. Old chunk orphaned. How would you handle document updates cleanly?
    
2. You batch 100 chunks per embedding call. Call fails on chunk #47 (content filter triggered). Do you: (A) fail the whole batch, (B) skip just #47, (C) retry with smaller batch? What are the tradeoffs?
    
3. You're indexing 100,000 documents. Estimated time: 4 hours. Midway, your script crashes. You restart — does it re-index everything or resume? How would you design for resumability?
    
4. Your indexer is synchronous — it blocks until done. User uploads a 500-page PDF. They wait 2 minutes staring at a spinner. How would you make this async/background? What feedback would you give the user?
    
5. You have documents in the index. You upgrade your embedding model (old: ada-002, new: text-embedding-3-large). Old vectors are incompatible with new. How do you migrate? What's the cost? Can you do it incrementally?
    

---

## Days 5-6 (RAG): Basic Retrieval

### Why This Matters

Retrieval is where RAG succeeds or fails. You can have perfect chunks, perfect embeddings, perfect storage — but if retrieval returns irrelevant content, the LLM will give wrong answers confidently.

This is also where you connect the pieces: query → embed → search → retrieve → augment prompt → generate.

### What to Learn

**Core Concepts:**

- Query embedding: same model as document embedding
- Top-k retrieval: how many chunks to retrieve
- Similarity thresholds: minimum score to include
- Context assembly: how to format retrieved chunks for the LLM
- The generation step: prompt structure with retrieved context

**Practical Skills:**

- Implement the full retrieval → generation pipeline
- Tune top-k for your use case
- Format context effectively
- Handle "no relevant results" gracefully

### Resources

**Primary:**

- ChromaDB Query: https://docs.trychroma.com/reference/Collection#query
- OpenAI Cookbook RAG Example: https://cookbook.openai.com/examples/question_answering_using_embeddings
- LangChain RAG Tutorial: https://python.langchain.com/docs/tutorials/rag/

**Secondary:**

- Search: "RAG prompt template best practices"
- Search: "top-k retrieval optimization"

### Day 5 Tasks (1 hour)

**First 30 min — Learn:**

1. Read ChromaDB query documentation — understand parameters (15 min)
2. Study a RAG prompt template — how is retrieved context formatted? (10 min)
3. Think: What happens when top-k returns irrelevant chunks? How would you detect this? (5 min)

**Next 30 min — Experiment:**

1. Using your indexed documents, write a simple retrieval function
2. Test with 5 different queries — examine what's retrieved
3. Try different top-k values (1, 3, 5, 10) — see how results change
4. Look at similarity scores — what's the range? What score indicates "relevant"?

### Day 6 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Build a `SimpleRAG` class:

```python
class SimpleRAG:
    def __init__(
        self,
        collection_name: str,
        llm_model: str = "gpt-4o-mini",
        top_k: int = 5
    ):
        """
        Simple RAG implementation: retrieve and generate.
        """
        pass
    
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
        pass
    
    def query_with_history(
        self, 
        question: str, 
        conversation_history: list[dict]
    ) -> dict:
        """Answer considering conversation history."""
        pass
```

**Success Criteria:**

- [ ] Retrieves top-k relevant chunks for a question
- [ ] Formats context into a clear prompt for the LLM
- [ ] LLM generates answer based on retrieved context
- [ ] Returns sources with scores (for transparency)
- [ ] Handles "no relevant results" — doesn't hallucinate, admits uncertainty
- [ ] `query_with_history` incorporates previous Q&A for follow-up questions
- [ ] Tracks token usage
- [ ] Tested with at least 10 questions — verify answers are grounded in retrieved content

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Retrieval)

1. You retrieve top-5 chunks. Chunk #3 has score 0.92, chunks #4 and #5 have scores 0.45 and 0.41. Should you include #4 and #5? They might add noise. How would you set a threshold, and should it be static or dynamic?
    
2. User asks: "What did John say about the project?" Your retrieval finds chunks mentioning "John" and chunks about "the project" — but maybe not the specific intersection. How does embedding-based retrieval handle this kind of conjunctive query?
    
3. You format retrieved chunks as: `Context:\n{chunk1}\n{chunk2}\n{chunk3}`. The LLM ignores chunk2 entirely (lost in the middle). How would you restructure the prompt to ensure all chunks get attention?
    
4. User asks a question. You retrieve 5 chunks. Together they use 2000 tokens. Your context window is 4096. System prompt is 500. Question is 50. Response budget is 500. You're at 3050/4096. What if retrieval returned 8 relevant chunks at 3500 tokens? How do you decide what to keep?
    
5. Your RAG answers: "According to the documents, X is true." But the user's documents actually said "X is false" — the LLM hallucinated despite having correct context. How do you detect and prevent this?
    

---

## Day 7 (RAG): Mini Build — Working RAG v1

### What to Build

A complete, end-to-end RAG system that combines everything from Weeks 3-4:

- Document processing (Week 3)
- Vector storage and indexing (Week 4 Days 1-4)
- Retrieval and generation (Week 4 Days 5-6)

### Specifications

```python
from rag_system import RAGSystem

# Initialize
rag = RAGSystem(
    collection_name="my_docs",
    embedding_model="text-embedding-3-small",
    llm_model="gpt-4o-mini"
)

# Index documents
stats = rag.index_directory("./documents/", file_types=[".pdf", ".md", ".txt"])
print(stats)  # {"files": 15, "chunks": 342, "indexed": 342}

# Query
result = rag.query("What is the refund policy?")
print(result["answer"])
print(result["sources"])  # List of source chunks with metadata

# Follow-up (with history)
result = rag.query("How long do I have?", history=[
    {"role": "user", "content": "What is the refund policy?"},
    {"role": "assistant", "content": result["answer"]}
])

# Stats
print(rag.get_stats())  # {"total_chunks": 342, "total_queries": 2, "avg_retrieval_time_ms": 45}
```

### Success Criteria

- [ ] End-to-end pipeline: raw documents → answers
- [ ] Uses your Week 3 document processor
- [ ] Uses your Week 4 indexer
- [ ] Uses your Week 4 retrieval + generation
- [ ] Handles multiple file types (PDF, markdown, text minimum)
- [ ] Conversation history for follow-up questions
- [ ] Returns sources with every answer (transparency)
- [ ] Handles edge cases: empty directory, no relevant results, very long documents
- [ ] Basic stats tracking (queries, timing)
- [ ] Tested on real documents — at least 10 files, 20 queries
- [ ] Code is modular — could swap vector store or LLM without rewriting everything

### Things to Ponder (Post-Build)

1. You built RAG v1. A user complains: "It keeps giving wrong answers." How do you debug this? What's your systematic approach to find whether the problem is chunking, indexing, retrieval, or generation?
    
2. Your RAG works great on your test documents. Client gives you their documents — suddenly quality drops. What might be different about their documents? How would you diagnose?
    
3. You're using OpenAI embeddings ($0.00002 per 1K tokens). You have 1M chunks averaging 200 tokens each. What's the embedding cost? Now imagine reindexing weekly. What's the annual cost? When does this matter?
    
4. Your RAG answers based on retrieved context. But the answer requires reasoning across multiple chunks — synthesis, not just extraction. Does your current approach handle this? What's missing?
    
5. You want to add this RAG to a web app with 100 users. They each have their own documents. How would you handle multi-tenancy? Separate collections? Metadata filtering? What are the tradeoffs?
    

---

# AGENT TRACK

---

## Days 1-2 (Agents): LangGraph Fundamentals

### Why This Matters

Week 3 you built agents with raw code — managing the loop, parsing function calls, tracking state manually. It worked, but:

- Adding new tools requires touching loop logic
- State management is ad-hoc
- Debugging is hard (what happened at each step?)
- Complex flows (branching, retries) become spaghetti

LangGraph gives you structure: nodes (actions), edges (transitions), state (data flow). It's the difference between scripting and engineering.

### What to Learn

**Core Concepts:**

- **Graph**: The overall workflow structure
- **Nodes**: Individual steps (functions that do something)
- **Edges**: Connections between nodes (what happens next)
- **State**: Data that flows through the graph (like a shared blackboard)
- **Conditional edges**: Branching based on state or output
- **Entry/exit points**: Where the graph starts and ends

**Why Graph-Based:**

- Visualizable: You can see the flow
- Debuggable: Trace execution through nodes
- Modular: Add/remove nodes without touching others
- Resumable: Checkpoint state, continue later

### Resources

**Primary:**

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- LangGraph Quickstart: https://langchain-ai.github.io/langgraph/tutorials/introduction/
- LangGraph Concepts: https://langchain-ai.github.io/langgraph/concepts/

**Secondary:**

- Search: "langgraph tutorial 2024"
- LangChain YouTube channel — LangGraph videos

### Day 1 Tasks (1 hour)

**First 30 min — Learn:**

1. Read LangGraph quickstart tutorial (20 min)
2. Understand the core concepts: StateGraph, nodes, edges, State (10 min)

**Next 30 min — Experiment:**

1. Install: `pip install langgraph langchain-openai`
2. Create simplest possible graph: one node that just returns "Hello"
3. Add a second node, connect them sequentially
4. Run the graph, see output
5. Add state: pass a message through both nodes, modify it in each

### Day 2 Tasks (1 hour)

**First 30 min — Deepen:**

1. Read about State in LangGraph — TypedDict, annotations, reducers (15 min)
2. Read about conditional edges — branching based on state (15 min)

**Next 30 min — Experiment:**

1. Create a graph with branching: Node A → (if condition) → Node B or Node C
2. Use state to track which branch was taken
3. Try: Input determines the branch (e.g., "positive" goes to B, "negative" goes to C)
4. Visualize your graph (LangGraph has built-in visualization)

### 5 Things to Ponder (LangGraph Fundamentals)

1. Week 3 you built an agent loop with a while loop and if statements. LangGraph uses graphs. What do you gain from the graph abstraction? What do you lose (if anything)?
    
2. State in LangGraph is a TypedDict that flows through nodes. Each node can read and modify it. What happens if two nodes try to modify the same field? How does LangGraph handle this?
    
3. You can visualize LangGraph workflows as diagrams. Why is this valuable? When would you show this diagram to a non-technical stakeholder?
    
4. LangGraph graphs are defined at code time, not runtime. What if you want a dynamic workflow that changes based on user input (add/remove nodes dynamically)? Is this possible? Should it be?
    
5. You have a working raw agent from Week 3. Rewriting it in LangGraph takes time. When is the rewrite worth it? What's the threshold of complexity where framework > raw code?
    

---

## Days 3-4 (Agents): Agent Loop in LangGraph

### Why This Matters

Now you translate your Week 3 raw agent into LangGraph. This teaches you:

- How LangGraph handles the observe-think-act loop
- How tool calling integrates with the graph
- What the framework gives you "for free"

Same functionality, better structure.

### What to Learn

**Core Concepts:**

- **Agent node**: The LLM that decides what to do
- **Tool node**: Executes tools requested by agent
- **Messages state**: Conversation + tool results as state
- **The agent loop as a graph**: Agent → (tool call?) → Tool → Agent → (repeat or end)
- **Built-in helpers**: `create_react_agent` and similar

**Practical Skills:**

- Build the agent-tool loop in LangGraph
- Handle tool results flowing back to agent
- Know when to use built-in helpers vs. custom graphs

### Resources

**Primary:**

- LangGraph ReAct Agent Tutorial: https://langchain-ai.github.io/langgraph/tutorials/introduction/
- LangGraph Tool Calling: https://langchain-ai.github.io/langgraph/how-tos/tool-calling/
- LangGraph Pre-built Agents: https://langchain-ai.github.io/langgraph/concepts/agentic_concepts/

**Secondary:**

- Search: "langgraph react agent example"
- Compare with your Week 3 raw implementation

### Day 3 Tasks (1 hour)

**First 30 min — Learn:**

1. Read LangGraph ReAct agent tutorial (20 min)
2. Understand how tool calling works in LangGraph — the flow (10 min)

**Next 30 min — Experiment:**

1. Take your Week 3 tools (calculator, notes, time, etc.)
2. Define them as LangChain tools (using `@tool` decorator or Tool class)
3. Create a simple agent graph with: agent node → tool node → back to agent
4. Run a query that requires a tool — verify the loop works

### Day 4 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Rebuild your Week 3 agent in LangGraph:

```python
from langgraph.graph import StateGraph, MessagesState

def create_agent_graph(tools: list) -> StateGraph:
    """
    Creates a LangGraph agent with:
    - Agent node (LLM with tool access)
    - Tool execution node
    - Conditional edge: if tool call → tool node, else → end
    - Loop back from tool node to agent node
    
    Returns compiled graph.
    """
    pass

# Usage
graph = create_agent_graph(tools=[calculator, search_notes, save_note, get_time])
result = graph.invoke({"messages": [HumanMessage(content="What's 15% of 230?")]})
```

**Success Criteria:**

- [ ] Graph structure: agent node → conditional → tool node → agent node (loop)
- [ ] Correctly identifies when to end (no more tool calls)
- [ ] All 4 tools from Week 3 work
- [ ] Multi-step tasks work (requires multiple tool calls)
- [ ] Messages state tracks full conversation (human + AI + tool results)
- [ ] Can visualize the graph (use `graph.get_graph().draw_mermaid()`)
- [ ] Handles tool errors gracefully
- [ ] Compared: Is behavior identical to your Week 3 raw agent?

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Agent Loop in LangGraph)

1. LangGraph uses `MessagesState` to track conversation. Your Week 3 agent used a list. What's the difference? What does LangGraph's approach give you?
    
2. In your raw agent, you wrote: `if response.tool_calls: execute_tools()`. In LangGraph, this becomes a conditional edge. The logic is the same — what's the benefit of expressing it as a graph edge?
    
3. LangGraph has `create_react_agent()` helper that builds the graph for you. When would you use the helper vs. building custom? What do you lose with the helper?
    
4. Your graph loops: agent → tool → agent → tool → agent → end. What if max_iterations is hit? How does LangGraph handle infinite loops? How would you add your own safeguard?
    
5. You want to add logging: print every node execution. In raw code, you'd add print statements everywhere. In LangGraph, how would you do this cleanly? (Hint: callbacks, tracing)
    

---

## Days 5-6 (Agents): Conditional Logic & Routing

### Why This Matters

Real agents aren't just loops. They branch:

- "If user is angry, escalate to human"
- "If confidence is low, ask for clarification"
- "If tool failed, try alternative"

Conditional logic turns simple agents into sophisticated workflows.

### What to Learn

**Core Concepts:**

- **Conditional edges**: Route based on state or output
- **Router nodes**: Nodes that decide where to go next
- **Parallel branches**: Multiple paths executed simultaneously
- **Subgraphs**: Nested graphs for complex sub-workflows
- **Error handling**: What happens when a node fails

**Practical Skills:**

- Add branching to your agent
- Implement fallback paths
- Route to different nodes based on LLM classification
- Handle errors with alternative paths

### Resources

**Primary:**

- LangGraph Conditional Edges: https://langchain-ai.github.io/langgraph/how-tos/branching/
- LangGraph Error Handling: https://langchain-ai.github.io/langgraph/how-tos/error-handling/
- LangGraph Human-in-the-Loop: https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/

**Secondary:**

- Search: "langgraph conditional routing"
- Search: "langgraph subgraphs"

### Day 5 Tasks (1 hour)

**First 30 min — Learn:**

1. Read LangGraph conditional edges documentation (15 min)
2. Read about error handling in LangGraph (10 min)
3. Think: Where in your agent would branching be useful? (5 min)

**Next 30 min — Experiment:**

1. Add a conditional to your agent: if query contains "urgent", add priority flag to state
2. Add a branch: if tool fails, try an alternative approach
3. Test both paths — verify routing works

### Day 6 Tasks (1 hour)

**First 30 min — Mini Challenge:**

Extend your agent with smart routing:

```python
def create_smart_agent_graph(tools: list) -> StateGraph:
    """
    Creates an agent with:
    - Intent classification: categorize user query first
    - Conditional routing based on intent:
      - "calculation" → calculator-focused path
      - "search" → search-focused path  
      - "general" → standard agent path
    - Fallback: if primary path fails, try alternative
    - Human escalation: if confidence < threshold, ask for help
    """
    pass
```

**Success Criteria:**

- [ ] Intent classifier node that categorizes incoming queries
- [ ] At least 3 different routes based on intent
- [ ] Fallback mechanism: if primary approach fails, try alternative
- [ ] Confidence check: add a path that says "I'm not sure, please clarify"
- [ ] All paths eventually reach END node (no hanging branches)
- [ ] Visualization shows the branching clearly
- [ ] Tested with queries that hit each branch

**Next 30 min — Solidify + Ponder**

### 5 Things to Ponder (Conditional Logic)

1. Your intent classifier is an LLM call. That's an extra API call before the main agent work. When is this overhead worth it? When would you skip classification and go direct?
    
2. You have 5 specialized paths based on intent. But intent classification can be wrong — user says "calculate" but actually wants search. How do you handle misrouting?
    
3. Your fallback path catches tool failures. But what's the difference between "tool failed due to API error" vs. "tool ran but returned no results"? Should they be handled the same way?
    
4. Human escalation: Agent says "I need human help." In the graph, this is a node. But what actually happens? How does the human provide input? How does the graph continue after?
    
5. Your graph is getting complex: 3 intents × 2 fallback options × human escalation = many paths. How do you test all paths? How do you ensure no edge case leads to a broken state?
    

---

## Day 7 (Agents): Mini Build — LangGraph Agent with Tools

### What to Build

A complete LangGraph agent that demonstrates:

- Structured workflow (not just a loop)
- Tool usage
- Conditional routing
- Error handling

### Specifications

```python
from agent_graph import SmartAgent

agent = SmartAgent(
    model="gpt-4o-mini",
    tools=[calculator, web_search, note_manager, calendar]
)

# Simple query
result = agent.run("What's 25 * 48?")
print(result["response"])  # "25 * 48 = 1200"
print(result["path"])  # ["intent_classifier", "calculator_path", "respond"]

# Complex query (multiple tools)
result = agent.run("Search for today's weather and save it as a note")
print(result["path"])  # ["intent_classifier", "agent", "web_search_tool", "agent", "save_note_tool", "respond"]

# With conversation
result = agent.run("What did I just save?", history=[...])

# Visualization
agent.visualize()  # Displays graph diagram

# Stats
print(agent.get_stats())  # {"queries": 3, "tool_calls": 5, "avg_latency_ms": 450}
```

### Success Criteria

- [ ] Uses LangGraph (not raw loops)
- [ ] Has intent classification or routing
- [ ] At least 4 working tools
- [ ] Handles multi-tool queries
- [ ] Has fallback/error handling path
- [ ] Maintains conversation history
- [ ] Can visualize the graph
- [ ] Tracks stats (queries, tool calls, latency)
- [ ] Clean separation: graph definition separate from tool implementations
- [ ] Tested with at least 10 diverse queries

### Things to Ponder (Post-Build)

1. Compare your Week 3 raw agent and Week 4 LangGraph agent. Lines of code? Debuggability? Ease of adding new tools? What's your verdict on when to use which?
    
2. LangGraph graphs are compiled and static. Your Week 3 agent could dynamically add tools at runtime. Which is better? When would you need dynamic tool addition?
    
3. Your agent has tools. Your RAG has retrieval. What if you gave your agent a "search_documents" tool that uses your RAG? What would that look like? (Preview: Week 7 combined phase)
    
4. LangGraph has checkpointing — save state mid-execution, resume later. When would this be useful? What use cases require long-running, resumable agents?
    
5. You're debugging a failed query. LangGraph provides traces. What information would you want in a trace to quickly identify the problem? (Preview: Week 8 observability)
    

---

# WEEK 4 CHECKLIST

## RAG Track Completion Criteria

- [ ] **Vector Stores:** Can create collections, add/query vectors, understand different stores and tradeoffs
- [ ] **Indexing:** Can batch embed, deduplicate, handle updates, build robust indexing pipeline
- [ ] **Retrieval:** Can implement full retrieval → generation flow, tune top-k, handle edge cases
- [ ] **Mini Build:** Working RAG v1 that answers questions from your documents

## Agent Track Completion Criteria

- [ ] **LangGraph Fundamentals:** Can create graphs with nodes, edges, state; understand the abstraction
- [ ] **Agent Loop:** Can implement agent-tool loop in LangGraph; know the pattern
- [ ] **Conditional Logic:** Can add branching, routing, fallbacks, error handling
- [ ] **Mini Build:** Working LangGraph agent with tools and smart routing

## What's Next

**Week 5:**

- **RAG Track:** Hybrid search (BM25 + vectors), reranking, query transformation — making retrieval much better
- **Agent Track:** State management deep dive, memory systems, human-in-the-loop patterns

---

# NOTES SECTION

## RAG Track Notes

### Days 1-2 Notes (Vector Stores)

### Days 3-4 Notes (Indexing)

### Days 5-6 Notes (Retrieval)

### Day 7 Notes (RAG Mini Build)

---

## Agent Track Notes

### Days 1-2 Notes (LangGraph Fundamentals)

### Days 3-4 Notes (Agent Loop)

### Days 5-6 Notes (Conditional Logic)

### Day 7 Notes (Agent Mini Build)