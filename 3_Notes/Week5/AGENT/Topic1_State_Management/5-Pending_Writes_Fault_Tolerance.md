# Note 5: Pending Writes and Fault Tolerance

> **Week 5, Days 1-2 — Agent Track** **Topic:** State Management & Checkpointing (5 of 6) **Docs referenced:** LangGraph Persistence docs, langgraph-checkpoint PyPI (v4.0.1), LangChain changelog

---

## The Problem: What Happens When Nodes Fail?

Consider a graph where three nodes run in parallel during a single super-step:

```
        ┌─→ Node A (API call) ──┐
START → │─→ Node B (LLM call)  ─│→ Node D → END
        └─→ Node C (DB query)  ─┘
```

If Node A and Node B complete successfully but Node C fails (timeout, rate limit, crash), what happens?

**Without fault tolerance:**

- The entire super-step fails
- Progress from Node A and Node B is lost
- On retry, all three nodes must re-execute
- Wasted LLM tokens, duplicate API calls, inconsistent state

**With LangGraph's fault tolerance:**

- Node A and Node B's results are saved as **pending writes**
- On retry, only Node C re-executes
- Node A and Node B's results are applied automatically
- No wasted work, consistent recovery

---

## Pending Writes: The Mechanism

**Pending writes** are intermediate state updates from nodes that completed successfully during a super-step that didn't fully complete (because another node failed).

### How It Works

1. **During a super-step**, each node's state updates are tracked individually
2. **As each node completes**, its writes are saved via `checkpointer.put_writes()`
3. **If all nodes complete**, a new checkpoint is created with all writes merged
4. **If any node fails**, the pending writes from successful nodes are preserved
5. **On resume**, pending writes are applied first, then only the failed node(s) re-execute

```
Super-step N starts (3 parallel nodes scheduled)
│
├── Node A completes → put_writes(A's changes)  ✓ Saved
├── Node B completes → put_writes(B's changes)  ✓ Saved
└── Node C fails     → Exception raised         ✗ Failed
│
Super-step N did NOT complete → No new checkpoint created
BUT pending writes from A and B are stored

On Resume:
├── Load checkpoint from super-step N-1
├── Apply pending writes (A's and B's results)
└── Re-execute only Node C
```

### The CheckpointTuple

When you retrieve a checkpoint, you get a `CheckpointTuple` that includes pending writes:

```python
CheckpointTuple(
    config={'configurable': {'thread_id': '1', 'checkpoint_id': '...'}},
    checkpoint={...},                    # The actual state snapshot
    metadata={'source': 'loop', ...},
    parent_config={...},
    pending_writes=[                     # Writes not yet in checkpoint
        ('node_a', 'messages', [...]),
        ('node_b', 'count', 5),
    ]
)
```

The `pending_writes` field is a list of tuples: `(task_id, channel_name, value)`.

---

## The Checkpointer Interface for Fault Tolerance

All checkpointers implement two key methods for fault tolerance:

|Method|Purpose|
|---|---|
|`.put(config, checkpoint, metadata, new_versions)`|Save a complete checkpoint|
|`.put_writes(config, writes, task_id)`|Save intermediate writes for a specific node|

When a node completes during a super-step, LangGraph calls `put_writes()` to save its results immediately — before the whole super-step completes.

```python
# Pseudocode of what happens internally
for node in scheduled_nodes:
    try:
        result = node.execute(state)
        checkpointer.put_writes(config, result, task_id=node.name)  # Saved immediately
    except Exception:
        # Node failed, but other nodes' writes are already saved
        raise

# Only if ALL nodes succeed:
checkpointer.put(config, merged_checkpoint, metadata, versions)
```

---

## Fault Tolerance Scenarios

### Scenario 1: Single Node Fails in Sequential Graph

```
START → Node A → Node B → Node C → END
                    ↑
                  fails
```

**What happens:**

- Checkpoint exists after Node A completes
- Node B fails mid-execution
- No pending writes (no parallel nodes)
- Resume re-executes from Node B

**Recovery:**

```python
config = {"configurable": {"thread_id": "my-thread"}}

try:
    graph.invoke({"input": "data"}, config)
except Exception as e:
    print(f"Failed at: {e}")
    
# Fix the issue (e.g., API is back up), then resume
result = graph.invoke(None, config)  # Continues from last checkpoint
```

### Scenario 2: One of Multiple Parallel Nodes Fails

```
        ┌─→ Node A ──┐
START → │─→ Node B  ─│→ END
        └─→ Node C  ─┘
              ↑
            fails
```

**What happens:**

- Checkpoint exists after START
- Node A and B complete, their writes are saved as pending
- Node C fails
- Super-step doesn't complete, no new checkpoint

**Recovery:**

```python
config = {"configurable": {"thread_id": "my-thread"}}

try:
    graph.invoke({"input": "data"}, config)
except Exception as e:
    print(f"Node C failed: {e}")

# On resume:
# - Pending writes from A and B are applied
# - Only Node C re-executes
result = graph.invoke(None, config)
```

### Scenario 3: Process Crash / Server Restart

If the entire process crashes (not just a node exception):

```python
# Session 1: Running graph
config = {"configurable": {"thread_id": "long-task"}}
# Process crashes here, mid-execution

# Session 2: After restart (with persistent checkpointer like Postgres)
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    graph = builder.compile(checkpointer=checkpointer)
    
    # Resume from last checkpoint
    result = graph.invoke(None, config)
```

