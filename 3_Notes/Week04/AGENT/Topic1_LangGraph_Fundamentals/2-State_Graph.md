# StateGraph and Compilation

## StateGraph: The Blueprint

`StateGraph` is the main class you use to define a LangGraph workflow. It's the **builder** — you add nodes, add edges, and then compile it into a runnable graph.

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

# 1. Define state schema
class MyState(TypedDict):
    message: str
    count: int

# 2. Create StateGraph with that schema
graph = StateGraph(MyState)

# 3. Add nodes and edges
graph.add_node("process", process_function)
graph.add_edge(START, "process")
graph.add_edge("process", END)

# 4. Compile into runnable
app = graph.compile()

# 5. Run
result = app.invoke({"message": "hello", "count": 0})
```

**Key insight**: StateGraph is parameterized by your state schema. This schema defines:

- What data flows through the graph
- What fields nodes can read
- What fields nodes can update

---

## The Builder Pattern

StateGraph uses a fluent builder API:

```python
graph = StateGraph(State)

# Add nodes (name → function)
graph.add_node("node_a", func_a)
graph.add_node("node_b", func_b)
graph.add_node("node_c", func_c)

# Add edges (from → to)
graph.add_edge(START, "node_a")           # Entry point
graph.add_edge("node_a", "node_b")        # Fixed transition
graph.add_conditional_edges(              # Branching
    "node_b",
    routing_function,
    {"path_1": "node_c", "path_2": END}
)
graph.add_edge("node_c", END)             # Exit point

# Compile
app = graph.compile()
```

### Available Methods

|Method|Purpose|
|---|---|
|`add_node(name, func)`|Register a node|
|`add_edge(from, to)`|Fixed transition|
|`add_conditional_edges(from, router, mapping)`|Conditional branching|
|`set_entry_point(name)`|Deprecated — use `add_edge(START, name)`|
|`set_finish_point(name)`|Deprecated — use `add_edge(name, END)`|
|`compile(**options)`|Build runnable graph|

---

## What Happens at Compile Time

When you call `graph.compile()`, LangGraph:

1. **Validates structure**
    
    - No orphaned nodes (nodes with no incoming edges)
    - Entry point exists (edge from START)
    - Exit point reachable (path to END)
    - No undefined node references
2. **Builds the execution engine**
    
    - Creates internal channels for state flow
    - Sets up the Pregel-style message passing system
    - Wires up the streaming infrastructure
3. **Configures runtime options**
    
    - Checkpointing (if provided)
    - Interrupt points (if specified)
    - Store for long-term memory (if provided)

**Important**: You MUST compile before invoking. The graph definition (`StateGraph`) is not runnable — only the compiled result (`CompiledStateGraph`) is.

```python
# This is just a builder
graph = StateGraph(State)
graph.add_node(...)

# This doesn't work
graph.invoke(...)  # ❌ AttributeError

# You must compile first
app = graph.compile()
app.invoke(...)    # ✅ Works
```

---

## Compile Options

The `compile()` method accepts several runtime configuration options:

```python
app = graph.compile(
    checkpointer=checkpointer,      # Enable state persistence
    interrupt_before=["node_x"],    # Pause BEFORE these nodes
    interrupt_after=["node_y"],     # Pause AFTER these nodes
    store=memory_store,             # Long-term memory store
    debug=True,                     # Enable debug logging
)
```

### 1. Checkpointer (State Persistence)

A checkpointer saves state after every super-step. This enables:

- **Fault tolerance**: Resume from failures
- **Human-in-the-loop**: Pause, modify state, resume
- **Time travel**: Inspect/restore previous states

```python
from langgraph.checkpoint.memory import MemorySaver

# In-memory (for development)
checkpointer = MemorySaver()

# Production options:
# from langgraph.checkpoint.postgres import PostgresSaver
# from langgraph.checkpoint.sqlite import SqliteSaver

