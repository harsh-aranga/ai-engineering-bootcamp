# Execution Model: Message Passing and Super-steps

## Why This Matters

LangGraph isn't just a workflow library — it's a **graph processing engine** built on distributed systems principles. Understanding the execution model explains behaviors that otherwise seem magical or confusing:

- Why state "just works" across nodes
- Why parallel nodes need reducers
- Why checkpointing happens where it does
- Why some updates are invisible to other nodes

---

## The Pregel Heritage

LangGraph's execution engine is named **Pregel**, after Google's 2010 system for large-scale graph processing. The core insight: **think like a vertex**.

### Google's Pregel (Original)

Built to run algorithms like PageRank across billions of nodes:

```
Each vertex:
1. Receives messages from neighbors
2. Computes locally
3. Sends messages to neighbors
4. Votes to halt when done
```

No vertex knows the whole graph. They only communicate via messages.

### LangGraph's Adaptation

Same model, different domain:

|Pregel (Google)|LangGraph|
|---|---|
|Graph algorithms|Workflow orchestration|
|Vertices|Nodes (functions)|
|Messages|State updates|
|Graph edges|Workflow transitions|
|Supersteps|Execution phases|

---

## Message Passing Model

### How Nodes Communicate

Nodes don't call each other directly. They communicate through **state** (channels):

```
Node A executes
    ↓
Returns {"result": "data"}
    ↓
State is updated (via channel/reducer)
    ↓
Node B reads updated state
    ↓
Executes with new data
```

This is **message passing** — nodes send updates that other nodes receive.

### The Illusion of Direct Communication

When you write:

```python
def node_a(state: State) -> dict:
    return {"data": "from A"}

def node_b(state: State) -> dict:
    value = state["data"]  # Gets "from A"
    return {"result": f"processed {value}"}
```

It looks like direct data flow. But underneath:

1. Node A's return → written to `data` channel
2. Super-step completes → channel value finalized
3. Node B reads from channel → sees updated value

---

## Super-steps

### What is a Super-step?

A **super-step** is one discrete iteration of graph execution:

1. **Plan**: Determine which nodes should run
2. **Execute**: Run those nodes (potentially in parallel)
3. **Update**: Merge all outputs into state via channels/reducers
4. **Checkpoint**: Save state (if checkpointer configured)

```
┌─────────────────────────────────────┐
│           SUPER-STEP N              │
├─────────────────────────────────────┤
│  1. Plan: Which nodes are active?   │
│  2. Execute: Run active nodes       │
│  3. Update: Apply all state changes │
│  4. Checkpoint: Save snapshot       │
└─────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│          SUPER-STEP N+1             │
└─────────────────────────────────────┘
```

### Key Property: Isolation Within Super-step

**Updates within a super-step are invisible to other nodes in the same super-step.**

```python
# Both run in same super-step
def node_a(state: State) -> dict:
    return {"counter": 1}

def node_b(state: State) -> dict:
    # Cannot see node_a's update yet!
    # Sees the state from BEFORE this super-step
    current = state.get("counter", 0)  # Still 0
    return {"counter": 2}
```

This is why reducers matter — both nodes are updating the same field "simultaneously."

### When Super-steps Change

Sequential nodes = different super-steps:

```
Super-step 1: [node_a]
Super-step 2: [node_b]
Super-step 3: [node_c]
```

Parallel nodes = same super-step:

```
Super-step 1: [node_a, node_b, node_c]  # All run together
Super-step 2: [node_d]
```

---

## Channels: The Communication Layer

### What is a Channel?

A **channel** is how state fields are managed internally. Each field in your TypedDict state becomes a channel.

```python
class State(TypedDict):
    query: str           # → LastValue channel
    results: list        # → LastValue channel (or BinaryOperatorAggregate with reducer)
    messages: Annotated[list, add_messages]  # → BinaryOperatorAggregate channel
```

### Built-in Channel Types

|Channel Type|Behavior|Use Case|
|---|---|---|
|`LastValue`|Stores most recent value, allows only ONE update per step|Default for scalar fields|
|`BinaryOperatorAggregate`|Applies reducer to merge multiple updates|Fields with `Annotated[type, reducer]`|
|`Topic`|Accumulates multiple values (pub/sub)|Low-level, rarely used directly|
|`EphemeralValue`|Cleared after each step|Internal edges, temporary data|

