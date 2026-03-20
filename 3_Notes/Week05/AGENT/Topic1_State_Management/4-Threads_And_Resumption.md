# Note 4: Threads and Resumption

> **Week 5, Days 1-2 — Agent Track** **Topic:** State Management & Checkpointing (4 of 6) **Docs referenced:** LangGraph Persistence docs, LangGraph Time Travel docs, langgraph-checkpoint PyPI

---

## What Is a Thread?

A **thread** is a unique identifier (`thread_id`) that groups a sequence of checkpoints together. Think of it as a conversation ID — all the state snapshots from a single conversation belong to the same thread.

```
Thread "user-123-session-1"
├── Checkpoint 0 (input received)
├── Checkpoint 1 (after node A)
├── Checkpoint 2 (after node B)
└── Checkpoint 3 (after node C, final)

Thread "user-456-session-1"
├── Checkpoint 0 (input received)
├── Checkpoint 1 (after node A)
└── Checkpoint 2 (after node B, interrupted)
```

Each thread maintains **independent execution history**. Two threads never share state, even if they're running the same graph.

---

## Passing thread_id in Config

Every graph invocation that uses persistence requires a `thread_id` in the config:

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    count: int

def agent_node(state):
    return {"count": state.get("count", 0) + 1}

# Build graph with checkpointer
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_edge(START, "agent")
builder.add_edge("agent", END)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# The config with thread_id
config = {"configurable": {"thread_id": "conversation-abc-123"}}

# First invocation
result1 = graph.invoke({"messages": ["Hello"], "count": 0}, config)
print(result1)  # {'messages': ['Hello'], 'count': 1}

# Second invocation — same thread_id = continued conversation
result2 = graph.invoke({"messages": ["How are you?"]}, config)
print(result2)  # count is now 2, messages accumulated
```

**Critical**: Without `thread_id`, the checkpointer cannot save or load state. The graph will run, but persistence won't work.

### Config Structure

```python
config = {
    "configurable": {
        "thread_id": "unique-conversation-id",      # Required
        "checkpoint_id": "specific-checkpoint-uuid", # Optional: resume from specific point
        "checkpoint_ns": "",                         # Optional: namespace for subgraphs
    }
}
```

|Field|Required|Purpose|
|---|---|---|
|`thread_id`|✅ Yes|Identifies the conversation/session|
|`checkpoint_id`|❌ No|Resumes from a specific checkpoint (time travel)|
|`checkpoint_ns`|❌ No|Namespace for subgraph isolation|

---

## Multi-Tenancy: Multiple Concurrent Threads

Threads enable multi-tenant applications. Each user gets their own `thread_id`, and their conversations are completely isolated:

```python
# User A's conversation
config_a = {"configurable": {"thread_id": "user-A-session-1"}}
graph.invoke({"messages": ["Hi, I'm Alice"]}, config_a)

# User B's conversation (completely separate)
config_b = {"configurable": {"thread_id": "user-B-session-1"}}
graph.invoke({"messages": ["Hi, I'm Bob"]}, config_b)

# User A continues their conversation
graph.invoke({"messages": ["What's my name?"]}, config_a)
# Agent knows it's Alice — state is thread-scoped
```

### Thread ID Patterns

|Pattern|Example|Use Case|
|---|---|---|
|User + Session|`user-123-session-456`|Multi-session per user|
|User only|`user-123`|Single ongoing conversation per user|
|Request ID|`req-uuid-abc123`|Stateless-ish, one-off requests|
|Ticket ID|`ticket-789`|Support ticket workflows|

---

## Inspecting State: get_state()

To see the current state of a thread:

```python
config = {"configurable": {"thread_id": "my-thread"}}

# Run the graph
graph.invoke({"messages": ["Hello"]}, config)

# Inspect current state
snapshot = graph.get_state(config)

