# Note 6: Designing Serializable State

> **Week 5, Days 1-2 — Agent Track** **Topic:** State Management & Checkpointing (6 of 6) **Docs referenced:** LangGraph Graph API docs, langgraph-checkpoint PyPI (v4.0.1), LangGraph State Management docs

---

## Why Serialization Matters

When you compile a graph with a checkpointer, your state must be serialized (converted to bytes) at every super-step boundary and deserialized when resuming. If your state contains objects that can't be serialized, checkpointing fails.

```
State (Python objects) → Serialize → Bytes → Store in DB
                                        ↓
State (Python objects) ← Deserialize ← Bytes ← Load from DB
```

Understanding what can and can't be checkpointed prevents runtime surprises.

---

## The Default Serializer: JsonPlusSerializer

LangGraph uses `JsonPlusSerializer` as the default serialization protocol. It uses `ormsgpack` (a fast MessagePack implementation) with fallback to extended JSON.

### What JsonPlusSerializer Handles Automatically

|Type|Serialization Support|
|---|---|
|Primitives (`str`, `int`, `float`, `bool`, `None`)|✅ Native|
|`list`, `dict`, `tuple`, `set`|✅ Native|
|`datetime`, `date`, `time`, `timedelta`|✅ Built-in|
|`Enum` subclasses|✅ Built-in|
|`UUID`|✅ Built-in|
|`bytes`|✅ Built-in|
|LangChain `BaseMessage` subclasses|✅ Built-in|
|LangChain `Document`|✅ Built-in|
|Pydantic `BaseModel`|✅ Built-in|
|`dataclass` instances|✅ Built-in|
|`TypedDict` (as plain dict)|✅ Native|

### What CANNOT Be Serialized

|Type|Why It Fails|
|---|---|
|Open file handles|Can't serialize OS resources|
|Database connections|Can't serialize network sockets|
|Thread/Process objects|Can't serialize OS threads|
|Lambda functions|Can't serialize closures|
|Generator objects|Can't serialize iterator state|
|Compiled regex (sometimes)|Implementation-dependent|
|Custom classes (without Pydantic)|No serialization hook|
|Functions/methods|Can't serialize code objects|

---

## Defining State: TypedDict vs Pydantic vs Dataclass

LangGraph supports three approaches for state schemas:

### Option 1: TypedDict (Recommended Default)

```python
from typing import TypedDict, Annotated, Optional
from operator import add

class AgentState(TypedDict):
    messages: list
    count: int
    status: Optional[str]
```

**Pros:**

- Lightweight (no runtime validation overhead)
- Native dict behavior (easy to work with)
- Best performance
- First-class support in LangGraph

**Cons:**

- No runtime type validation
- Types are hints only (not enforced)

### Option 2: Pydantic BaseModel

```python
from pydantic import BaseModel, Field
from typing import Optional

class AgentState(BaseModel):
    messages: list = Field(default_factory=list)
    count: int = 0
    status: Optional[str] = None
```

**Pros:**

- Runtime validation (catches type errors)
- Default values built-in
- Rich validation (constraints, patterns)
- Recursive data validation

**Cons:**

- Slower (validation on every access)
- More complex serialization
- Some edge cases with generics (see GitHub issues)

### Option 3: Dataclass

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AgentState:
    messages: list = field(default_factory=list)
    count: int = 0
    status: Optional[str] = None
```

**Pros:**

- Default values supported
- Cleaner than TypedDict for defaults
- No external dependencies

**Cons:**

- No runtime validation
- Less common in LangGraph examples

### When to Use Which

|Scenario|Recommendation|
|---|---|
|Prototyping / most cases|TypedDict|
|Need default values|Dataclass or Pydantic|
|Need runtime validation|Pydantic|
|Performance critical|TypedDict|
|Complex nested validation|Pydantic|

---

## Reducers: How State Updates Merge

Reducers define how node outputs merge into existing state. Without reducers, each update **overwrites** the previous value.

### The Problem: Parallel Nodes

```python
class State(TypedDict):
    results: list  # No reducer

# Node A returns: {"results": ["from A"]}
# Node B returns: {"results": ["from B"]}
# Both run in parallel in same super-step

