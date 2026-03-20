# Nodes and Edges

## The Core Abstraction

LangGraph models workflows as **directed graphs**:

- **Nodes** = Processing steps (functions that do work)
- **Edges** = Transitions (what happens next)

```
In short: nodes do the work, edges tell what to do next.
```

This is the fundamental abstraction. Everything else builds on it.

---

## Nodes

### What is a Node?

A node is a **Python function** that:

1. Receives the current state as input
2. Performs some computation or side effect
3. Returns updates to the state

```python
def my_node(state: State) -> dict:
    # Read from state
    query = state["query"]
    
    # Do work (LLM call, tool execution, computation, etc.)
    result = process(query)
    
    # Return state updates (partial is fine)
    return {"result": result}
```

### Node Function Signatures

Nodes can accept additional parameters beyond state:

```python
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

# Basic: just state
def node_basic(state: State) -> dict:
    return {"output": "done"}

# With config: access thread_id, metadata, callbacks
def node_with_config(state: State, config: RunnableConfig) -> dict:
    thread_id = config["configurable"]["thread_id"]
    return {"output": f"Thread: {thread_id}"}

# With runtime (v0.6+): access context, store, stream_writer
def node_with_runtime(state: State, runtime: Runtime[Context]) -> dict:
    user_id = runtime.context.user_id
    return {"output": f"User: {user_id}"}

# Async nodes
async def async_node(state: State) -> dict:
    result = await some_async_operation()
    return {"result": result}
```

### Adding Nodes to a Graph

```python
from langgraph.graph import StateGraph

graph = StateGraph(State)

# Add nodes with name → function mapping
graph.add_node("process", process_function)
graph.add_node("validate", validate_function)
graph.add_node("respond", respond_function)
```

The **name** is how you reference the node when adding edges.

### What Can a Node Do?

Nodes are just Python functions — they can do anything:

|Action|Example|
|---|---|
|Call an LLM|`llm.invoke(messages)`|
|Execute tools|`tool.invoke(input)`|
|Query a database|`db.execute(query)`|
|Call an API|`requests.get(url)`|
|Transform data|`parse_json(response)`|
|Make decisions|`if condition: return {"next": "a"}`|

**Key principle**: Nodes don't need to involve LLMs. They're just functions.

---

## Special Nodes: START and END

LangGraph provides two virtual nodes:

```python
from langgraph.graph import START, END
```

### START

The entry point. Where execution begins.

```python
graph.add_edge(START, "first_node")
```

### END

The terminal point. Where execution stops.

```python
graph.add_edge("last_node", END)
```

You can have multiple paths to END:

```python
graph.add_edge("success_node", END)
graph.add_edge("error_node", END)
```

---

## Edges

### What is an Edge?

An edge defines **which node executes next**. There are two types:

1. **Normal edges**: Fixed transitions (always go to this node)
2. **Conditional edges**: Dynamic routing (decide at runtime)

### Normal Edges

Fixed, unconditional transitions:

```python
graph.add_edge(START, "node_a")      # Start → A
graph.add_edge("node_a", "node_b")   # A → B
graph.add_edge("node_b", END)        # B → End
```

This creates a linear flow: START → A → B → END

### Conditional Edges

Dynamic routing based on state:

```python
def router(state: State) -> str:
    """Decide which node to go to next."""
    if state["needs_tool"]:
        return "tool_node"
    else:
        return "respond_node"

graph.add_conditional_edges(
    "decision_node",    # Source node
    router,             # Routing function
    {                   # Mapping (optional)
        "tool_node": "tool_node",
        "respond_node": "respond_node"
    }
)
```

The routing function:

- Receives the current state
- Returns a string (the name of the next node)
- Can return `END` to terminate

### Conditional Edge Variants

```python
# With explicit mapping
graph.add_conditional_edges(
    "source",
    router_function,
    {"option_a": "node_a", "option_b": "node_b", "done": END}
)

# With list (when return values match node names)
graph.add_conditional_edges(
    "source",
    router_function,
    ["node_a", "node_b"]  # Router must return "node_a" or "node_b"
)

# Inline lambda
graph.add_conditional_edges(
    "source",
    lambda state: "yes" if state["approved"] else "no",
    {"yes": "proceed", "no": "reject"}
)
```

---

## Common Patterns

### Pattern 1: Linear Flow

```python
graph.add_edge(START, "step_1")
graph.add_edge("step_1", "step_2")
graph.add_edge("step_2", "step_3")
graph.add_edge("step_3", END)
```

```
START → step_1 → step_2 → step_3 → END
```

### Pattern 2: Branching

```python
def router(state: State) -> str:
    if state["type"] == "A":
        return "handle_a"
    elif state["type"] == "B":
        return "handle_b"
    else:
        return "handle_default"

graph.add_edge(START, "classify")
graph.add_conditional_edges("classify", router)
graph.add_edge("handle_a", END)
graph.add_edge("handle_b", END)
graph.add_edge("handle_default", END)
```

```
                    ┌─→ handle_a ─→ END
START → classify ──┼─→ handle_b ─→ END
                    └─→ handle_default ─→ END
```

### Pattern 3: Loop (Cycle)

```python
def should_continue(state: State) -> str:
    if state["done"]:
        return "finish"
    else:
        return "process"

graph.add_edge(START, "process")
graph.add_conditional_edges("process", should_continue)
graph.add_edge("finish", END)
```

```
START → process ─┬─→ process (loop back)
                 └─→ finish → END
```