print(snapshot.values)      # {'messages': [...], 'count': 1}
print(snapshot.next)        # () — empty tuple means graph finished
print(snapshot.metadata)    # {'source': 'loop', 'step': 1, ...}
print(snapshot.created_at)  # '2025-03-16T10:30:00.000000+00:00'
```

### StateSnapshot Fields (Recap from Note 2)

|Field|What It Contains|
|---|---|
|`values`|Your state data (the dict you care about)|
|`next`|Tuple of node names scheduled to run next|
|`config`|Config including `thread_id`, `checkpoint_id`|
|`metadata`|Source, step number, writes made|
|`created_at`|Timestamp|
|`parent_config`|Config of the previous checkpoint|
|`tasks`|Pending tasks, errors, or interrupts|

---

## Viewing History: get_state_history()

To see all checkpoints in a thread (most recent first):

```python
config = {"configurable": {"thread_id": "my-thread"}}

# List all checkpoints
for snapshot in graph.get_state_history(config):
    print(f"Step {snapshot.metadata['step']}: {snapshot.values}")
    print(f"  Next: {snapshot.next}")
    print(f"  Checkpoint ID: {snapshot.config['configurable']['checkpoint_id']}")
    print()
```

Example output:

```
Step 2: {'messages': [...], 'count': 2}
  Next: ()
  Checkpoint ID: 1f070a87-33b5-66ae-8002-fd25026c289a

Step 1: {'messages': [...], 'count': 1}
  Next: ('agent',)
  Checkpoint ID: 1f070a87-33b3-6d36-8001-50c306580336

Step 0: {'messages': [...], 'count': 0}
  Next: ('agent',)
  Checkpoint ID: 1f070a87-33b2-6026-8000-3e11b28e762c

Step -1: {'messages': [...], 'count': 0}
  Next: ('__start__',)
  Checkpoint ID: 1f070a87-33b0-5f1a-bfff-abc123def456
```

The `next` field tells you what would execute if you resumed from that checkpoint.

---

## Resumption: Continuing a Conversation

The simplest form of resumption is just invoking with the same `thread_id`:

```python
config = {"configurable": {"thread_id": "ongoing-chat"}}

# First message
graph.invoke({"messages": [("user", "My name is Harsh")]}, config)

# Later (even after restart with persistent checkpointer)
graph.invoke({"messages": [("user", "What's my name?")]}, config)
# Graph resumes from last checkpoint, has full context
```

This is how conversational memory works — each invocation loads the latest checkpoint, runs the graph, and saves a new checkpoint.

---

## Time Travel: Resuming from Specific Checkpoints

### Replay: Re-run from a Past Point

To replay from an earlier checkpoint:

```python
config = {"configurable": {"thread_id": "my-thread"}}

# Find the checkpoint you want
history = list(graph.get_state_history(config))
target_checkpoint = history[2]  # Third from top (0-indexed)

# Replay from that checkpoint
result = graph.invoke(None, target_checkpoint.config)
```

**Important**: Replay re-executes nodes. LLM calls, API requests, and tool calls will fire again and may produce different results.

### Fork: Branch with Modified State

To modify state and explore an alternative path:

```python
config = {"configurable": {"thread_id": "my-thread"}}

# Find checkpoint before the decision point
history = list(graph.get_state_history(config))
before_decision = next(s for s in history if s.next == ("decide",))

# Fork: modify state at that checkpoint
fork_config = graph.update_state(
    before_decision.config,
    values={"user_choice": "option_b"},  # Change a value
)

# Resume from the fork
fork_result = graph.invoke(None, fork_config)
```

**Key insight**: `update_state` doesn't modify the original history. It creates a new checkpoint that branches from the specified point. The original execution remains intact.

```
Original timeline:
checkpoint_1 → checkpoint_2 → checkpoint_3

After fork from checkpoint_1:
checkpoint_1 → checkpoint_2 → checkpoint_3  (original)
            ↘ fork_checkpoint → new_checkpoint  (branch)
```

---

## update_state: Modifying Checkpoints

The `update_state` method creates a new checkpoint with modified values:

```python
# Get current state
config = {"configurable": {"thread_id": "my-thread"}}
current = graph.get_state(config)

