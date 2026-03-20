# Reducers: How State Updates Work

## The Core Problem

When a node returns state updates, LangGraph needs to know: **How do I merge this update into the existing state?**

Two possibilities:

1. **Overwrite**: Replace the old value with the new value
2. **Merge**: Combine the old and new values somehow

Without explicit instructions, LangGraph defaults to overwrite. But overwrite breaks when you want to accumulate data (like message history) or when parallel nodes update the same field.

---

## What is a Reducer?

A **reducer** is a function that takes two values — the current state value and the new update — and returns the merged result.

```python
def reducer(current_value, new_value) -> merged_value:
    # Combine current and new somehow
    return merged_value
```

Reducers are **pure functions**: same inputs always produce same outputs, no side effects.

---

## Default Behavior: Overwrite

Without a reducer, updates **overwrite** the existing value:

```python
from typing import TypedDict

class State(TypedDict):
    count: int
    items: list[str]

# Initial state
{"count": 0, "items": ["a", "b"]}

# Node returns
{"count": 5, "items": ["c"]}

# Result: complete overwrite
{"count": 5, "items": ["c"]}  # "a" and "b" are gone!
```

This is fine for scalar values that should be replaced. It's problematic for:

- Lists you want to accumulate (message history)
- Counters you want to increment
- Dictionaries you want to merge

---

## Attaching Reducers with Annotated

Use Python's `Annotated` type to attach a reducer to a field:

```python
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    count: int                          # No reducer → overwrite
    items: Annotated[list[str], add]    # Reducer → concatenate lists
```

### Syntax

```python
Annotated[<type>, <reducer_function>]
```

- **Type**: The field's type (e.g., `list[str]`, `int`)
- **Reducer**: A callable that takes `(current, new)` and returns merged result

---

## Common Built-in Reducers

### 1. `operator.add` — List Concatenation

```python
from operator import add

class State(TypedDict):
    messages: Annotated[list[str], add]

# Current: ["hello"]
# Update:  ["world"]
# Result:  ["hello", "world"]
```

`operator.add` works differently for different types:

- **Lists**: Concatenation (`[1, 2] + [3] = [1, 2, 3]`)
- **Integers**: Addition (`5 + 3 = 8`)
- **Strings**: Concatenation (`"hello" + "world" = "helloworld"`)

### 2. `operator.add` — Integer Accumulation

```python
from operator import add

class State(TypedDict):
    total: Annotated[int, add]

# Current: 10
# Update:  5
# Result:  15
```

Nodes return the **increment**, not the new total:

```python
def my_node(state: State) -> dict:
    # Don't do: return {"total": state["total"] + 5}
    # Do:       return {"total": 5}  # Reducer adds this to current
    return {"total": 5}
```

---

## LangGraph's Built-in: `add_messages`

For message-based agents, LangGraph provides `add_messages` with extra intelligence:

```python
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

**What `add_messages` does:**

1. Appends new messages to the list
2. Handles message IDs properly
3. If a new message has the same ID as an existing one, **replaces** it (useful for streaming updates)

This is more sophisticated than plain `operator.add`.

---

## Custom Reducer Functions

You can define any reducer function:

```python
# Keep only last N items
def keep_last_n(n: int):
    def reducer(current: list, new: list) -> list:
        combined = current + new
        return combined[-n:]
    return reducer

class State(TypedDict):
    recent_actions: Annotated[list[str], keep_last_n(5)]
```

### More Examples

```python
# Dictionary merge (shallow)
def merge_dicts(current: dict, new: dict) -> dict:
    return {**current, **new}

class State(TypedDict):
    metadata: Annotated[dict, merge_dicts]
```

```python
# Set union (deduplicate)
def set_union(current: list, new: list) -> list:
    return list(set(current) | set(new))

class State(TypedDict):
    seen_ids: Annotated[list[str], set_union]
```

```python
# Take maximum
def take_max(current: float, new: float) -> float:
    return max(current, new)

class State(TypedDict):
    highest_score: Annotated[float, take_max]
```

```python
# Timestamps on messages
from datetime import datetime

def add_timestamped(current: list, new: list) -> list:
    for msg in new:
        if "timestamp" not in msg:
            msg["timestamp"] = datetime.now().isoformat()
    return current + new

class State(TypedDict):
    events: Annotated[list[dict], add_timestamped]
```

---

## Why Reducers Matter: Parallel Execution

The most critical use case for reducers is **parallel node execution**.

### The Problem

```
        ┌──────────┐
        │  Node A  │
        └────┬─────┘
             │
     ┌───────┴───────┐
     ▼               ▼
┌─────────┐     ┌─────────┐
│ Node B  │     │ Node C  │   ← Run in PARALLEL
└────┬────┘     └────┬────┘
     │               │
     └───────┬───────┘
             ▼
        ┌──────────┐
        │  Node D  │
        └──────────┘
```

When B and C run in parallel, both might update the same field. Without a reducer:

```
InvalidUpdateError: At key 'items': Can receive only one value per step.
Use an Annotated key to handle multiple values.
```

LangGraph **refuses to proceed** because it doesn't know how to merge the updates.

### The Solution

Add a reducer:

```python
class State(TypedDict):
    items: Annotated[list[str], add]  # Now parallel updates are merged