This is how agent loops work: keep processing until done.

### Pattern 4: Fan-Out / Fan-In (Parallel)

```python
from operator import add

class State(TypedDict):
    results: Annotated[list, add]  # Reducer for parallel updates

graph.add_edge(START, "split")
graph.add_edge("split", "worker_a")
graph.add_edge("split", "worker_b")
graph.add_edge("split", "worker_c")
graph.add_edge("worker_a", "merge")
graph.add_edge("worker_b", "merge")
graph.add_edge("worker_c", "merge")
graph.add_edge("merge", END)
```

```
            ┌─→ worker_a ─┐
START → split ─→ worker_b ─┼─→ merge → END
            └─→ worker_c ─┘
```

Workers execute in parallel. Reducer merges their outputs.

### Pattern 5: The ReAct Loop

The canonical agent pattern:

```python
def should_continue(state: State) -> str:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_continue)
graph.add_edge("tools", "agent")
```

```
START → agent ─┬─→ tools → agent (loop)
               └─→ END (when no tool calls)
```

---

## Conditional Entry Points

You can start at different nodes based on input:

```python
def entry_router(state: State) -> str:
    if state["fast_path"]:
        return "quick_response"
    return "full_processing"

graph.add_conditional_edges(START, entry_router)
```

---

## The Send API: Dynamic Parallelism

For map-reduce patterns where you don't know the number of parallel tasks upfront:

```python
from langgraph.types import Send

def generate_tasks(state: State) -> list[Send]:
    """Return a list of Send objects to fan out dynamically."""
    tasks = []
    for item in state["items"]:
        tasks.append(Send("process_item", {"item": item}))
    return tasks

graph.add_conditional_edges("split", generate_tasks)
```

Each `Send` creates a parallel branch with its own input state.

---

## Node Return Values

### Returning State Updates

Nodes return a dict with state updates:

```python
def my_node(state: State) -> dict:
    # Return only the fields you're updating
    return {
        "result": "computed value",
        "count": 1  # If using add reducer, adds 1
    }
```

### Returning Nothing

If a node has no updates, return empty dict:

```python
def logging_node(state: State) -> dict:
    print(f"Current state: {state}")
    return {}  # No state changes
```

### Returning Command (Advanced)

For combined state update + routing:

```python
from langgraph.types import Command

def node_with_command(state: State) -> Command:
    return Command(
        update={"result": "done"},
        goto="next_node"  # Override normal edge routing
    )
```

---

## Edge Execution Model

### Super-steps

LangGraph executes in **super-steps** (from the Pregel model):

1. All nodes in a super-step run in parallel
2. After all complete, state is merged
3. Next super-step begins

```
Super-step 1: [node_a, node_b, node_c] run in parallel
              State merged via reducers
Super-step 2: [node_d] runs
              State merged
Super-step 3: END
```

### Parallel Nodes in Same Super-step

When multiple edges lead to the same destination from parallel nodes:

```
split → worker_a ─┐
split → worker_b ─┼─→ merge
split → worker_c ─┘
```

All workers execute in the same super-step. `merge` executes in the next super-step after all workers complete.

---

## Debugging: Graph Visualization

LangGraph can visualize your graph:

```python
# Compile first
app = graph.compile()

# Get Mermaid diagram
print(app.get_graph().draw_mermaid())

# Or as PNG (requires graphviz)
from IPython.display import Image, display
display(Image(app.get_graph().draw_mermaid_png()))
```

This helps verify your edges are connected correctly.

---

## Common Mistakes

### Mistake 1: Orphaned Nodes

```python
graph.add_node("lonely_node", func)
# No edges to or from this node
# Compile will fail or warn
```

**Fix**: Every node needs at least one incoming edge.

### Mistake 2: Missing END

```python
graph.add_edge("last_node", "nowhere")  # "nowhere" doesn't exist
```

**Fix**: Ensure all paths eventually reach END.

### Mistake 3: Infinite Loop

```python
def always_continue(state: State) -> str:
    return "process"  # Never returns END

graph.add_conditional_edges("process", always_continue)
```

**Fix**: Always have a termination condition. LangGraph has `recursion_limit` as a safeguard.

### Mistake 4: Wrong Return Value in Router

```python
def router(state: State) -> str:
    return "node_x"  # But "node_x" doesn't exist or isn't in mapping
```

**Fix**: Router must return a value that maps to an existing node.

---

## Key Takeaways

1. **Nodes are functions** — they receive state, do work, return updates
2. **Edges are transitions** — normal (fixed) or conditional (dynamic)
3. **START and END** are virtual nodes marking entry and exit
4. **Conditional edges** enable branching and loops
5. **Super-steps** execute parallel nodes together, then merge state
6. **Router functions** must return strings matching node names or END
7. **The Send API** enables dynamic parallelism (map-reduce)
8. **Visualize your graph** to verify edge connections

---

## Summary Table

|Concept|Method|Purpose|
|---|---|---|
|Add node|`add_node(name, func)`|Register a processing step|
|Normal edge|`add_edge(from, to)`|Fixed transition|
|Conditional edge|`add_conditional_edges(from, router, mapping)`|Dynamic routing|
|Entry point|`add_edge(START, node)`|Where execution begins|
|Exit point|`add_edge(node, END)`|Where execution ends|
|Dynamic parallel|`Send(node, state)`|Fan-out at runtime|

---

_Sources: LangGraph documentation (langchain-ai.github.io/langgraph), LangGraph graph-api docs, LangGraph blog posts, community tutorials_