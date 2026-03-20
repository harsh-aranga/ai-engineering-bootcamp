# Note 3: Checkpointer Backends — MemorySaver, SQLite, Postgres

> **Week 5, Days 1-2 — Agent Track** **Topic:** State Management & Checkpointing (3 of 6) **Docs referenced:** LangGraph Persistence docs, langgraph-checkpoint-sqlite PyPI (v3.0.3), langgraph-checkpoint-postgres PyPI (v3.0.4)

---

## The Storage Layer Decision

Note 2 covered _what_ checkpoints are and _when_ they're created. This note covers _where_ they're stored.

LangGraph provides multiple checkpointer implementations. They all implement the same `BaseCheckpointSaver` interface, so you can swap backends without changing your graph code — only the initialization changes.

```
┌─────────────────────────────────────────────────────────────┐
│                     Your LangGraph Code                      │
│         graph.invoke(...), graph.get_state(...)             │
└─────────────────────────────┬───────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ BaseCheckpointSaver│
                    │     Interface      │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   MemorySaver          SqliteSaver          PostgresSaver
   (in-memory)          (file-based)         (database)
```

---

## MemorySaver: Development Only

**Package:** Included in `langgraph` (no extra install)

**What it is:** Stores checkpoints in a Python dictionary in RAM. Fast, zero setup, but everything disappears when the process exits.

### When to Use

- Quick prototyping
- Unit tests
- Tutorials and demos
- Single-session experiments

### When NOT to Use

- Anything that needs to survive a restart
- Production deployments
- Multi-process applications

### Code Example

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class MyState(TypedDict):
    messages: list
    count: int

def agent_node(state):
    return {"count": state.get("count", 0) + 1}

# Build graph
builder = StateGraph(MyState)
builder.add_node("agent", agent_node)
builder.add_edge(START, "agent")
builder.add_edge("agent", END)

# MemorySaver — one line, no config
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# Use it
config = {"configurable": {"thread_id": "test-1"}}
result = graph.invoke({"messages": [], "count": 0}, config)
print(result)  # {'messages': [], 'count': 1}

# State persists within this process
result2 = graph.invoke({"messages": ["hello"]}, config)
print(result2)  # count is now 2

# But if you restart Python... everything is gone
```

### Trade-offs

|Aspect|MemorySaver|
|---|---|
|**Durability**|❌ Lost on process exit|
|**Speed**|✅ Fastest (in-memory)|
|**Setup**|✅ Zero configuration|
|**Concurrency**|⚠️ Single process only|
|**Production**|❌ Never|

---

## SqliteSaver: Local Persistence

**Package:** `pip install langgraph-checkpoint-sqlite`

**What it is:** Stores checkpoints in a SQLite database file. Survives restarts, works for single-node deployments, but doesn't scale to high concurrency.

### When to Use

- Local development with persistence
- Single-user applications
- CLI tools that need state across runs
- Simple production apps (low traffic, single server)

### When NOT to Use

- High-concurrency applications
- Distributed systems (multiple servers)
- Applications requiring horizontal scaling

### Code Example: In-Memory SQLite (Testing)

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# :memory: = in-memory SQLite (like MemorySaver but with SQLite interface)
# Useful for testing SQLite-specific behavior
with SqliteSaver.from_conn_string(":memory:") as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "test-1"}}
    result = graph.invoke({"messages": [], "count": 0}, config)
```

### Code Example: File-Based SQLite (Persistent)

```python
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# Option 1: Using from_conn_string (recommended)
with SqliteSaver.from_conn_string("./checkpoints.db") as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
    # ... use graph

# Option 2: Using existing connection
conn = sqlite3.connect("./checkpoints.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = builder.compile(checkpointer=checkpointer)
# Remember to close connection when done
```

**Important:** `check_same_thread=False` is required because LangGraph's execution model may use the connection across threads.

### Code Example: Async SQLite

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Requires: pip install aiosqlite
async with AsyncSqliteSaver.from_conn_string("./checkpoints.db") as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "async-test"}}
    result = await graph.ainvoke({"messages": [], "count": 0}, config)
```

### Trade-offs

|Aspect|SqliteSaver|
|---|---|
|**Durability**|✅ Survives restarts|
|**Speed**|✅ Fast (local file I/O)|
|**Setup**|✅ Minimal (just a file path)|
|**Concurrency**|⚠️ Limited (SQLite write locks)|
|**Production**|⚠️ Low-traffic single-node only|

---

## PostgresSaver: Production Grade

**Package:** `pip install langgraph-checkpoint-postgres`

**What it is:** Stores checkpoints in a PostgreSQL database. Designed for production: durable, concurrent, queryable, and horizontally scalable.

### When to Use

- Production deployments
- Multi-user applications
- Distributed systems
- High-concurrency workloads
- When you need to query checkpoint history directly

### When NOT to Use

- Quick prototyping (overkill)
- Environments without Postgres access

### Code Example: Basic Setup

```python
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://user:password@localhost:5432/mydb"

# IMPORTANT: Call .setup() on first use to create tables
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()  # Creates checkpoint tables (run once)
    graph = builder.compile(checkpointer=checkpointer)
    
    config = {"configurable": {"thread_id": "prod-session-123"}}
    result = graph.invoke({"messages": [], "count": 0}, config)