### LastValue: The Default Channel

Most state fields use `LastValue`:

```python
class State(TypedDict):
    query: str      # LastValue channel
    result: str     # LastValue channel
```

**Critical rule**: LastValue can only receive **one value per super-step**.

```python
# This FAILS if both run in same super-step:
def node_a(state): return {"result": "A"}
def node_b(state): return {"result": "B"}

# Error: InvalidUpdateError: LastValue can only receive one value per step
```

### BinaryOperatorAggregate: For Parallel Updates

When you use `Annotated[type, reducer]`, you get a `BinaryOperatorAggregate` channel:

```python
from typing import Annotated
from operator import add

class State(TypedDict):
    results: Annotated[list, add]  # Now uses reducer

# Both can update in same super-step:
def node_a(state): return {"results": ["A"]}
def node_b(state): return {"results": ["B"]}

# After super-step: results = ["A", "B"] (merged via add)
```

---

## The Complete Execution Flow

### Step-by-Step Breakdown

```
1. INITIALIZATION
   - Input written to start channel
   - First super-step scheduled

2. SUPER-STEP LOOP
   For each super-step:
   
   a. PLAN PHASE
      - Identify nodes with fulfilled dependencies
      - A node is "active" when all incoming edges have values
   
   b. EXECUTE PHASE
      - Run all active nodes (potentially in parallel)
      - Each node:
        - Reads current state (from channels)
        - Performs computation
        - Returns state updates
      - Updates are buffered, NOT yet visible
   
   c. UPDATE PHASE
      - Collect all pending writes
      - Apply updates to channels:
        - LastValue: overwrite (fails if multiple)
        - BinaryOperatorAggregate: apply reducer
      - State is now updated for next super-step
   
   d. CHECKPOINT PHASE (if checkpointer configured)
      - Serialize current state
      - Save to checkpoint storage
      - Record version for this super-step
   
   e. SCHEDULE NEXT
      - Determine which nodes activate next
      - If none → graph terminates

3. TERMINATION
   - No more active nodes
   - Return final state
```

### Visual Flow

```
                    ┌──────────────────┐
                    │      INPUT       │
                    └────────┬─────────┘
                             ↓
              ┌──────────────────────────────┐
              │        SUPER-STEP 1          │
              │  ┌─────────────────────────┐ │
              │  │   node_a   │   node_b   │ │  ← Execute in parallel
              │  └─────────────────────────┘ │
              │              ↓               │
              │    Merge updates (reducer)   │
              │              ↓               │
              │       Save checkpoint        │
              └──────────────────────────────┘
                             ↓
              ┌──────────────────────────────┐
              │        SUPER-STEP 2          │
              │  ┌─────────────────────────┐ │
              │  │        node_c           │ │  ← Sequential
              │  └─────────────────────────┘ │
              │              ↓               │
              │       Save checkpoint        │
              └──────────────────────────────┘
                             ↓
                    ┌──────────────────┐
                    │      OUTPUT      │
                    └──────────────────┘
```

---

## Transactional Super-steps

### All-or-Nothing Principle

Super-steps are **transactional**:

- If any node in a super-step raises an exception, **none of the updates are applied**
- State remains at the last successful checkpoint
- This ensures consistency

```python
def node_a(state): return {"counter": 1}
def node_b(state): raise Exception("Failed!")  # Crashes

# Both run in same super-step:
# node_a returns {"counter": 1}
# node_b raises exception
# Result: counter is NOT updated, state rolled back
```

### Why This Matters

For agent systems:

- If tool execution fails mid-step, no partial state corruption
- Retry from last checkpoint with clean state
- Deterministic replay possible

---

## Node Activation

### How Nodes Become Active

A node becomes active when:

1. It receives a message (state update) on any incoming edge
2. All required dependencies are satisfied

At graph start:

- Entry point node is activated by START
- Receives initial input

After each super-step:

- Nodes connected to just-completed nodes check if they should activate
- Conditional edges evaluate to determine next node

### Vote to Halt

Borrowed from Pregel: nodes "vote to halt" when done.

In LangGraph:

- Node returns → implicitly votes to continue (to next node via edge)
- END edge → votes to halt
- When all paths reach END → graph terminates

---

## Parallel Execution Details

