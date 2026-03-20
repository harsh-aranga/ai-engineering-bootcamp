# Semantic Memory with Vector Search

## Why Keyword/Key-Value Lookup Isn't Enough

In Note 4, we covered entity extraction and basic storage with `put()` and `get()`. But there's a problem:

```python
# Key-value lookup requires knowing the exact key
memory = store.get(("user_123", "memories"), "food_preference")
# Works only if you know the key is "food_preference"

# What if the user asks: "What does the user like to eat?"
# You don't know which key to look up
```

**The gap:** Users ask questions in natural language. Your stored memories have arbitrary keys. How do you find the right memory without knowing the key?

**Semantic search** solves this by matching on _meaning_ rather than exact keys or keywords.

---

## How Semantic Search Works

### The Core Idea

1. **Embed the memory** when storing: Convert text to a vector (list of numbers)
2. **Embed the query** when searching: Convert the question to a vector
3. **Find similar vectors**: Memories with vectors close to the query vector are relevant

```
Memory: "User prefers dark mode"
   ↓ embed
Vector: [0.12, -0.34, 0.56, ...]  (1536 dimensions)

Query: "What display settings does the user like?"
   ↓ embed
Vector: [0.14, -0.31, 0.58, ...]  (similar direction)

Cosine similarity ≈ 0.92 → High relevance!
```

### Why Vectors Capture Meaning

Embedding models are trained so that semantically similar text produces vectors that are close in space:

- "I prefer dark mode" and "User likes dark theme" → vectors point in similar directions
- "I prefer dark mode" and "What's the weather?" → vectors point in different directions

This is why semantic search finds "dark mode" when you ask about "display settings"—the embedding model learned these concepts are related.

---

## LangGraph Store with Semantic Search

LangGraph's `BaseStore` supports semantic search via the `index` configuration.

### Configuring the Index

```python
from langgraph.store.memory import InMemoryStore
from langchain.embeddings import init_embeddings

# Initialize with embedding configuration
store = InMemoryStore(
    index={
        "dims": 1536,                                    # Embedding dimensions
        "embed": init_embeddings("openai:text-embedding-3-small"),  # Embedding model
        "fields": ["text"],                               # Which fields to embed
    }
)
```

**Configuration options:**

- `dims`: Dimension count of your embedding model (1536 for OpenAI text-embedding-3-small)
- `embed`: The embedding model/function
- `fields`: Which fields in your stored documents get embedded (default: entire value)

### Storing with Embeddings

When you `put()` items, they're automatically embedded:

```python
# Store memories - embeddings generated automatically
store.put(
    ("user_123", "memories"), 
    "mem_001",
    {"text": "User prefers dark mode in all applications"}
)

store.put(
    ("user_123", "memories"),
    "mem_002", 
    {"text": "User works as a software engineer at Acme Corp"}
)

store.put(
    ("user_123", "memories"),
    "mem_003",
    {"text": "User enjoys hiking on weekends"}
)
```

### Searching by Meaning

Use `search()` with a `query` parameter:

```python
# Semantic search - finds relevant memories by meaning
results = store.search(
    ("user_123", "memories"),           # Namespace
    query="What are the user's display preferences?",  # Natural language
    limit=3                              # Max results
)

for item in results:
    print(f"Score: {item.score:.2f} | {item.value['text']}")

# Output:
# Score: 0.89 | User prefers dark mode in all applications
# Score: 0.23 | User works as a software engineer at Acme Corp
# Score: 0.15 | User enjoys hiking on weekends
```

The `score` field indicates semantic similarity (higher = more relevant).

### Combining Semantic Search with Filters

You can filter on metadata AND search by meaning:

```python
store.put(
    ("user_123", "memories"),
    "mem_004",
    {
        "text": "User prefers concise responses",
        "type": "preference",
        "category": "communication"
    }
)

# Filter by type, then rank by semantic similarity
results = store.search(
    ("user_123", "memories"),
    query="How should I communicate with the user?",
    filter={"type": "preference"},  # Only search preferences
    limit=5
)
```

---

## Production Setup: PostgresStore

For production, use `PostgresStore` with pgvector:

