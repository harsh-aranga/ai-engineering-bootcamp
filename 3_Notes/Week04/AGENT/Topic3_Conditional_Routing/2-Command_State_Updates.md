# Command: State Updates with Dynamic Navigation

## The Problem Command Solves

In standard LangGraph, **state updates** and **routing decisions** are separate:

- Nodes return state updates: `return {"foo": "bar"}`
- Conditional edge functions decide routing: `return "next_node"`

This creates friction when a node needs to do **both** — update state AND decide where to go next.

**Example scenario:**

```python
def assess_quality(state):
    score = evaluate(state["document"])
    
    # I need to:
    # 1. Save the score to state
    # 2. Route to "approve" if score > 0.8, else "revise"
    
    # But I can only return state updates here!
    return {"quality_score": score}  # How do I also route?
```

Without `Command`, you'd need a separate conditional edge function that re-reads state and duplicates the routing logic.

## Enter Command

`Command` lets a node **update state AND specify the next node** in a single return.

```python
from langgraph.types import Command

def assess_quality(state) -> Command:
    score = evaluate(state["document"])
    
    # Decide routing
    next_node = "approve" if score > 0.8 else "revise"
    
    # Return BOTH state update AND routing decision
    return Command(
        update={"quality_score": score},  # State update
        goto=next_node                     # Next node
    )
```

## Command Syntax

### Basic Usage

```python
from langgraph.types import Command

def my_node(state) -> Command:
    return Command(
        update={"key": "value"},  # Dict of state updates
        goto="target_node"        # String: name of next node
    )
```

### Multiple Destinations (Fan-Out)

`goto` can be a list, sending execution to multiple nodes in parallel:

```python
def distribute_work(state) -> Command:
    return Command(
        update={"status": "distributed"},
        goto=["worker_a", "worker_b", "worker_c"]  # All three run in parallel
    )
```

### Update Only (No Routing)

If you omit `goto`, the graph follows its normal edges:

```python
def update_state_only(state) -> Command:
    return Command(
        update={"processed": True}
        # No goto → follows static edges defined in add_edge()
    )
```

### Routing Only (No Update)

If you omit `update`, just routes without changing state:

```python
def route_only(state) -> Command:
    next_node = "path_a" if state["condition"] else "path_b"
    return Command(goto=next_node)
```

## Type Annotations for Graph Visualization

When using `Command`, add type annotations so LangGraph Studio can visualize the possible paths:

```python
from typing import Literal
from langgraph.types import Command

def router_node(state) -> Command[Literal["node_a", "node_b", "node_c"]]:
    """Type hint tells LangGraph which nodes this can route to."""
    if state["intent"] == "search":
        return Command(goto="node_a")
    elif state["intent"] == "calculate":
        return Command(goto="node_b")
    else:
        return Command(goto="node_c")
```

Without the type hint, LangGraph can't draw edges from this node in the visualization.

## Command vs Conditional Edges