### What Runs in Parallel?

Nodes that can be reached from the same point run in the same super-step:

```python
# Fan-out pattern
graph.add_edge(START, "worker_a")
graph.add_edge(START, "worker_b")
graph.add_edge(START, "worker_c")

# worker_a, worker_b, worker_c all run in super-step 1
```

### Order is NOT Guaranteed

```python
def worker_a(state):
    print("A")
    return {"results": ["A"]}

def worker_b(state):
    print("B")
    return {"results": ["B"]}

# Output order of prints: could be A,B or B,A
# Final results: could be ["A","B"] or ["B","A"]
```

If order matters, use sequential edges or sort in a merge node.

### The Reducer Requirement

Without a reducer, parallel updates to the same field fail:

```python
# NO REDUCER - FAILS
class State(TypedDict):
    result: str  # LastValue channel

def node_a(state): return {"result": "A"}
def node_b(state): return {"result": "B"}
# InvalidUpdateError!

# WITH REDUCER - WORKS
class State(TypedDict):
    results: Annotated[list, operator.add]

def node_a(state): return {"results": ["A"]}
def node_b(state): return {"results": ["B"]}
# results = ["A", "B"]
```

---

## Checkpointing Integration

### When Checkpoints Happen

After each super-step completes:

1. All node updates merged
2. State serialized
3. Checkpoint saved with version number

```python
app = graph.compile(checkpointer=MemorySaver())

result = app.invoke({"query": "test"}, config={"configurable": {"thread_id": "1"}})

# Internally:
# Super-step 0 → Checkpoint v0
# Super-step 1 → Checkpoint v1
# Super-step 2 → Checkpoint v2
```

### Replay and Recovery

Because checkpoints happen at super-step boundaries:

- Crash during super-step → restart from last checkpoint
- Resume interrupted graph → continue from checkpoint
- Time travel → restore any checkpoint version

---

## Mental Model Summary

### Think Like a Vertex (Node)

Each node:

1. Wakes up when there's work (active)
2. Reads the shared state (messages in)
3. Does computation
4. Writes updates to state (messages out)
5. Goes inactive until next activation

### The Pregel Mindset

```
"I don't know the whole graph.
 I just read my inputs,
 do my work,
 write my outputs,
 and trust the system."
```

### Why This Design?

|Feature|Benefit|
|---|---|
|Message passing|Clean isolation, no shared memory bugs|
|Super-steps|Clear execution phases, deterministic|
|Transactional|Consistency on failure|
|Checkpointing at boundaries|Natural recovery points|
|Parallel within super-step|Performance|

---

## Common Gotchas

### 1. Updates Not Visible Until Next Super-step

```python
def node_a(state):
    return {"x": 1}

def node_b(state):
    # If running in SAME super-step as node_a:
    # state["x"] is the OLD value, not 1
```

### 2. Parallel Without Reducer

```python
# WRONG
class State(TypedDict):
    data: dict  # No reducer

# Both update in parallel → crash
```

### 3. Assuming Order in Parallel

```python
# results order is non-deterministic
results: Annotated[list, operator.add]
```

### 4. Expensive Operations in Same Super-step

All parallel nodes must complete before the super-step ends. One slow node blocks the others from "committing."

---

## Key Takeaways

1. **LangGraph uses message passing** — nodes communicate through state, not direct calls
2. **Super-steps are atomic units** — plan, execute, update, checkpoint
3. **Updates are invisible within a super-step** — nodes see state from before the step
4. **Super-steps are transactional** — failure rolls back all changes
5. **Parallel nodes need reducers** — LastValue allows only one update per step
6. **Checkpoints happen at super-step boundaries** — natural recovery points
7. **Node activation is based on incoming messages** — edges determine flow
8. **Order within parallel is not guaranteed** — don't rely on execution order

---

## Connection to Previous Concepts

|Concept|How Execution Model Applies|
|---|---|
|Reducers (Note 4)|Merge parallel updates at end of super-step|
|Nodes/Edges (Note 5)|Nodes execute in super-steps, edges determine activation|
|Checkpointing|Saves state at super-step boundaries|
|State schema|Defines channels that enable message passing|

---

_Sources: LangGraph Pregel documentation, Google Pregel paper (2010), LangGraph reference docs, community articles on LangGraph internals_