```python
from langgraph.store.postgres import PostgresStore
from langchain.embeddings import init_embeddings

store = PostgresStore(
    connection_string="postgresql://user:pass@localhost:5432/dbname",
    index={
        "dims": 1536,
        "embed": init_embeddings("openai:text-embedding-3-small"),
        "fields": ["text", "summary"],  # Embed multiple fields
    }
)

# Run migrations once to create tables and enable pgvector
store.setup()
```

**Why PostgresStore for production:**

- **Persistence:** Data survives restarts
- **pgvector:** Efficient vector similarity search
- **Scalability:** Handles large memory stores
- **Transactions:** ACID compliance for reliability

### Async Version for High Throughput

```python
from langgraph.store.postgres import AsyncPostgresStore

async def setup_store():
    store = await AsyncPostgresStore.from_conn_string(
        "postgresql://user:pass@localhost:5432/dbname",
        index={
            "dims": 1536,
            "embed": "openai:text-embedding-3-small",
        }
    )
    await store.setup()
    return store
```

---

## Controlling What Gets Embedded

### Default: Embed the Entire Value

```python
store = InMemoryStore(
    index={"dims": 1536, "embed": embeddings}
)

# The entire JSON value is serialized and embedded
store.put(("docs",), "doc1", {"text": "Hello", "metadata": "extra"})
```

### Specify Fields to Embed

```python
store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": embeddings,
        "fields": ["text"],  # Only embed the "text" field
    }
)

# Only "text" is embedded; "metadata" is stored but not searchable
store.put(("docs",), "doc1", {"text": "Hello", "metadata": "not embedded"})
```

### Override at Put Time

```python
# Use default embedding fields
store.put(("docs",), "doc1", {"text": "Python tutorial"})

# Override: embed a different field for this item
store.put(
    ("docs",), "doc2",
    {"text": "TypeScript guide", "summary": "A quick overview"},
    index=["summary"]  # Embed "summary" instead of default
)

# Skip embedding entirely for this item
store.put(
    ("docs",), "doc3",
    {"text": "System metadata"},
    index=False  # Don't embed, just store
)
```

### Embedding Multiple Fields

Embed multiple aspects of a memory for better recall:

```python
store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": embeddings,
        "fields": ["memory", "emotional_context"],  # Embed both
    }
)

store.put(
    ("user_123", "memories"), "mem1",
    {
        "memory": "Had pizza with friends at Mario's",
        "emotional_context": "felt happy and connected",
        "not_indexed": "other metadata"
    }
)

# Search can match on either embedded field
results = store.search(
    ("user_123", "memories"),
    query="times they felt isolated"  # Matches emotional_context
)
```

---

## Retrieval at Runtime: The Full Pattern

Here's how semantic memory integrates into an agent:

```python
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.store.memory import InMemoryStore
from langchain.chat_models import init_chat_model

# Setup
model = init_chat_model("claude-sonnet-4-6")
store = InMemoryStore(
    index={"dims": 1536, "embed": "openai:text-embedding-3-small"}
)

def chat_with_memory(state: MessagesState, *, store):
    """Retrieve relevant memories and inject into prompt."""
    
    # 1. Get the user's latest message
    user_message = state["messages"][-1].content
    
    # 2. Search for relevant memories
    memories = store.search(
        ("user_123", "memories"),
        query=user_message,
        limit=5
    )
    
    # 3. Format memories for context
    memory_context = "\n".join([
        f"- {m.value.get('text', str(m.value))}" 
        for m in memories 
        if m.score > 0.3  # Only include reasonably relevant memories
    ])
    
    # 4. Build prompt with memory context
    system_prompt = f"""You are a helpful assistant.

Here's what you remember about this user:
{memory_context if memory_context else "No relevant memories found."}

Use this context to personalize your response."""
    
    # 5. Generate response
    messages = [
        {"role": "system", "content": system_prompt},
        *state["messages"]
    ]
    response = model.invoke(messages)
    
    return {"messages": [response]}

# Build graph
builder = StateGraph(MessagesState)
builder.add_node("chat", chat_with_memory)
builder.add_edge(START, "chat")
graph = builder.compile(store=store)
```

### The Runtime Flow

