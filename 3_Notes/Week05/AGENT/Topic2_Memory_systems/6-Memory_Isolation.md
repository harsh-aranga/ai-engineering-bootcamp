# Memory Isolation — Namespaces and Privacy

## The Core Problem

You have one Store, but many users. Without isolation:

```python
# User A stores a memory
store.put(("memories",), "pref_001", {"text": "I'm allergic to peanuts"})

# User B searches for preferences
results = store.search(("memories",), query="food allergies")
# User B sees User A's medical information ← Privacy violation
```

**Namespaces** solve this by partitioning the Store into isolated regions.

---

## Understanding Namespaces

A namespace is a **tuple** that creates a hierarchical path to your data:

```python
# Flat namespace (single level)
("memories",)

# User-scoped namespace (two levels)
("user_123", "memories")

# Hierarchical namespace (three+ levels)
("org_acme", "user_123", "preferences")
```

Think of namespaces like a filesystem:

```
/memories/                      ← flat
/user_123/memories/             ← user-scoped
/org_acme/user_123/preferences/ ← hierarchical
```

### Namespace Isolation

Operations are scoped to their namespace:

```python
# User A's namespace
store.put(("user_A", "memories"), "mem_001", {"text": "I love pizza"})

# User B's namespace
store.put(("user_B", "memories"), "mem_001", {"text": "I'm vegan"})

# Each user only sees their own data
store.search(("user_A", "memories"), query="food")
# → Returns only User A's memories

store.search(("user_B", "memories"), query="food")
# → Returns only User B's memories
```

**Key point:** Same key (`mem_001`) in different namespaces = completely separate items.

---

## Common Namespace Patterns

### Pattern 1: Per-User Isolation

The most common pattern—each user gets their own memory space:

```python
def get_user_namespace(user_id: str, memory_type: str = "memories"):
    return (user_id, memory_type)

# Usage
namespace = get_user_namespace("user_123")  # ("user_123", "memories")
store.put(namespace, "mem_001", {"text": "User prefers dark mode"})
```

### Pattern 2: Organization → User Hierarchy

For multi-tenant applications:

```python
def get_namespace(org_id: str, user_id: str, memory_type: str = "memories"):
    return (org_id, user_id, memory_type)

# Acme Corp, User Alice
namespace = get_namespace("acme", "alice", "preferences")
# → ("acme", "alice", "preferences")

# Acme Corp, User Bob
namespace = get_namespace("acme", "bob", "preferences")
# → ("acme", "bob", "preferences")
```

### Pattern 3: Memory Type Segmentation

Separate different kinds of memories:

```python
# Same user, different memory types
user_id = "user_123"

preferences_ns = (user_id, "preferences")    # ("user_123", "preferences")
facts_ns = (user_id, "facts")                # ("user_123", "facts")
episodes_ns = (user_id, "episodes")          # ("user_123", "episodes")

# Store different types
store.put(preferences_ns, "pref_001", {"text": "Prefers concise responses"})
store.put(facts_ns, "fact_001", {"text": "Works at Anthropic"})
store.put(episodes_ns, "ep_001", {"text": "Asked about LangGraph on March 15"})
```

### Pattern 4: Agent-Specific Memories

When multiple agents share a user:

```python
# Different agents maintain separate memories about the same user
support_agent_ns = ("support_agent", "user_123", "memories")
sales_agent_ns = ("sales_agent", "user_123", "memories")
```

---

## Dynamic Namespaces with Templates

Hardcoding user IDs isn't practical. LangMem supports **namespace templates** that resolve at runtime:

```python
from langmem import create_manage_memory_tool, create_search_memory_tool

# Template with {user_id} placeholder
manage_tool = create_manage_memory_tool(
    namespace=("memories", "{user_id}")  # Template
)

search_tool = create_search_memory_tool(
    namespace=("memories", "{user_id}")
)
```

The `{user_id}` is replaced at runtime from `config["configurable"]`:

```python
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore

store = InMemoryStore(index={"dims": 1536, "embed": "openai:text-embedding-3-small"})

agent = create_react_agent(
    "anthropic:claude-sonnet-4-6",
    tools=[manage_tool, search_tool],
    store=store,
)

# Invoke for User A
agent.invoke(
    {"messages": [{"role": "user", "content": "Remember I like dolphins"}]},
    config={"configurable": {"user_id": "user_A"}}  # Resolves to ("memories", "user_A")
)

# Invoke for User B - completely isolated
agent.invoke(
    {"messages": [{"role": "user", "content": "What do I like?"}]},
    config={"configurable": {"user_id": "user_B"}}  # Resolves to ("memories", "user_B")
)
# → User B sees nothing about dolphins
```

