# Entity Extraction and Storage

## What Are Entities in Agent Memory?

Entities are the meaningful pieces of information worth remembering: people, places, preferences, relationships, facts. When a user says "I work at Acme Corp with Alice, who manages the ML team," the entities are:

- **Person:** Alice
- **Organization:** Acme Corp
- **Role:** Alice manages the ML team
- **Relationship:** User works with Alice

Entity extraction is the process of identifying these pieces; storage is where and how you persist them for later retrieval.

> **Scope clarification:** This note covers extraction mechanics and storage patterns. Semantic search over stored entities is covered in Note 5. Namespace organization is covered in Note 6.

---

## Extraction Approaches

### 1. LLM-Based Extraction (Primary Approach)

Use an LLM to extract entities from conversation text. This is flexible and handles natural language well.

**Basic pattern:**

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("claude-sonnet-4-6")

extraction_prompt = """Extract all important entities from this conversation.
For each entity, identify:
- Type (person, organization, preference, fact, relationship)
- Name/subject
- Details

Conversation:
{conversation}

Return as JSON list."""

response = model.invoke(extraction_prompt.format(conversation=text))
# Parse and store the extracted entities
```

**Structured output with Pydantic:**

```python
from pydantic import BaseModel, Field
from typing import Literal

class Entity(BaseModel):
    """An extracted entity from conversation."""
    entity_type: Literal["person", "organization", "preference", "fact", "relationship"]
    name: str = Field(description="Entity name or subject")
    details: str = Field(description="Additional context")
    confidence: float = Field(description="Extraction confidence 0-1")

# Use structured output
entities = model.with_structured_output(list[Entity]).invoke(prompt)
```

### 2. Knowledge Triple Extraction

A common pattern: extract (subject, predicate, object) triples.

```python
from pydantic import BaseModel, Field

class Triple(BaseModel):
    """A knowledge triple representing a fact."""
    subject: str = Field(description="The entity this fact is about")
    predicate: str = Field(description="The relationship or attribute")
    object: str = Field(description="The value or related entity")
    context: str | None = Field(default=None, description="When/where this is true")

# Example extractions:
# "Alice manages the ML team" → ("Alice", "manages", "ML team")
# "User prefers dark mode" → ("User", "prefers", "dark mode")
# "Bob joined in 2023" → ("Bob", "joined", "2023", context="employment start")
```

Triples are useful because:

- They're composable: multiple triples build a knowledge graph
- They're searchable: find all facts about a subject
- They're updatable: replace specific predicates without affecting others

### 3. Named Entity Recognition (NER)

Traditional NER identifies entity spans (person names, organizations, locations) but doesn't capture relationships. Use as a supplement to LLM extraction, not a replacement.

```python
import spacy

nlp = spacy.load("en_core_web_sm")
doc = nlp("Alice from Acme Corp met Bob in San Francisco.")

for ent in doc.ents:
    print(f"{ent.text}: {ent.label_}")
# Alice: PERSON
# Acme Corp: ORG
# Bob: PERSON
# San Francisco: GPE
```

**When to use NER:**

- High-volume extraction where LLM costs matter
- Extracting simple entity mentions (names, places)
- Pre-filtering text before LLM extraction

**When to use LLM extraction:**

- Capturing relationships between entities
- Extracting preferences and abstract facts
- Handling context-dependent meaning

---

## LangMem: The Extraction Toolkit

LangMem provides batteries-included extraction via `create_memory_manager`.

### Basic Usage

```python
from langmem import create_memory_manager

manager = create_memory_manager(
    "anthropic:claude-3-5-sonnet-latest",
    instructions="Extract all noteworthy facts about the user.",
    enable_inserts=True,  # Can add new memories
)

conversation = [
    {"role": "user", "content": "I work at Acme Corp in the ML team"},
    {"role": "assistant", "content": "That's great! What kind of ML work do you do?"},
    {"role": "user", "content": "Mostly NLP and large language models"}
]

memories = manager.invoke({"messages": conversation})
# Returns list of ExtractedMemory objects
```

### Custom Schemas

Define exactly what structure you want extracted:

```python
from pydantic import BaseModel, Field
from langmem import create_memory_manager

class UserPreference(BaseModel):
    """A user preference."""
    category: str = Field(description="Type of preference")
    value: str = Field(description="The preference value")
    importance: str = Field(description="How important: low/medium/high")

class Relationship(BaseModel):
    """A relationship between entities."""
    person1: str
    person2: str
    relationship_type: str
    context: str | None = None