```

### Code Example: Async Postgres

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

DB_URI = "postgresql://user:password@localhost:5432/mydb"

async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
    await checkpointer.setup()  # Async setup
    graph = builder.compile(checkpointer=checkpointer)
    
    config = {"configurable": {"thread_id": "async-prod-123"}}
    result = await graph.ainvoke({"messages": [], "count": 0}, config)
```

### Code Example: Manual Connection (Advanced)

If you need custom connection settings:

```python
import psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver

# CRITICAL: Must include autocommit=True and row_factory=dict_row
conn = psycopg.connect(
    "postgresql://user:password@localhost:5432/mydb",
    autocommit=True,        # Required for .setup() to work
    row_factory=dict_row    # Required for reading checkpoints
)

checkpointer = PostgresSaver(conn)
checkpointer.setup()
graph = builder.compile(checkpointer=checkpointer)
```

**Common mistake:** Forgetting `autocommit=True` or `row_factory=dict_row` causes cryptic errors like `TypeError: tuple indices must be integers or slices, not str`.

### Trade-offs

|Aspect|PostgresSaver|
|---|---|
|**Durability**|✅ Full ACID guarantees|
|**Speed**|✅ Fast with connection pooling|
|**Setup**|⚠️ Requires Postgres instance|
|**Concurrency**|✅ High (designed for it)|
|**Production**|✅ Recommended|

---

## Other Backends (Brief Mention)

LangGraph has additional checkpointer implementations for specific use cases:

|Backend|Package|Use Case|
|---|---|---|
|**RedisSaver**|`langgraph-checkpoint-redis`|High-speed, distributed, ephemeral (with TTL)|
|**MongoDBSaver**|`langgraph-checkpoint-mongodb`|Document-oriented storage|
|**CosmosDBSaver**|`langgraph-checkpoint-cosmosdb`|Azure deployments|
|**CouchbaseSaver**|Community|Distributed, high availability|

The pattern is the same: install the package, create the saver, pass to `compile()`.

---

## Choosing a Backend: Decision Tree

```
Are you prototyping/testing?
    │
    ├── YES → MemorySaver
    │
    └── NO → Do you need persistence across restarts?
                │
                ├── NO → MemorySaver
                │
                └── YES → Is this production with multiple users/servers?
                            │
                            ├── NO → SqliteSaver (single node, low traffic)
                            │
                            └── YES → PostgresSaver (or Redis for speed)
```

### Quick Reference

|Scenario|Recommended Backend|
|---|---|
|Tutorial / learning|MemorySaver|
|Unit tests|MemorySaver|
|CLI tool with memory|SqliteSaver|
|Local dev with persistence|SqliteSaver|
|Single-user web app|SqliteSaver|
|Multi-user production|PostgresSaver|
|High-concurrency|PostgresSaver or RedisSaver|
|LangGraph Cloud|Automatic (Postgres)|

---

## Serialization: How Data Gets Stored

All checkpointers use the same serialization protocol. By default, this is `JsonPlusSerializer`:

- Uses `ormsgpack` (fast MessagePack) as primary format
- Falls back to extended JSON for edge cases
- Handles LangChain/LangGraph types, datetimes, enums automatically

You can customize serialization, including adding encryption:

```python
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.postgres import PostgresSaver

# Encrypt checkpoint data at rest
encrypted_serde = EncryptedSerializer.from_pycryptodome_aes(encryption_key)
checkpointer = PostgresSaver(conn, serde=encrypted_serde)
```

This is useful for compliance requirements (HIPAA, GDPR) where checkpoint data must be encrypted.

---

## Common Patterns

### Pattern 1: Environment-Based Backend Selection

```python
import os
from langgraph.checkpoint.memory import MemorySaver

def get_checkpointer():
    env = os.getenv("ENVIRONMENT", "development")
    
    if env == "production":
        from langgraph.checkpoint.postgres import PostgresSaver
        checkpointer = PostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))
        checkpointer.setup()
        return checkpointer
    elif env == "staging":
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver.from_conn_string("./staging_checkpoints.db")
    else:
        return MemorySaver()

checkpointer = get_checkpointer()
graph = builder.compile(checkpointer=checkpointer)
```

### Pattern 2: Connection Pooling for Production

For high-traffic production apps, use connection pooling:

```python
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

# Create a connection pool
pool = ConnectionPool(
    "postgresql://user:password@localhost:5432/mydb",
    min_size=5,
    max_size=20
)

# Use pool connection for checkpointer
with pool.connection() as conn:
    checkpointer = PostgresSaver(conn)
    # ... use checkpointer
```

---

## Key Takeaways

1. **MemorySaver**: Fast, zero setup, but ephemeral — development only
2. **SqliteSaver**: Persistent, simple, but limited concurrency — single-node apps
3. **PostgresSaver**: Full durability, high concurrency, queryable — production
4. **Same interface**: Swap backends by changing initialization, not graph code
5. **Setup required**: PostgresSaver needs `.setup()` call to create tables
6. **Connection gotchas**: Postgres manual connections need `autocommit=True` and `row_factory=dict_row`
7. **Serialization is automatic**: `JsonPlusSerializer` handles LangChain types, datetimes, etc.
8. **Encryption available**: `EncryptedSerializer` for compliance requirements

---

## What's Next

- **Note 4**: Threads and resumption — addressing conversations and continuing them
- **Note 5**: Pending writes and fault tolerance — surviving failures mid-execution
- **Note 6**: Designing serializable state — what can and can't be checkpointed