With a persistent checkpointer (SQLite, Postgres), state survives process restarts. With MemorySaver, everything is lost.

---

## Inspecting Failures

### Check State After Failure

```python
config = {"configurable": {"thread_id": "my-thread"}}

try:
    graph.invoke({"input": "data"}, config)
except Exception:
    pass

# Inspect the state
snapshot = graph.get_state(config)

print(f"Values: {snapshot.values}")
print(f"Next nodes: {snapshot.next}")  # What would run next

# Check for task errors
for task in snapshot.tasks:
    if hasattr(task, 'error') and task.error:
        print(f"Task {task.name} failed: {task.error}")
```

### View Pending Writes Directly

```python
# Access via checkpointer directly
checkpoint_tuple = checkpointer.get_tuple(config)

if checkpoint_tuple.pending_writes:
    print("Pending writes from successful nodes:")
    for task_id, channel, value in checkpoint_tuple.pending_writes:
        print(f"  {task_id} → {channel}: {value}")
```

---

## Best Practices for Fault Tolerance

### 1. Design Idempotent Nodes

A node is **idempotent** if running it multiple times with the same input produces the same result. This makes retries safe.

```python
# ❌ NOT idempotent — creates duplicate records
def bad_node(state):
    db.insert({"user": state["user"], "action": "processed"})
    return {"processed": True}

# ✅ Idempotent — uses upsert or checks first
def good_node(state):
    db.upsert(
        {"user": state["user"]},  # Key
        {"action": "processed"}   # Update
    )
    return {"processed": True}
```

### 2. Use Persistent Checkpointers for Long Tasks

For tasks that take minutes or hours, use PostgresSaver or SqliteSaver — MemorySaver loses everything on crash.

```python
# For production / long-running tasks
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()  # Create tables
    graph = builder.compile(checkpointer=checkpointer)
```

### 3. Implement Retry Logic in Nodes

For transient failures (rate limits, timeouts), handle retries within the node:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def call_external_api(data):
    response = requests.post(API_URL, json=data)
    response.raise_for_status()
    return response.json()

def api_node(state):
    try:
        result = call_external_api(state["request"])
        return {"api_result": result}
    except Exception as e:
        # After 3 retries, let it fail for checkpoint recovery
        raise
```

### 4. Track Errors in State

Surface errors in state for downstream handling:

```python
from typing import TypedDict, Optional

class AgentState(TypedDict):
    messages: list
    error: Optional[str]
    error_node: Optional[str]

def risky_node(state):
    try:
        result = do_risky_operation()
        return {"messages": state["messages"] + [result]}
    except Exception as e:
        return {
            "error": str(e),
            "error_node": "risky_node"
        }

def should_continue(state):
    if state.get("error"):
        return "error_handler"
    return "next_node"
```

### 5. Use Conditional Edges for Error Routing

```python
builder.add_conditional_edges(
    "risky_node",
    should_continue,
    {
        "next_node": "next_node",
        "error_handler": "error_handler",
    }
)
```

---

## Limitations to Know

### 1. Checkpoints Are at Super-Step Boundaries

You can only resume from a super-step boundary — not from the middle of a node's execution. If a node runs for 10 minutes and crashes at minute 9, you restart that node from the beginning.

### 2. LLM Calls Are Non-Deterministic

Resuming after a failure may produce different results if the node makes LLM calls. The same prompt might return different content on retry.

### 3. Pending Writes Require Proper Checkpointer Support

All built-in checkpointers (MemorySaver, SqliteSaver, PostgresSaver) support pending writes. Custom checkpointers must implement `put_writes()` correctly.

### 4. State Validation Timing

LangGraph validates node **input** (before execution) but not node **output** (after execution). Invalid output can be checkpointed before validation catches it on the next step.

---

## Recovery Pattern: Try-Resume Loop

A common production pattern for fault-tolerant execution:

```python
import time

def run_with_recovery(graph, input_data, thread_id, max_retries=3):
    config = {"configurable": {"thread_id": thread_id}}
    
    for attempt in range(max_retries):
        try:
            if attempt == 0:
                # First attempt: provide input
                result = graph.invoke(input_data, config)
            else:
                # Retry: resume from checkpoint (no new input)
                result = graph.invoke(None, config)
            
            return result  # Success
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                # Wait before retry (exponential backoff)
                time.sleep(2 ** attempt)
            else:
                # Final attempt failed
                raise RuntimeError(f"Failed after {max_retries} attempts") from e
```

---

## Key Takeaways

1. **Pending writes** save successful nodes' results during failed super-steps
2. **On resume**, pending writes are applied first, then only failed nodes re-execute
3. **No wasted work**: Completed nodes don't re-run (no duplicate API calls, LLM tokens)
4. **put_writes()** saves each node's results immediately as it completes
5. **Checkpoints only exist at super-step boundaries** — can't resume mid-node
6. **Persistent checkpointers** (SQLite, Postgres) survive process crashes
7. **Design for idempotency** — nodes should be safe to re-run
8. **LLM non-determinism** — retries may produce different results

---

## What's Next

- **Note 6**: Designing serializable state — what can and can't be checkpointed