# ERROR: InvalidUpdateError
# "Can receive only one value per step"
```

### The Solution: Annotated with Reducer

```python
from typing import Annotated
from operator import add

class State(TypedDict):
    results: Annotated[list, add]  # add = concatenate lists

# Node A returns: {"results": ["from A"]}
# Node B returns: {"results": ["from B"]}
# Final state: {"results": ["from A", "from B"]}
```

### Built-in Reducers

|Reducer|Works On|Behavior|
|---|---|---|
|`operator.add`|`list`, `str`, `int`|Concatenate/sum|
|`add_messages`|`list[BaseMessage]`|Append with deduplication by ID|

### The add_messages Reducer

For conversation state, use the built-in `add_messages`:

```python
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

`add_messages` is smarter than `operator.add`:

- Appends new messages to the list
- If a message has the same `id` as an existing message, it **replaces** rather than duplicates
- Handles LangChain message types correctly

### Custom Reducers

For complex merge logic, define your own reducer:

```python
def merge_unique(existing: list, new: list) -> list:
    """Append only items not already present."""
    result = existing.copy()
    for item in new:
        if item not in result:
            result.append(item)
    return result

class State(TypedDict):
    tags: Annotated[list[str], merge_unique]
```

Reducer function signature: `(existing_value, new_value) -> merged_value`

---

## MessagesState: The Convenience Pattern

For agents that primarily work with messages, LangGraph provides `MessagesState`:

```python
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    # Inherits: messages: Annotated[list[AnyMessage], add_messages]
    extra_field: str
```

This is equivalent to:

```python
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    extra_field: str
```

---

## Schema Migration: What Happens When State Changes

LangGraph handles schema evolution gracefully:

### Adding New Keys

✅ **Fully supported**. New keys get their default value (or `None`) when loading old checkpoints.

```python
# V1: Old schema
class StateV1(TypedDict):
    messages: list

# V2: Add new key
class StateV2(TypedDict):
    messages: list
    retry_count: int  # New key

# Old checkpoints load fine — retry_count will be missing but graph can handle it
```

### Removing Keys

✅ **Fully supported**. Removed keys are ignored when loading old checkpoints.

### Renaming Keys

⚠️ **Data loss**. The old key's data is lost; the new key starts empty.

```python
# V1
class StateV1(TypedDict):
    msg_history: list

# V2: Renamed
class StateV2(TypedDict):
    messages: list  # Renamed from msg_history

# Old checkpoints: msg_history data is lost, messages starts empty
```

**Workaround**: Migrate data programmatically before changing schema.

### Changing Key Types

⚠️ **Potentially breaking**. Incompatible type changes can cause deserialization errors.

```python
# V1
class StateV1(TypedDict):
    count: int

# V2: Changed type
class StateV2(TypedDict):
    count: str  # Was int

# Old checkpoints with int may fail or behave unexpectedly
```

### Thread State Considerations

|Change|Completed Threads|Interrupted Threads|
|---|---|---|
|Add key|✅ Safe|✅ Safe|
|Remove key|✅ Safe|✅ Safe|
|Rename key|⚠️ Data loss|⚠️ Data loss|
|Change type|⚠️ May break|⚠️ May break|
|Add node|✅ Safe|✅ Safe|
|Remove node|✅ Safe|⚠️ May break*|
|Rename node|✅ Safe|⚠️ May break*|

*If the interrupted thread was about to enter the removed/renamed node.

---

## Best Practices for Serializable State

### 1. Keep State Flat and Simple

```python
# ✅ Good: flat, serializable
class AgentState(TypedDict):
    messages: list
    current_step: str
    retry_count: int
    tool_results: dict

# ❌ Avoid: nested objects that may not serialize
class BadState(TypedDict):
    db_connection: Any  # Can't serialize
    file_handle: Any    # Can't serialize
    callback: Callable  # Can't serialize
```

### 2. Store Results, Not Resources

```python
# ❌ Bad: storing the connection
def bad_node(state):
    conn = get_db_connection()
    return {"db_conn": conn}  # Won't serialize!

# ✅ Good: store the result, not the connection
def good_node(state):
    conn = get_db_connection()
    result = conn.query("SELECT * FROM users")
    return {"users": result}  # Data serializes fine
```