manager = create_memory_manager(
    "anthropic:claude-3-5-sonnet-latest",
    schemas=[UserPreference, Relationship],  # Custom schemas
    instructions="Extract user preferences and any relationships mentioned.",
    enable_inserts=True,
    enable_deletes=True,  # Can mark memories as obsolete
)
```

### Memory Enrichment (Reconciliation)

When extracting from ongoing conversations, new information may conflict with existing memories:

```python
# First conversation
conversation1 = [
    {"role": "user", "content": "I work at Acme Corp"}
]
memories = manager.invoke({"messages": conversation1})
# Extracts: "User works at Acme Corp"

# Later conversation
conversation2 = [
    {"role": "user", "content": "I just started at BigTech Inc!"}
]

# Pass existing memories for reconciliation
updated = manager.invoke({
    "messages": conversation2,
    "existing": memories  # Manager sees existing memories
})
# Manager decides: delete old memory, create new one
```

LangMem prompts the LLM to:

1. Compare new information against existing memories
2. Decide whether to INSERT, UPDATE, or DELETE
3. Return the reconciled memory set

---

## Storage Patterns

### LangGraph Store API

LangGraph's `BaseStore` provides the storage primitive:

```python
from langgraph.store.memory import InMemoryStore

# Initialize with embedding config for semantic search
store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": "openai:text-embedding-3-small",
    }
)

# Store operations
namespace = ("user_123", "memories")

# PUT: Store an entity
store.put(
    namespace,
    "mem_001",  # Unique key
    {
        "type": "preference",
        "content": "User prefers dark mode",
        "extracted_at": "2025-03-15T10:00:00Z"
    }
)

# GET: Retrieve by key
item = store.get(namespace, "mem_001")
# Returns: Item(namespace=[...], key="mem_001", value={...}, ...)

# SEARCH: Find memories (with optional semantic search)
results = store.search(
    namespace,
    query="What display settings does the user like?",  # Semantic
    filter={"type": "preference"},  # Metadata filter
    limit=5
)
```

### Production Storage Options

|Store|Use Case|Persistence|
|---|---|---|
|`InMemoryStore`|Development, testing|None (lost on restart)|
|`SqliteSaver`|Local persistence|File-based|
|`PostgresStore`|Production|Database|
|`AsyncPostgresStore`|High-throughput production|Async database|

```python
from langgraph.store.postgres import PostgresStore
from langchain.embeddings import init_embeddings

store = PostgresStore(
    connection_string="postgresql://user:pass@localhost:5432/dbname",
    index={
        "dims": 1536,
        "embed": init_embeddings("openai:text-embedding-3-small"),
        "fields": ["content"],  # Which fields to embed
    }
)
store.setup()  # Run migrations once
```

### Storing Extracted Entities

Combine extraction with storage:

```python
from langmem import create_memory_store_manager
from langgraph.store.memory import InMemoryStore
from pydantic import BaseModel, Field

class Triple(BaseModel):
    subject: str
    predicate: str
    object: str

store = InMemoryStore(
    index={"dims": 1536, "embed": "openai:text-embedding-3-small"}
)

# Store manager handles extraction AND persistence
manager = create_memory_store_manager(
    "anthropic:claude-3-5-sonnet-latest",
    namespace=("user", "{user_id}", "facts"),  # Dynamic namespace
    schemas=[Triple],
    instructions="Extract facts as knowledge triples.",
    enable_inserts=True,
    enable_deletes=True,
)

# Usage in a graph node
from langgraph.func import entrypoint

@entrypoint(store=store)
def extract_and_store(messages: list, config):
    # Manager automatically:
    # 1. Extracts triples from messages
    # 2. Reconciles with existing memories in namespace
    # 3. Stores results in the configured store
    manager.invoke({"messages": messages}, config=config)
```

---

## Hot Path vs Background Extraction

### Hot Path (During Conversation)

Agent extracts memories in real-time via tool calls:

```python
from langmem import create_manage_memory_tool, create_search_memory_tool
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore

store = InMemoryStore(
    index={"dims": 1536, "embed": "openai:text-embedding-3-small"}
)

agent = create_react_agent(
    "anthropic:claude-3-5-sonnet-latest",
    tools=[
        create_manage_memory_tool(namespace=("memories", "{user_id}")),
        create_search_memory_tool(namespace=("memories", "{user_id}")),
    ],
    store=store,
)

