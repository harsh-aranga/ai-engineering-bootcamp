# Note 2: Checkpointing — Saving State at Every Step

> **Week 5, Days 1-2 — Agent Track** **Topic:** State Management & Checkpointing (2 of 6) **Docs referenced:** LangGraph Persistence Concepts, langgraph-checkpoint PyPI (v4.0.1), LangChain Reference docs

---

## What Is a Checkpoint?

A checkpoint is a **complete snapshot of graph state at a specific point in time**. It captures everything needed to restore the graph to exactly that moment — the values of all state keys, metadata about which step produced it, and version information for change tracking.

Think of checkpoints as **automatic save files** that LangGraph creates as your graph executes. You don't call "save" manually — the system snapshots state at defined boundaries.

```python
# A checkpoint is essentially this structure (simplified)
checkpoint = {
    "v": 4,                                          # Schema version
    "id": "1ef4f797-8335-6428-8001-8a1503f9b875",   # Unique checkpoint ID (UUID v6)
    "ts": "2024-07-31T20:14:19.804150+00:00",       # Timestamp
    "channel_values": {                              # Your actual state data
        "messages": [...],
        "current_step": "agent",
    },
    "channel_versions": {...},                       # Version tracking per channel
    "versions_seen": {...},                          # What each node has seen
    "pending_sends": [],                             # Messages to be delivered
}
```

---

## When Checkpoints Are Created: Super-Steps

LangGraph doesn't checkpoint after every line of code. It checkpoints at **super-step boundaries**.

### What Is a Super-Step?

A super-step is a single "tick" of the graph execution where all nodes scheduled for that step execute (potentially in parallel). After all scheduled nodes complete, LangGraph creates a checkpoint.

For a simple sequential graph:

```
START → Node A → Node B → Node C → END
```

The super-steps are:

|Super-Step|What Happens|Checkpoint Created|
|---|---|---|
|-1 (input)|Input received, written to `__start__` channel|✓ Checkpoint with source="input"|
|0|Node A executes|✓ Checkpoint with source="loop", step=0|
|1|Node B executes|✓ Checkpoint with source="loop", step=1|
|2|Node C executes|✓ Checkpoint with source="loop", step=2|

**Key insight**: You can only resume from a checkpoint, which means you can only resume from a super-step boundary — not from the middle of a node's execution.

### Parallel Execution

If multiple nodes are scheduled to run in the same super-step (no edges between them), they execute in parallel but produce a **single checkpoint** after all complete:

```
        ┌─→ Node B ─┐
START → │           │ → Node D → END
        └─→ Node C ─┘
```

|Super-Step|What Happens|Checkpoint|
|---|---|---|
|-1|Input received|✓|
|0|Node B and Node C execute in parallel|✓ (one checkpoint after both complete)|
|1|Node D executes|✓|

---

## Checkpoint Structure: What Gets Saved

When you call `graph.get_state(config)`, you get a `StateSnapshot` object. This is the user-facing representation of a checkpoint.

### StateSnapshot Fields

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    step_count: int

def agent_node(state):
    return {"step_count": state.get("step_count", 0) + 1}

# Build and compile with checkpointer
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_edge(START, "agent")
builder.add_edge("agent", END)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# Run the graph
config = {"configurable": {"thread_id": "example-1"}}
graph.invoke({"messages": ["Hello"], "step_count": 0}, config)