### 3. Use Pydantic for Complex Objects

If you need custom objects in state, make them Pydantic models:

```python
from pydantic import BaseModel

class ToolResult(BaseModel):
    tool_name: str
    output: str
    success: bool
    timestamp: datetime

class AgentState(TypedDict):
    messages: list
    tool_results: list[ToolResult]  # Pydantic serializes correctly
```

### 4. Avoid Lambdas and Closures

```python
# ❌ Bad: lambda in state
class BadState(TypedDict):
    processor: Callable  # Can't serialize

# ✅ Good: store configuration, create function at runtime
class GoodState(TypedDict):
    processor_name: str  # "uppercase" or "lowercase"

def get_processor(name: str) -> Callable:
    processors = {
        "uppercase": str.upper,
        "lowercase": str.lower,
    }
    return processors[name]
```

### 5. Test Serialization Early

```python
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

def test_state_serialization():
    serializer = JsonPlusSerializer()
    
    state = {
        "messages": [HumanMessage(content="Hello")],
        "count": 5,
        "metadata": {"key": "value"},
    }
    
    # Test round-trip
    serialized = serializer.dumps_typed(state)
    deserialized = serializer.loads_typed(serialized)
    
    assert deserialized == state
    print("✓ State serializes correctly")
```

---

## Encrypted Checkpoints

For sensitive data, use `EncryptedSerializer`:

```python
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.checkpoint.postgres import PostgresSaver

# Create encrypted serializer
encryption_key = b"your-32-byte-encryption-key-here"  # AES-256
encrypted_serde = EncryptedSerializer.from_pycryptodome_aes(encryption_key)

# Use with checkpointer
checkpointer = PostgresSaver(conn, serde=encrypted_serde)
```

Checkpoints are encrypted at rest — the database stores ciphertext.

---

## Common Serialization Errors

### Error: "Object of type X is not JSON serializable"

**Cause**: Non-serializable object in state.

**Fix**: Convert to serializable format:

```python
# Instead of datetime object
return {"timestamp": datetime.now()}  # Works with JsonPlusSerializer

# Instead of custom class
return {"result": my_obj.to_dict()}  # Convert to dict
```

### Error: "Can receive only one value per step"

**Cause**: Parallel nodes writing to same key without reducer.

**Fix**: Add reducer:

```python
class State(TypedDict):
    results: Annotated[list, add]  # Add reducer
```

### Error: Generic Pydantic types not deserializing correctly

**Cause**: Known issue with `Generic[TypeVar]` Pydantic models.

**Fix**: Avoid generic Pydantic in state, or use concrete types:

```python
# ❌ May have issues
class MyGeneric(BaseModel, Generic[T]):
    value: T

# ✅ Use concrete types
class MyConcreteModel(BaseModel):
    value: str
```

---

## Key Takeaways

1. **JsonPlusSerializer** handles primitives, datetime, enums, LangChain messages, Pydantic, dataclasses automatically
2. **Can't serialize**: file handles, connections, threads, lambdas, generators, custom classes without Pydantic
3. **TypedDict**: Recommended default — lightweight, fast, no validation overhead
4. **Pydantic**: Use when you need runtime validation or complex nested objects
5. **Reducers**: Required when parallel nodes update the same key — use `Annotated[type, reducer]`
6. **add_messages**: Smart reducer for conversation history — handles deduplication by message ID
7. **Schema migration**: Adding/removing keys is safe; renaming or changing types may cause issues
8. **Store results, not resources**: Connections, handles, and live objects can't be checkpointed
9. **Test serialization early**: Catch issues before production

---

## Series Complete

This concludes the State Management & Checkpointing notes:

1. **Note 1**: State and Why Persistence Matters
2. **Note 2**: Checkpointing — Saving State at Every Step
3. **Note 3**: Checkpointer Backends (MemorySaver, SQLite, Postgres)
4. **Note 4**: Threads and Resumption
5. **Note 5**: Pending Writes and Fault Tolerance
6. **Note 6**: Designing Serializable State ← You are here

**Next up**: Memory Systems (conversation, summary, vector) and Human-in-the-Loop patterns.