# Agent decides when to save memories
agent.invoke(
    {"messages": [{"role": "user", "content": "Remember that I prefer Python over JavaScript"}]},
    config={"configurable": {"user_id": "user_123"}}
)
```

**Pros:**

- Immediate: memories available in same conversation
- Agent control: decides what's important

**Cons:**

- Latency: extraction adds to response time
- Reliability: agent might forget to save

### Background Extraction (After Conversation)

Extract memories asynchronously after the conversation:

```python
from langgraph.func import entrypoint
from langchain.chat_models import init_chat_model
from langmem import create_memory_store_manager

# Main conversation agent
@entrypoint(store=store)
def conversation_agent(messages: list):
    response = llm.invoke(messages)
    return response

# Background memory extraction (runs separately)
@entrypoint(store=store)
def extract_memories(messages: list, config):
    manager = create_memory_store_manager(
        "anthropic:claude-3-5-sonnet-latest",
        namespace=("memories", "{user_id}"),
        instructions="Extract important facts and preferences.",
        enable_inserts=True,
    )
    manager.invoke({"messages": messages}, config=config)

# Usage:
# 1. Conversation completes
# 2. Trigger extraction asynchronously (queue, cron, etc.)
```

**Pros:**

- No latency impact on conversation
- Batch processing possible
- Higher recall (dedicated extraction pass)

**Cons:**

- Delay: memories not available until extraction runs
- Complexity: need async infrastructure

### When to Use Which

|Scenario|Approach|
|---|---|
|Critical info needed immediately|Hot path|
|Preferences that improve next response|Hot path|
|Building long-term user profiles|Background|
|High-volume conversations|Background|
|Episodic memory (session summaries)|Background|

---

## Practical Patterns

### Pattern 1: Extract on Every Turn

```python
def chat_with_extraction(state, store, config):
    # Get response first
    response = llm.invoke(state["messages"])
    
    # Extract in background (non-blocking in production)
    extract_memories(state["messages"] + [response], store, config)
    
    return {"messages": [response]}
```

### Pattern 2: Extract on Conversation End

```python
def on_conversation_end(thread_id: str, store, config):
    # Fetch full conversation from checkpointer
    conversation = get_conversation_history(thread_id)
    
    # Extract all memories at once
    manager.invoke({"messages": conversation}, config=config)
```

### Pattern 3: Incremental Extraction with Windowing

```python
def incremental_extract(state, store, config):
    # Only extract from recent messages (not full history)
    recent = state["messages"][-6:]  # Last 3 turns
    
    # Get existing memories for reconciliation
    existing = store.search(
        ("memories", config["configurable"]["user_id"]),
        limit=20
    )
    
    manager.invoke({
        "messages": recent,
        "existing": [item.value for item in existing]
    }, config=config)
```

---

## Key Decisions for Your System

1. **What to extract?**
    
    - Preferences (dark mode, communication style)
    - Facts (works at Acme, speaks Spanish)
    - Relationships (Alice is Bob's manager)
    - Events (completed project X last week)
2. **Schema: Structured vs Unstructured?**
    
    - Pydantic schemas for predictable entity types
    - Free-form text for diverse/unknown entities
    - Triples as a middle ground
3. **When to extract?**
    
    - Hot path for critical, immediate use
    - Background for comprehensive, non-urgent
4. **How to reconcile conflicts?**
    
    - Latest wins (simple)
    - LLM reconciliation (LangMem default)
    - Timestamped versioning (audit trail)

---

## Key Takeaways

1. **LLM extraction is the primary approach.** NER supplements but doesn't replace it for capturing relationships and context.
    
2. **Pydantic schemas enforce structure.** Define what you want extracted; the LLM fills in the values.
    
3. **Triples are a powerful primitive.** (subject, predicate, object) composes into knowledge graphs.
    
4. **LangGraph Store provides the storage layer.** `put()`, `get()`, `search()` with namespace organization.
    
5. **LangMem adds extraction logic.** `create_memory_manager` for extraction; `create_memory_store_manager` for extraction + persistence.
    
6. **Hot path vs background is a latency/immediacy trade-off.** Choose based on whether memories need to be available in the same conversation.
    
7. **Reconciliation matters.** New information may conflict with existing memories—your system needs a strategy.
    

---

## References

- LangMem SDK Documentation: https://langchain-ai.github.io/langmem/
- LangMem `create_memory_manager`: https://langchain-ai.github.io/langmem/reference/memory/
- LangGraph Store Persistence: https://github.com/langchain-ai/langgraph/blob/main/docs/docs/concepts/persistence.md
- LangGraph Long-term Memory: https://docs.langchain.com/oss/python/langchain/long-term-memory
- Semantic Search for LangGraph Memory: https://blog.langchain.com/semantic-search-for-langgraph-memory/