# Update state (creates new checkpoint)
new_config = graph.update_state(
    config,
    values={"count": 100},  # Modify values
    as_node="agent",        # Optional: specify which node "made" this update
)

# The new checkpoint has source="update" in metadata
new_state = graph.get_state(new_config)
print(new_state.metadata["source"])  # "update"
```

### The as_node Parameter

When you call `update_state`, LangGraph needs to know which node "made" the update (to determine what runs next). By default, it infers this from the checkpoint's version history.

Specify `as_node` explicitly when:

- **Parallel branches**: Multiple nodes updated state in the same step
- **Ambiguity**: LangGraph raises `InvalidUpdateError` if it can't determine

```python
# Explicit as_node
fork_config = graph.update_state(
    checkpoint_config,
    values={"topic": "new topic"},
    as_node="generate_topic",  # Pretend this node made the update
)
# Execution resumes from generate_topic's successors
```

---

## Resuming with invoke(None, config)

A special pattern: calling `invoke(None, config)` continues execution from the checkpoint without new input.

```python
# Fork from an earlier checkpoint
fork_config = graph.update_state(old_checkpoint.config, values={...})

# Resume execution (no new input, just continue)
result = graph.invoke(None, fork_config)
```

This is how human-in-the-loop works:

1. Graph hits an interrupt point
2. Human reviews/modifies state via `update_state`
3. Graph resumes with `invoke(None, config)`

---

## Practical Patterns

### Pattern 1: Conversational Agent with Memory

```python
def chat(user_message: str, session_id: str):
    config = {"configurable": {"thread_id": session_id}}
    result = graph.invoke({"messages": [("user", user_message)]}, config)
    return result["messages"][-1].content

# Same session = continued conversation
chat("Hi, I'm Harsh", "session-123")
chat("What's my name?", "session-123")  # Knows it's Harsh

# New session = fresh start
chat("What's my name?", "session-456")  # Doesn't know
```

### Pattern 2: Debug a Failed Run

```python
config = {"configurable": {"thread_id": "failed-run"}}

# Find where it went wrong
for snapshot in graph.get_state_history(config):
    print(f"Step {snapshot.metadata['step']}")
    print(f"  State: {snapshot.values}")
    if snapshot.tasks:
        for task in snapshot.tasks:
            if hasattr(task, 'error'):
                print(f"  ERROR: {task.error}")
```

### Pattern 3: What-If Analysis

```python
config = {"configurable": {"thread_id": "analysis"}}

# Run original
original_result = graph.invoke({"scenario": "baseline"}, config)

# Fork and try alternative
history = list(graph.get_state_history(config))
decision_point = next(s for s in history if s.next == ("evaluate",))

fork_config = graph.update_state(
    decision_point.config,
    values={"scenario": "aggressive"},
)
alternative_result = graph.invoke(None, fork_config)

# Compare results
print(f"Baseline: {original_result}")
print(f"Alternative: {alternative_result}")
```

---

## Thread Cleanup

To delete a thread and all its checkpoints:

```python
# PostgresSaver and some other backends support this
checkpointer.delete_thread(thread_id="old-conversation")

# Async version
await checkpointer.adelete_thread(thread_id="old-conversation")
```

Not all checkpointers implement `delete_thread`. Check your backend's documentation.

---

## Key Takeaways

1. **Thread = conversation ID** — groups checkpoints into an isolated sequence
2. **thread_id is required** — pass it in `config["configurable"]["thread_id"]`
3. **Multi-tenancy is automatic** — different thread_ids = completely separate state
4. **get_state()** — inspect current state of a thread
5. **get_state_history()** — list all checkpoints (most recent first)
6. **Resumption** — invoke with same thread_id continues from last checkpoint
7. **Time travel** — use checkpoint_id in config to resume from specific point
8. **Fork with update_state** — modify state and branch without losing original history
9. **invoke(None, config)** — continue execution without new input (post-interrupt or post-fork)

---

## What's Next

- **Note 5**: Pending writes and fault tolerance — surviving failures mid-execution
- **Note 6**: Designing serializable state — what can and can't be checkpointed