app = graph.compile(checkpointer=checkpointer)

# Must provide thread_id to use checkpointing
config = {"configurable": {"thread_id": "conversation-123"}}
result = app.invoke(initial_state, config)
```

**Without a checkpointer**: No persistence. Graph runs start-to-finish, no resume capability.

**With a checkpointer**: State saved after each step. Can pause, inspect, modify, resume.

### 2. Interrupt Points (Static Breakpoints)

Pause execution at specific nodes — useful for debugging or human review:

```python
app = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["sensitive_action"],  # Pause BEFORE node runs
    interrupt_after=["data_fetch"],         # Pause AFTER node runs
)
```

**`interrupt_before`**: Graph pauses just before the specified nodes execute. The node has NOT run yet.

**`interrupt_after`**: Graph pauses immediately after the specified nodes execute. The node HAS run, results in state.

```python
# Example: Review before final action
app = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["send_email"]  # Pause before sending
)

config = {"configurable": {"thread_id": "email-workflow"}}

# First invoke — runs until interrupt
result = app.invoke(initial_state, config)
# Graph is now paused before "send_email"

# Human reviews state, decides to proceed
# Resume by invoking with None
result = app.invoke(None, config)
# Graph continues from where it paused
```

**Note**: Static interrupts (`interrupt_before`/`interrupt_after`) are compile-time decisions. For dynamic, runtime interrupts, use the `interrupt()` function inside nodes (covered in later notes on human-in-the-loop).

### 3. Store (Long-Term Memory)

For cross-thread memory persistence:

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
app = graph.compile(checkpointer=checkpointer, store=store)
```

The store allows nodes to save/retrieve data that persists across different conversations (threads).

---

## The Compiled Graph Object

After compilation, you get a `CompiledStateGraph` (internally, a `Pregel` instance):

```python
app = graph.compile()
print(type(app))  # <class 'langgraph.graph.state.CompiledStateGraph'>
```

### Key Methods on Compiled Graph

|Method|Purpose|
|---|---|
|`invoke(input, config)`|Run graph synchronously, return final state|
|`stream(input, config)`|Run graph, yield events as they happen|
|`ainvoke(input, config)`|Async version of invoke|
|`astream(input, config)`|Async version of stream|
|`get_state(config)`|Get current state snapshot (requires checkpointer)|
|`get_state_history(config)`|Get all state snapshots (requires checkpointer)|
|`update_state(config, values)`|Manually modify state (requires checkpointer)|
|`get_graph()`|Get graph structure for visualization|

### Running the Graph

```python
# Basic invocation
result = app.invoke({"message": "hello", "count": 0})
print(result)  # Final state after all nodes run

# With config (for checkpointing)
config = {"configurable": {"thread_id": "my-thread"}}
result = app.invoke({"message": "hello", "count": 0}, config)

# Streaming
for event in app.stream({"message": "hello", "count": 0}):
    print(event)  # See each step as it happens
```

---

## Definition vs. Compiled: Mental Model

```
┌─────────────────────────────────────────────────────────────┐
│                     DEFINITION PHASE                         │
│                                                              │
│   StateGraph(State)                                          │
│       │                                                      │
│       ├── add_node("a", func_a)                             │
│       ├── add_node("b", func_b)                             │
│       ├── add_edge(START, "a")                              │
│       ├── add_edge("a", "b")                                │
│       └── add_edge("b", END)                                │
│                                                              │
│   This is just a BLUEPRINT. Not runnable.                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ .compile()
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     RUNTIME PHASE                            │
│                                                              │
│   CompiledStateGraph                                         │
│       │                                                      │
│       ├── .invoke()     → Run and return final state        │
│       ├── .stream()     → Run and yield events              │
│       ├── .get_state()  → Inspect current state             │
│       └── .update_state() → Modify state manually           │
│                                                              │
│   This is RUNNABLE. Has execution engine, channels, etc.    │
└─────────────────────────────────────────────────────────────┘
```