|Aspect|Conditional Edges|Command|
|---|---|---|
|**Where routing logic lives**|Separate function|Inside the node|
|**Can update state?**|No (edges don't update state)|Yes|
|**Defined when?**|Graph build time|Runtime|
|**Good for**|Simple routing based on existing state|Complex decisions that also update state|

### When to Use Conditional Edges

- Routing logic is simple (just reading a flag)
- Multiple nodes need the same routing logic
- You want routing visible in graph definition

```python
# Good for conditional edges: simple, reusable
def should_continue(state) -> str:
    return "continue" if state["attempts"] < 3 else "end"

builder.add_conditional_edges("worker", should_continue, {
    "continue": "worker",
    "end": END
})
```

### When to Use Command

- Routing decision depends on computation done in the node
- You need to update state AND route atomically
- Routing logic is complex or node-specific

```python
# Good for Command: computation + routing + state update
def evaluate_and_route(state) -> Command[Literal["pass", "fail", "retry"]]:
    result = run_evaluation(state["submission"])
    
    if result.score > 0.9:
        return Command(update={"result": result, "status": "passed"}, goto="pass")
    elif result.retryable:
        return Command(update={"attempts": state["attempts"] + 1}, goto="retry")
    else:
        return Command(update={"result": result, "status": "failed"}, goto="fail")
```

## Command with ends Parameter

When using `Command`, you must tell the graph builder which nodes your Command can route to:

```python
builder = StateGraph(AgentState)

builder.add_node("router", router_node, ends=["node_a", "node_b", "node_c"])
builder.add_node("node_a", handle_a)
builder.add_node("node_b", handle_b)
builder.add_node("node_c", handle_c)

# No add_edge from "router" needed — Command handles it dynamically
builder.add_edge(START, "router")
```

The `ends` parameter is required when:

- The node returns `Command` with `goto`
- You don't have static edges from that node

## Important: Command + Static Edges

**Commands add dynamic edges; they don't replace static edges.**

```python
builder.add_node("node_a", my_node)
builder.add_edge("node_a", "node_b")  # Static edge

def my_node(state) -> Command:
    return Command(goto="node_c")  # Dynamic edge

# Result: BOTH node_b AND node_c will execute!
```

If your node returns `Command(goto=...)`, don't also add a static `add_edge` from that node unless you want both paths to run.

## Full Example: Assessment Pipeline

```python
from typing import Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

class AssessmentState(TypedDict):
    document: str
    quality_score: float
    revision_count: int
    final_status: str

def assess_document(state: AssessmentState) -> Command[Literal["approve", "revise", "reject"]]:
    """Assess quality and route based on score."""
    # Simulate evaluation
    score = len(state["document"]) / 100  # Dummy scoring
    
    if score > 0.8:
        return Command(
            update={"quality_score": score, "final_status": "approved"},
            goto="approve"
        )
    elif state["revision_count"] < 3:
        return Command(
            update={"quality_score": score, "revision_count": state["revision_count"] + 1},
            goto="revise"
        )
    else:
        return Command(
            update={"quality_score": score, "final_status": "rejected"},
            goto="reject"
        )

def revise_document(state: AssessmentState) -> dict:
    """Revise and go back to assessment."""
    improved = state["document"] + " [revised]"
    return {"document": improved}

def approve_document(state: AssessmentState) -> dict:
    return {"final_status": "Document approved and published"}

def reject_document(state: AssessmentState) -> dict:
    return {"final_status": "Document rejected after max revisions"}

# Build graph
builder = StateGraph(AssessmentState)

builder.add_node("assess", assess_document, ends=["approve", "revise", "reject"])
builder.add_node("revise", revise_document)
builder.add_node("approve", approve_document)
builder.add_node("reject", reject_document)

builder.add_edge(START, "assess")
builder.add_edge("revise", "assess")  # Loop back after revision
builder.add_edge("approve", END)
builder.add_edge("reject", END)

graph = builder.compile()

# Run
result = graph.invoke({
    "document": "Short doc",
    "quality_score": 0.0,
    "revision_count": 0,
    "final_status": ""
})
print(result)
```

## Command with Subgraphs

`Command` can navigate across subgraph boundaries using `graph=Command.PARENT`:

```python
from langgraph.types import Command

def subgraph_node(state) -> Command:
    # Navigate to a node in the PARENT graph
    return Command(
        update={"result": "done"},
        goto="parent_node_name",
        graph=Command.PARENT  # Escape the subgraph
    )
```

This enables sophisticated multi-agent handoffs where an agent can "hand off" to a sibling agent by routing through the parent.

## Key Takeaways

1. **Command = update + goto** — Combines state mutation with routing in one return
2. **Use type hints** — `Command[Literal["a", "b"]]` enables visualization
3. **Use `ends` parameter** — Tell the builder which nodes Command can reach
4. **Commands add edges, don't replace** — Static edges still fire unless removed
5. **Good for atomic decisions** — When routing depends on computation that also updates state

---

**Next:** Note 3 covers parallel execution — static fan-out and the dynamic `Send` API.

_Sources: LangGraph docs (docs.langchain.com/oss/python/langgraph/graph-api), LangGraph Command API reference_