```
User: "What should I have for dinner?"
        ↓
1. Extract query: "What should I have for dinner?"
        ↓
2. Embed query → [0.12, -0.34, 0.56, ...]
        ↓
3. Search store for similar vectors
        ↓
4. Retrieve: "User prefers Italian food" (0.78)
            "User is vegetarian" (0.72)
            "User works at Acme Corp" (0.15) ← filtered out
        ↓
5. Inject into prompt:
   "Here's what you remember:
    - User prefers Italian food
    - User is vegetarian"
        ↓
6. LLM generates personalized response
```

---

## Relevance Scoring and Thresholds

### Understanding Scores

The `score` returned by `search()` is typically cosine similarity (0 to 1):

- **> 0.8:** Very similar, highly relevant
- **0.5 - 0.8:** Related, possibly relevant
- **< 0.5:** Weakly related, likely not relevant

### Threshold Strategies

```python
# Strategy 1: Hard threshold
relevant = [m for m in memories if m.score > 0.5]

# Strategy 2: Top-k with minimum threshold
memories = store.search(namespace, query=query, limit=10)
relevant = [m for m in memories if m.score > 0.3][:5]

# Strategy 3: Dynamic threshold based on distribution
if memories:
    max_score = memories[0].score
    threshold = max_score * 0.7  # Within 70% of best match
    relevant = [m for m in memories if m.score >= threshold]
```

### When Scores Are Low

Low scores across all results usually mean:

- The query is unrelated to stored memories
- The memories don't contain relevant information
- Consider NOT injecting memory context (avoid noise)

```python
memories = store.search(namespace, query=query, limit=5)

if not memories or memories[0].score < 0.3:
    # Don't inject memories - nothing relevant
    memory_context = ""
else:
    memory_context = format_memories(memories)
```

---

## LangGraph Platform Configuration

If deploying to LangGraph Platform, configure via `langgraph.json`:

```json
{
  "store": {
    "index": {
      "embed": "openai:text-embedding-3-small",
      "dims": 1536,
      "fields": ["text", "summary"]
    }
  }
}
```

The platform handles:

- Automatic embedding on `put()`
- Vector indexing
- Efficient `search()` with similarity scoring

---

## Key Trade-offs

### Embedding Model Choice

|Model|Dimensions|Speed|Quality|Cost|
|---|---|---|---|---|
|`text-embedding-3-small`|1536|Fast|Good|Low|
|`text-embedding-3-large`|3072|Slower|Better|Higher|
|`sentence-transformers/all-MiniLM-L6-v2`|384|Very fast|Moderate|Free (local)|

**Rule of thumb:** Start with `text-embedding-3-small`. Move to larger models only if recall is insufficient.

### Latency Considerations

Each `search()` call:

1. Embeds the query (~50-100ms for API, ~10ms local)
2. Searches the vector index (~5-50ms depending on size)

For latency-sensitive applications:

- Cache query embeddings if repeated
- Use local embedding models
- Pre-filter by namespace to reduce search space

### Index Size

- Each memory consumes storage for the embedding vector
- 1536-dim float32 vectors ≈ 6KB each
- 100K memories ≈ 600MB of vector data

pgvector with HNSW indexing keeps search fast even at scale.

---

## Key Takeaways

1. **Semantic search matches meaning, not keywords.** You can find "dark mode preference" by asking about "display settings."
    
2. **Embeddings are the bridge.** Text → Vector → Similarity comparison. Same embedding model for storage and query.
    
3. **LangGraph Store has built-in support.** Configure `index` with `dims`, `embed`, and `fields`.
    
4. **Control what gets embedded.** Use `fields` to specify which parts of your memory documents are searchable.
    
5. **Use score thresholds.** Not all "matches" are relevant. Filter by score to avoid noise.
    
6. **Production = PostgresStore + pgvector.** InMemoryStore for dev, Postgres for prod.
    
7. **The runtime pattern:** Query → Embed → Search → Filter by score → Inject into prompt.
    

---

## References

- Semantic Search for LangGraph Memory: https://blog.langchain.com/semantic-search-for-langgraph-memory/
- LangGraph Memory Documentation: https://docs.langchain.com/oss/python/langgraph/add-memory
- LangMem API Reference: https://langchain-ai.github.io/langmem/reference/memory/
- LangGraph Persistence Concepts: https://github.com/langchain-ai/langgraph/blob/main/docs/docs/concepts/persistence.md
- OpenAI Embeddings: https://platform.openai.com/docs/guides/embeddings