---

## Input and Output Schemas

By default, the state schema is used for both input and output. You can customize this:

```python
from typing import TypedDict

class InputState(TypedDict):
    query: str

class OutputState(TypedDict):
    answer: str
    sources: list[str]

class FullState(TypedDict):
    query: str
    answer: str
    sources: list[str]
    intermediate_data: dict  # Internal, not exposed

graph = StateGraph(
    state_schema=FullState,
    input_schema=InputState,   # Only these fields required on input
    output_schema=OutputState  # Only these fields returned on output
)
```

This lets you:

- Accept minimal input (don't require all state fields)
- Return clean output (hide internal fields)

---

## Context Schema (Run-Scoped Configuration)

For configuration that's fixed for an entire run but not part of state:

```python
from langgraph.runtime import Runtime

class Context(TypedDict):
    api_key: str
    max_retries: int

class State(TypedDict):
    message: str

graph = StateGraph(state_schema=State, context_schema=Context)

def my_node(state: State, runtime: Runtime[Context]) -> dict:
    # Access context via runtime
    api_key = runtime.context.get("api_key")
    return {"message": f"Using API key: {api_key[:4]}..."}

graph.add_node("my_node", my_node)
```

Context is provided at runtime, not stored in state.

---

## Common Patterns

### Pattern 1: Basic Linear Flow

```python
graph = StateGraph(State)
graph.add_node("step_1", step_1)
graph.add_node("step_2", step_2)
graph.add_node("step_3", step_3)

graph.add_edge(START, "step_1")
graph.add_edge("step_1", "step_2")
graph.add_edge("step_2", "step_3")
graph.add_edge("step_3", END)

app = graph.compile()
```

### Pattern 2: With Branching

```python
def router(state: State) -> str:
    if state["needs_review"]:
        return "review"
    return "complete"

graph = StateGraph(State)
graph.add_node("process", process)
graph.add_node("review", review)
graph.add_node("complete", complete)

graph.add_edge(START, "process")
graph.add_conditional_edges("process", router, {
    "review": "review",
    "complete": "complete"
})
graph.add_edge("review", "complete")
graph.add_edge("complete", END)

app = graph.compile()
```

### Pattern 3: With Checkpointing

```python
from langgraph.checkpoint.memory import MemorySaver

graph = StateGraph(State)
# ... add nodes and edges ...

app = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["final_action"]
)

# Run with thread ID
config = {"configurable": {"thread_id": "workflow-1"}}
result = app.invoke(initial_state, config)

# If interrupted, resume later
result = app.invoke(None, config)
```

---

## Pregel Heritage

LangGraph's execution model is inspired by Google's Pregel system (used for large-scale graph processing):

- **Message passing**: Nodes communicate by sending state updates
- **Super-steps**: Execution proceeds in discrete steps; all nodes in a step run "simultaneously"
- **Channels**: State fields are implemented as channels that can be read/written

You don't need to understand Pregel internals to use LangGraph, but it explains:

- Why state updates are "messages" that get merged
- Why parallel nodes in the same super-step don't see each other's updates
- Why the compiled graph is called a "Pregel" instance internally

---

## Key Takeaways

1. **StateGraph is the builder**, CompiledStateGraph is the runnable
2. **You must compile** before invoking — definition ≠ execution
3. **Compile-time options** configure runtime behavior: checkpointing, interrupts, memory
4. **Checkpointer is required** for persistence, human-in-loop, fault tolerance
5. **Static interrupts** (`interrupt_before`/`interrupt_after`) are set at compile time; dynamic interrupts use `interrupt()` function
6. **Input/output schemas** let you control the public interface vs. internal state

---

_Sources: LangGraph documentation (langchain-ai.github.io/langgraph), LangGraph Python reference (reference.langchain.com), LangChain blog on LangGraph (February 2024)_