### Complex Template Patterns

```python
# Organization + User
namespace=("memories", "{org_id}", "{user_id}")
config={"configurable": {"org_id": "acme", "user_id": "alice"}}
# → ("memories", "acme", "alice")

# Agent + User + Memory Type
namespace=("{agent_name}", "{user_id}", "preferences")
config={"configurable": {"agent_name": "support_bot", "user_id": "user_123"}}
# → ("support_bot", "user_123", "preferences")
```

### Using NamespaceTemplate Directly

For custom code (not using LangMem tools):

```python
from langmem.utils import NamespaceTemplate

template = NamespaceTemplate(("org", "{user_id}", "memories"))

# Resolve manually
namespace = template({"configurable": {"user_id": "alice"}})
# → ("org", "alice", "memories")

# Within a LangGraph node, config is available automatically
def my_node(state, config):
    namespace = template(config)
    store.put(namespace, key, value)
```

---

## Cross-Namespace Search

Sometimes you need to search across namespaces—carefully.

### Prefix-Based Search

The `list()` method supports namespace prefixes:

```python
# List all items under a user (all memory types)
items = store.list(namespace_prefix=("user_123",))

# List all users' preferences in an org
items = store.list(namespace_prefix=("acme",))
```

### Scoped Search Tools

Create a search tool that can see multiple users (admin use case):

```python
# User-level tool: can only search own memories
user_search = create_search_memory_tool(
    namespace=("memories", "{user_id}")
)

# Org-level tool: can search all users in the org
org_search = create_search_memory_tool(
    namespace=("memories", "{org_id}")  # Broader scope
)
```

**Use case:** A supervisor agent that needs visibility across team members.

### Privacy Consideration

Cross-namespace access should be:

- Explicitly designed (not accidental)
- Role-based (only authorized agents/users)
- Auditable (logged for compliance)

---

## TTL: Time-to-Live for Memory Expiration

Memories shouldn't live forever. TTL automatically expires old data.

### LangGraph Platform Configuration

In `langgraph.json`:

```json
{
  "store": {
    "ttl": {
      "default_ttl": 10080,
      "refresh_on_read": true,
      "sweep_interval_minutes": 120
    }
  }
}
```

**Parameters:**

- `default_ttl`: Lifespan in minutes (10080 = 7 days)
- `refresh_on_read`: If `true`, accessing an item resets its TTL (keeps active memories alive)
- `sweep_interval_minutes`: How often the system deletes expired items

### Per-Item TTL Override

Override default TTL when storing specific items:

```python
# This memory expires in 1 hour (60 minutes)
store.put(
    namespace,
    "temp_context",
    {"text": "User is currently on a call"},
    ttl=60
)

# This memory never expires
store.put(
    namespace,
    "permanent_fact",
    {"text": "User's birthday is March 15"},
    ttl=None  # No expiration
)
```

### TTL Use Cases

|Memory Type|TTL Strategy|
|---|---|
|Session context|Short (minutes to hours)|
|Recent interactions|Medium (days)|
|User preferences|Long (weeks to months)|
|Critical facts|No TTL (permanent)|

### PostgresStore TTL Implementation

PostgresStore tracks TTL with database columns and a background sweeper:

```python
from langgraph.store.postgres import PostgresStore

store = PostgresStore(
    connection_string="postgresql://...",
    index={"dims": 1536, "embed": embeddings},
)

# The store has internal columns:
# - expires_at: Timestamp when item expires
# - last_accessed_at: For refresh_on_read behavior

# Sweeper runs periodically to delete expired items
```

**Note:** TTL features require PostgresStore or LangGraph Platform. InMemoryStore doesn't have TTL sweeping.

---

## Privacy Best Practices

### 1. Default to User Isolation

Always include user ID in namespaces:

```python
# Bad: Shared namespace
namespace = ("memories",)

# Good: User-isolated
namespace = ("memories", user_id)
```

### 2. Validate User ID Source

Don't trust user-provided IDs blindly:

```python
def get_namespace(config):
    # Get user_id from authenticated session, not user input
    user_id = config["configurable"].get("user_id")
    
    if not user_id:
        raise ValueError("user_id required in config")
    
    # Sanitize: prevent path traversal attacks
    if ".." in user_id or "/" in user_id:
        raise ValueError("Invalid user_id")
    
    return ("memories", user_id)
```

### 3. Separate Sensitive Data

Use different namespaces for different sensitivity levels:

```python
# Public preferences (can be shared)
public_ns = (user_id, "preferences", "public")

# Private data (strict isolation)
private_ns = (user_id, "preferences", "private")

# PII (additional access controls)
pii_ns = (user_id, "pii")  # May require encryption
```

### 4. Implement Memory Deletion

Users should be able to delete their data (GDPR, CCPA):

```python
def delete_user_memories(user_id: str, store):
    """Delete all memories for a user."""
    namespace_prefix = (user_id,)
    
    # List all items under user's namespace
    items = store.list(namespace_prefix=namespace_prefix)
    
    # Delete each item
    for item in items:
        store.delete(item.namespace, item.key)
```

### 5. Audit Memory Access

Log who accesses what:

```python
import logging

def search_with_audit(store, namespace, query, requester_id):
    logging.info(f"Memory search: requester={requester_id}, namespace={namespace}, query={query[:50]}")
    results = store.search(namespace, query=query)
    logging.info(f"Memory search returned {len(results)} results")
    return results
```

---

## Complete Example: Multi-Tenant Memory System

```python
from langgraph.store.memory import InMemoryStore
from langgraph.prebuilt import create_react_agent
from langmem import create_manage_memory_tool, create_search_memory_tool

# Initialize store with embeddings
store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": "openai:text-embedding-3-small",
    }
)

# Create tools with hierarchical namespace template
# Organization → User → Memory Type
manage_tool = create_manage_memory_tool(
    namespace=("{org_id}", "{user_id}", "memories")
)

search_tool = create_search_memory_tool(
    namespace=("{org_id}", "{user_id}", "memories")
)

# Create agent
agent = create_react_agent(
    "anthropic:claude-sonnet-4-6",
    tools=[manage_tool, search_tool],
    store=store,
)

# Usage for different tenants

# Acme Corp - Alice
response = agent.invoke(
    {"messages": [{"role": "user", "content": "Remember I manage the engineering team"}]},
    config={"configurable": {"org_id": "acme", "user_id": "alice"}}
)
# Stored in: ("acme", "alice", "memories")

# Acme Corp - Bob
response = agent.invoke(
    {"messages": [{"role": "user", "content": "What does Alice manage?"}]},
    config={"configurable": {"org_id": "acme", "user_id": "bob"}}
)
# Searches in: ("acme", "bob", "memories") - finds nothing about Alice

# Different Org - Alice (different Alice!)
response = agent.invoke(
    {"messages": [{"role": "user", "content": "Remember I'm the CEO"}]},
    config={"configurable": {"org_id": "startup_xyz", "user_id": "alice"}}
)
# Stored in: ("startup_xyz", "alice", "memories") - completely separate
```

---

## Key Takeaways

1. **Namespaces are tuples** that create hierarchical isolation paths.
    
2. **Always scope by user.** Default pattern: `(user_id, "memories")` or `(org_id, user_id, "memories")`.
    
3. **Templates enable dynamic resolution.** Use `{user_id}` in namespace tuples, resolved from `config["configurable"]`.
    
4. **Cross-namespace access is possible** but should be intentional, role-based, and auditable.
    
5. **TTL prevents memory bloat.** Configure default expiration, use `refresh_on_read` for active memories.
    
6. **Privacy requires more than namespaces.** Validate user IDs, separate sensitive data, implement deletion, audit access.
    
7. **The Store is shared; namespaces are the isolation mechanism.** Without proper namespacing, all users share the same memory space.
    

---

## References

- LangGraph Persistence Concepts: https://github.com/langchain-ai/langgraph/blob/main/docs/docs/concepts/persistence.md
- LangMem Dynamic Namespaces: https://langchain-ai.github.io/langmem/guides/dynamically_configure_namespaces/
- LangMem Namespace Template: https://langchain-ai.github.io/langmem/reference/utils/
- LangGraph TTL Configuration: https://langchain-ai.github.io/langgraph/how-tos/ttl/configure_ttl/
- LangGraph Store System: https://deepwiki.com/langchain-ai/langgraph/4.3-store-system