# State Schema with TypedDict

## What is State in LangGraph?

State is the **shared data structure** that flows through your graph. Every node:

1. Receives the current state as input
2. Performs some computation
3. Returns updates to the state

Think of state as a **shared blackboard** — nodes read from it, write to it, and pass it along.

```python
from typing import TypedDict

class State(TypedDict):
    query: str
    response: str
    step_count: int
```

---

## Why TypedDict?

LangGraph supports three options for state schemas:

1. **TypedDict** (recommended)
2. Pydantic BaseModel
3. Dataclass

**TypedDict is the default choice** for LangGraph because:

|Feature|TypedDict|Pydantic|Dataclass|
|---|---|---|---|
|Partial updates|✅ Natural|⚠️ Awkward|⚠️ Awkward|
|Runtime overhead|None|Validation cost|Minimal|
|Reducer support|✅ Clean with Annotated|Possible but verbose|Possible but verbose|
|IDE support|✅ Full type hints|✅ Full|✅ Full|
|Caching behavior|Predictable|Can cause issues|Predictable|

**Key insight**: Nodes return _partial_ updates (only the fields they modify), not the entire state. TypedDict makes this natural — you just return a dict with the keys you want to update.

```python
# Node returns partial update — only the fields it modifies
def my_node(state: State) -> dict:
    # Don't need to return all fields
    return {"response": "computed result"}  # Only update 'response'
```

With Pydantic or Dataclass, partial updates are awkward because they expect complete objects.

---

## Basic State Definition

```python
from typing import TypedDict

class State(TypedDict):
    # Simple scalar fields
    query: str
    response: str
    count: int
    
    # Optional fields
    error: str | None
    
    # Complex fields
    metadata: dict
    history: list[str]
```

### Using the State

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(State)

def process(state: State) -> dict:
    # Read from state
    query = state["query"]
    count = state["count"]
    
    # Return updates (partial is fine)
    return {
        "response": f"Processed: {query}",
        "count": count + 1
    }

graph.add_node("process", process)
graph.add_edge(START, "process")
graph.add_edge("process", END)

app = graph.compile()

# Invoke with initial state
result = app.invoke({
    "query": "hello",
    "response": "",
    "count": 0,
    "error": None,
    "metadata": {},
    "history": []
})
```

---

## Default Update Behavior: Overwrite

Without any special configuration, **updates overwrite** the existing value:

```python
class State(TypedDict):
    count: int
    items: list[str]

# Initial state
{"count": 0, "items": ["a"]}

# Node returns
{"count": 5, "items": ["b"]}

# Result: complete overwrite
{"count": 5, "items": ["b"]}  # "a" is gone!
```

This is fine for scalar fields but problematic for lists you want to accumulate.

---

## Annotated Types and Reducers

To control _how_ updates are applied, use `Annotated` with a **reducer function**:

```python
from typing import Annotated
from typing_extensions import TypedDict
from operator import add

class State(TypedDict):
    count: int                              # Overwrite (default)
    items: Annotated[list[str], add]        # Append via operator.add
```

Now:

```python
# Initial state
{"count": 0, "items": ["a"]}

# Node returns
{"count": 5, "items": ["b"]}

# Result: count overwrites, items appends
{"count": 5, "items": ["a", "b"]}  # "a" is preserved!
```

### How Annotated Works

```python
Annotated[<type>, <reducer_function>]
```

- **Type**: The field's type (e.g., `list[str]`)
- **Reducer**: A function that takes `(current_value, new_value)` and returns the merged result

```python
# operator.add for lists: concatenates them
operator.add(["a"], ["b"])  # → ["a", "b"]

# Custom reducer
def my_reducer(current: list, new: list) -> list:
    return current + new
```

---

## Common Reducer Patterns

### 1. List Concatenation

```python
from operator import add

class State(TypedDict):
    items: Annotated[list[str], add]
```

### 2. Counter Increment

```python
class State(TypedDict):
    count: Annotated[int, add]

# Node returns {"count": 1} → adds 1 to current count
```

### 3. Dictionary Merge

```python
class State(TypedDict):
    metadata: Annotated[dict, lambda curr, new: {**curr, **new}]
```

### 4. Custom Logic

```python
def keep_last_n(n: int):
    def reducer(current: list, new: list) -> list:
        combined = current + new
        return combined[-n:]  # Keep only last n items
    return reducer

class State(TypedDict):
    recent_actions: Annotated[list[str], keep_last_n(10)]
```

### 5. Set Union (Deduplicate)

```python
def set_union(current: list, new: list) -> list:
    return list(set(current) | set(new))

class State(TypedDict):
    seen_ids: Annotated[list[str], set_union]
```

---

## The Messages Pattern

The most common state pattern in LangGraph agents is a **messages list** — the conversation history between user, assistant, and tools.

### Manual Definition

```python
from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

def add_messages(current: list, new: list) -> list:
    """Append new messages to existing list."""
    return current + new

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

### Using LangGraph's Built-in

LangGraph provides `add_messages` with extra features (ID handling, message replacement):

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

The built-in `add_messages` reducer:

- Appends new messages to the list
- Handles message IDs properly
- Supports replacing messages by ID (useful for streaming updates)

---

## MessagesState: The Prebuilt Shortcut