```

Now:

- Node B returns `{"items": ["from_b"]}`
- Node C returns `{"items": ["from_c"]}`
- Reducer merges: `["from_b", "from_c"]` (order may vary!)

---

## InvalidUpdateError: The Signal

When you see:

```
InvalidUpdateError: At key 'foo': Can receive only one value per step.
Use an Annotated key to handle multiple values.
```

This means:

1. Two or more nodes in the same super-step tried to update the same field
2. That field has no reducer
3. LangGraph doesn't know how to merge

**Fix**: Add a reducer to that field.

---

## Super-steps and Update Ordering

LangGraph executes nodes in **super-steps** (inspired by Pregel/BSP model):

1. All nodes in a super-step run in parallel
2. Each node works on its own copy of the state
3. After all nodes finish, results are merged using reducers
4. Next super-step begins with the merged state

**Important**: Within a parallel super-step, update order is **not guaranteed**.

```python
# Nodes B and C run in parallel
# B returns {"items": ["b"]}
# C returns {"items": ["c"]}

# Result could be ["b", "c"] or ["c", "b"]
```

If you need deterministic ordering, include a sort key:

```python
class State(TypedDict):
    items: Annotated[list[tuple[int, str]], add]  # (priority, value)

# Then sort in the next node
def sort_items(state: State) -> dict:
    sorted_items = sorted(state["items"], key=lambda x: x[0])
    return {"items": sorted_items}
```

---

## Bypassing Reducers: Overwrite

Sometimes you want to **reset** a field, ignoring the reducer. Use `Overwrite`:

```python
from langgraph.types import Overwrite

class State(TypedDict):
    messages: Annotated[list, add_messages]

def reset_node(state: State) -> dict:
    # Bypass reducer, directly set value
    return {"messages": Overwrite([])}
```

`Overwrite` tells LangGraph: "Don't apply the reducer, just set this value directly."

---

## Reducers and Checkpointing

Reducers interact with checkpointing:

1. **After each super-step**, state is checkpointed
2. **Reducer logic is applied** before checkpoint
3. **On resume**, execution continues from checkpointed state

This means:

- Failed nodes don't corrupt state (transactional super-steps)
- Successful nodes' updates are preserved via reducers
- Replay works correctly because reducers are deterministic

---

## Reducer Design Rules

### 1. Reducers Must Be Pure

```python
# ❌ BAD: Side effects
def bad_reducer(current, new):
    print(f"Merging {new}")  # Side effect
    global counter           # Modifying global state
    counter += 1
    return current + new

# ✅ GOOD: Pure function
def good_reducer(current, new):
    return current + new
```

### 2. Reducers Must Be Deterministic

```python
# ❌ BAD: Non-deterministic
import random
def bad_reducer(current, new):
    if random.random() > 0.5:
        return current + new
    return new + current

# ✅ GOOD: Deterministic
def good_reducer(current, new):
    return current + new  # Always same result for same inputs
```

### 3. Handle None/Empty Cases

```python
def safe_reducer(current, new):
    if current is None:
        current = []
    if new is None:
        return current
    return current + new
```

### 4. Don't Mutate Inputs

```python
# ❌ BAD: Mutates current
def bad_reducer(current, new):
    current.extend(new)  # Modifies current in place
    return current

# ✅ GOOD: Creates new value
def good_reducer(current, new):
    return current + new  # Returns new list
```

---

## Common Patterns Summary

|Use Case|Reducer|Example|
|---|---|---|
|Append to list|`operator.add`|Message history|
|Increment counter|`operator.add`|Step counter|
|Merge dictionaries|`lambda c, n: {**c, **n}`|Metadata accumulation|
|Keep last N|Custom|Sliding window|
|Deduplicate|Set union|Seen IDs|
|Take max/min|`max` / `min`|High score|
|Message handling|`add_messages`|Agent conversations|

---

## Mental Model

```
┌─────────────────────────────────────────────────────────────┐
│                    STATE UPDATE FLOW                        │
│                                                              │
│   Current State                                              │
│   {"items": ["a", "b"], "count": 5}                         │
│                │                                             │
│                ▼                                             │
│   ┌────────────────────────┐                                │
│   │      Node Runs         │                                │
│   │  Returns: {"items": ["c"], "count": 2}                  │
│   └────────────────────────┘                                │
│                │                                             │
│                ▼                                             │
│   ┌────────────────────────┐                                │
│   │   For each field:      │                                │
│   │   - Has reducer? → Apply reducer(current, new)          │
│   │   - No reducer?  → Overwrite with new                   │
│   └────────────────────────┘                                │
│                │                                             │
│                ▼                                             │
│   New State                                                  │
│   items: ["a", "b"] + ["c"] = ["a", "b", "c"]  (reducer)    │
│   count: 2  (overwrite, no reducer)                         │
│                                                              │
│   {"items": ["a", "b", "c"], "count": 2}                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **Reducers control how updates merge** — overwrite vs. combine
2. **No reducer = overwrite** — field is replaced completely
3. **Use `Annotated[type, reducer]`** to attach reducers
4. **`operator.add`** works for lists (concat) and ints (add)
5. **`add_messages`** is the smart reducer for message lists
6. **Parallel nodes require reducers** — or you get `InvalidUpdateError`
7. **Reducers must be pure and deterministic** — for checkpointing to work
8. **Use `Overwrite`** to bypass a reducer when needed
9. **Update order in parallel is not guaranteed** — design accordingly

---

_Sources: LangGraph documentation (langchain-ai.github.io/langgraph), LangGraph use-graph-api docs, LangGraph GitHub issues on InvalidUpdateError, community articles on state management_