# Inspect the checkpoint
snapshot = graph.get_state(config)
print(snapshot)
```

The `StateSnapshot` contains:

|Field|Type|Description|
|---|---|---|
|`values`|dict|Current state values (your actual data)|
|`next`|tuple|Names of nodes scheduled to execute next (empty if graph complete)|
|`config`|dict|Config including `thread_id`, `checkpoint_ns`, `checkpoint_id`|
|`metadata`|dict|Source ("input", "loop", "update"), step number, parent info|
|`created_at`|str|ISO timestamp when checkpoint was created|
|`parent_config`|dict|Config pointing to the previous checkpoint (linked list)|
|`tasks`|tuple|`PregelTask` objects describing pending work, errors, or interrupts|
|`interrupts`|tuple|Any interrupt data if graph was paused|

### Example StateSnapshot Output

```python
StateSnapshot(
    values={'messages': ['Hello'], 'step_count': 1},
    next=(),  # Empty = graph finished
    config={
        'configurable': {
            'thread_id': 'example-1',
            'checkpoint_ns': '',
            'checkpoint_id': '1f070a87-33b5-66ae-8002-fd25026c289a'
        }
    },
    metadata={
        'source': 'loop',      # Created during execution loop
        'step': 1,             # Super-step number
        'parents': {},
        'writes': {'agent': {'step_count': 1}}  # What this step wrote
    },
    created_at='2025-08-03T20:28:43.857059+00:00',
    parent_config={
        'configurable': {
            'thread_id': 'example-1',
            'checkpoint_ns': '',
            'checkpoint_id': '1f070a87-33b3-6d36-8001-50c306580336'
        }
    },
    tasks=(),
    interrupts=()
)
```

---

## The Raw Checkpoint: Internal Structure

Under the hood, checkpointers store a `Checkpoint` TypedDict with more internal details:

```python
checkpoint = {
    "v": 4,  # Checkpoint schema version (currently v4)
    "id": "1ef4f797-8335-6428-8001-8a1503f9b875",  # UUID v6 (embeds timestamp + counter)
    "ts": "2024-07-31T20:14:19.804150+00:00",
    
    # Your actual state data, keyed by channel name
    "channel_values": {
        "messages": [HumanMessage(content="Hello"), AIMessage(content="Hi there!")],
        "step_count": 1,
    },
    
    # Version number for each channel (for change detection)
    "channel_versions": {
        "__start__": 2,
        "messages": 3,
        "step_count": 3,
    },
    
    # What version each node last saw (for Pregel algorithm)
    "versions_seen": {
        "__input__": {},
        "__start__": {"__start__": 1},
        "agent": {"messages": 2, "step_count": 2},
    },
    
    # Pending messages between nodes
    "pending_sends": [],
}
```

### Why UUID v6 for Checkpoint IDs?

The checkpoint ID uses UUID v6 format, which embeds:

- A timestamp component
- A monotonic counter

This ensures checkpoints can be **sorted chronologically** just by comparing their IDs — no need to parse timestamps.

---

## Checkpoint Metadata: The "Why" Behind Each Checkpoint

Every checkpoint includes metadata explaining how it was created:

```python
metadata = {
    "source": "loop",      # How this checkpoint was created
    "step": 2,             # Which super-step
    "writes": {...},       # What state changes this step made
    "parents": {},         # Parent graph info (for subgraphs)
    "thread_id": "conv-1", # Which thread this belongs to
}
```

### Metadata Source Values

|Source|Meaning|
|---|---|
|`"input"`|Created when execution begins, before any nodes run (step = -1)|
|`"loop"`|Created after a super-step completes during normal execution|
|`"update"`|Created when you manually call `graph.update_state()`|
|`"fork"`|Created when forking from an existing checkpoint|

The `source` field is useful for debugging — you can tell whether a checkpoint came from normal execution or manual intervention.

---

## Attaching a Checkpointer: The Compile Step

To enable checkpointing, pass a checkpointer when compiling your graph:

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

# Build your graph
builder = StateGraph(MyState)
builder.add_node("agent", agent_node)
# ... add edges ...

# Create checkpointer
checkpointer = MemorySaver()

# Compile WITH checkpointer
graph = builder.compile(checkpointer=checkpointer)

# Now every invoke/stream automatically checkpoints
config = {"configurable": {"thread_id": "session-123"}}
result = graph.invoke({"messages": ["Hello"]}, config)
```

**Critical**: Without a checkpointer, the graph runs but nothing persists. The `thread_id` in config is meaningless without a checkpointer attached.

### Subgraph Checkpointing

If your graph has subgraphs, you only pass the checkpointer to the **parent** graph. LangGraph automatically propagates it to children:

```python
# CORRECT: Only parent gets checkpointer
parent_graph = parent_builder.compile(checkpointer=checkpointer)

# WRONG: Don't pass checkpointer to subgraphs
# child_graph = child_builder.compile(checkpointer=checkpointer)  # Don't do this
```

---

## The Checkpointer Interface: What It Must Do

All checkpointers implement `BaseCheckpointSaver` with these core methods:

|Method|Purpose|
|---|---|
|`.put(config, checkpoint, metadata, new_versions)`|Store a checkpoint|
|`.put_writes(config, writes, task_id)`|Store intermediate writes (pending writes)|
|`.get_tuple(config)`|Fetch a checkpoint + metadata + pending writes|
|`.list(config, *, filter, before, limit)`|List checkpoints matching criteria|

For async graphs (`.ainvoke()`, `.astream()`), async variants are used:

- `.aput()`, `.aput_writes()`, `.aget_tuple()`, `.alist()`

You rarely call these directly — the graph's `.invoke()`, `.get_state()`, and `.get_state_history()` methods wrap them.

---

## Accessing Checkpoints: The Graph API

### Get Current State

```python
config = {"configurable": {"thread_id": "session-123"}}

# Get the latest checkpoint for this thread
snapshot = graph.get_state(config)
print(snapshot.values)  # Your state data
print(snapshot.next)    # What would execute next (empty if done)
```

### Get State History

```python
# Get all checkpoints for this thread (most recent first)
for snapshot in graph.get_state_history(config):
    print(f"Step {snapshot.metadata['step']}: {snapshot.values}")
```

### Get Specific Checkpoint

```python
# Include checkpoint_id to get a specific point in time
config_with_checkpoint = {
    "configurable": {
        "thread_id": "session-123",
        "checkpoint_id": "1f070a87-33b5-66ae-8002-fd25026c289a"
    }
}
old_snapshot = graph.get_state(config_with_checkpoint)
```

---

## Key Takeaways

1. **Checkpoint = snapshot of state** at a super-step boundary
2. **Super-step = one tick** of the graph where scheduled nodes execute
3. **Checkpoints are automatic** — created after every super-step when a checkpointer is attached
4. **StateSnapshot** is the user-facing view; raw `Checkpoint` is the internal structure
5. **UUID v6 IDs** enable chronological sorting without parsing timestamps
6. **Metadata tracks provenance** — source (input/loop/update/fork), step number, writes
7. **Checkpointer attached at compile** — without it, nothing persists
8. **Subgraphs inherit** the parent's checkpointer automatically

---

## What's Next

- **Note 3**: Checkpointer backends — MemorySaver vs SQLite vs Postgres trade-offs
- **Note 4**: Threads and resumption — addressing conversations and continuing them
- **Note 5**: Pending writes and fault tolerance — surviving failures
- **Note 6**: Designing serializable state — what can and can't be checkpointed