For agents that primarily work with messages, LangGraph provides `MessagesState`:

```python
from langgraph.graph import MessagesState

# This is equivalent to:
# class MessagesState(TypedDict):
#     messages: Annotated[list[AnyMessage], add_messages]
```

### Using MessagesState Directly

```python
from langgraph.graph import StateGraph, MessagesState, START, END

graph = StateGraph(MessagesState)

def chatbot(state: MessagesState) -> dict:
    # state["messages"] is the conversation history
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

graph.add_node("chatbot", chatbot)
graph.add_edge(START, "chatbot")
graph.add_edge("chatbot", END)

app = graph.compile()
```

### Extending MessagesState

Usually you need more than just messages. Subclass to add fields:

```python
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    # Inherits: messages: Annotated[list[AnyMessage], add_messages]
    
    # Add your own fields
    user_id: str
    session_data: dict
    tool_outputs: list[dict]
```

---

## Channels: The Internal Name

LangGraph internally calls each state field a **channel**. You'll see this term in documentation:

```python
class State(TypedDict):
    query: str           # This is the "query" channel
    messages: list       # This is the "messages" channel
```

Channels are just keys in your TypedDict. The terminology comes from LangGraph's Pregel-inspired message-passing model, where data flows through named channels.

---

## State Initialization

When you invoke the graph, you provide the initial state:

```python
# All fields should have initial values
result = app.invoke({
    "query": "hello",
    "response": "",
    "count": 0
})
```

For fields with reducers, the initial value matters:

- List with `add` reducer: Start with `[]`
- Int with `add` reducer: Start with `0`
- Dict with merge reducer: Start with `{}`

---

## Partial Updates: The Key Pattern

**Critical concept**: Nodes return only the fields they modify, not the entire state.

```python
class State(TypedDict):
    query: str
    response: str
    count: int
    history: Annotated[list[str], add]

def step_one(state: State) -> dict:
    # Only update 'response' and 'history'
    # 'query' and 'count' are untouched
    return {
        "response": f"Processed: {state['query']}",
        "history": ["step_one completed"]
    }

def step_two(state: State) -> dict:
    # Only update 'count'
    return {"count": state["count"] + 1}
```

LangGraph merges these partial updates:

- Fields without reducers: Overwrite
- Fields with reducers: Apply reducer function

---

## Anti-Pattern: Mutating State Directly

**Never mutate state directly.** Always return updates.

```python
# ❌ BAD: Direct mutation
def bad_node(state: State) -> dict:
    state["count"] += 1              # Mutating in place
    state["items"].append("new")      # Mutating in place
    return state                      # Returns mutated original

# ✅ GOOD: Return updates
def good_node(state: State) -> dict:
    return {
        "count": state["count"] + 1,  # New value
        "items": ["new"]              # Reducer handles append
    }
```

Why this matters:

- Direct mutation breaks checkpointing (state history is corrupted)
- Direct mutation breaks LangGraph's tracking mechanisms
- Reducers don't get called if you mutate in place

---

## Input and Output Schemas

You can define separate schemas for input/output to hide internal state:

```python
class InputState(TypedDict):
    query: str

class OutputState(TypedDict):
    response: str
    confidence: float

class FullState(TypedDict):
    query: str
    response: str
    confidence: float
    # Internal fields not exposed
    intermediate_results: list
    debug_info: dict

graph = StateGraph(
    state_schema=FullState,
    input_schema=InputState,    # Only require 'query' on input
    output_schema=OutputState   # Only return 'response' and 'confidence'
)
```

This lets you:

- Accept minimal input (user doesn't need to provide all fields)
- Return clean output (hide internal implementation details)

---

## TypedDict vs Pydantic: When to Use Which

### Use TypedDict (Default)

- Internal graph state
- Prototyping
- When you need partial updates
- When runtime validation isn't critical

### Use Pydantic

- Input validation at graph boundaries
- When you need strict type coercion
- API response schemas
- When validation errors should fail loudly

**Common pattern**: TypedDict for state, Pydantic for inputs/outputs.

```python
from pydantic import BaseModel
from typing import TypedDict

# Pydantic for external interface
class UserQuery(BaseModel):
    query: str
    max_results: int = 10

# TypedDict for internal state
class State(TypedDict):
    query: str
    max_results: int
    results: list
    internal_data: dict

# Validate input, then convert to state
def handle_request(user_query: UserQuery) -> dict:
    initial_state = {
        "query": user_query.query,
        "max_results": user_query.max_results,
        "results": [],
        "internal_data": {}
    }
    return app.invoke(initial_state)
```

---

## Key Takeaways

1. **TypedDict is the default** for LangGraph state — lightweight, partial-update friendly
2. **Use Annotated with reducers** to control how updates merge (append vs overwrite)
3. **Nodes return partial updates** — only the fields they modify
4. **MessagesState** is the prebuilt shortcut for message-based agents
5. **Never mutate state directly** — always return new values
6. **Channels** is just the internal name for state fields
7. **Input/output schemas** let you hide internal state from external interface

---

_Sources: LangGraph documentation (langchain-ai.github.io/langgraph), LangGraph graph-api docs, LangGraph GitHub source (message.py), Real Python LangGraph tutorial_