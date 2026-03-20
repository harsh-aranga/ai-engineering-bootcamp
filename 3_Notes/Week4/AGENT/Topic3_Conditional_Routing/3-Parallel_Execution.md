# Parallel Execution: Static Fan-Out and Dynamic Send API

## Why Parallel Execution Matters

Sequential execution is simple but slow:

```
Query → Search ArXiv (2s) → Search Wikipedia (2s) → Combine → Response
Total: 4 seconds
```

Parallel execution cuts latency:

```
Query → Search ArXiv (2s)  ─┬→ Combine → Response
      → Search Wikipedia (2s)─┘
Total: 2 seconds (longest branch)
```

When operations are **independent** (don't depend on each other's output), run them in parallel.

## Two Types of Parallelism in LangGraph

|Type|Defined When|Use Case|
|---|---|---|
|**Static Fan-Out**|Graph build time|Known, fixed parallel branches|
|**Dynamic Fan-Out (Send)**|Runtime|Variable number of parallel tasks|

---

## Static Fan-Out: Multiple Edges from One Node

Add multiple edges from the same source node. LangGraph automatically runs destinations in parallel.

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
import operator

class ResearchState(TypedDict):
    query: str
    results: Annotated[list, operator.add]  # Reducer: concatenate lists

def search_arxiv(state: ResearchState) -> dict:
    # Simulate ArXiv search
    return {"results": [f"ArXiv result for: {state['query']}"]}

def search_wikipedia(state: ResearchState) -> dict:
    # Simulate Wikipedia search
    return {"results": [f"Wikipedia result for: {state['query']}"]}

def search_news(state: ResearchState) -> dict:
    # Simulate news search
    return {"results": [f"News result for: {state['query']}"]}

def combine_results(state: ResearchState) -> dict:
    # All parallel results are already merged via reducer
    return {"results": state["results"]}

# Build graph with static fan-out
builder = StateGraph(ResearchState)

builder.add_node("arxiv", search_arxiv)
builder.add_node("wikipedia", search_wikipedia)
builder.add_node("news", search_news)
builder.add_node("combine", combine_results)

# Fan-out: START connects to three nodes
builder.add_edge(START, "arxiv")
builder.add_edge(START, "wikipedia")
builder.add_edge(START, "news")

# Fan-in: All three connect to combine
builder.add_edge("arxiv", "combine")
builder.add_edge("wikipedia", "combine")
builder.add_edge("news", "combine")

builder.add_edge("combine", END)

graph = builder.compile()
```

### How It Works: Supersteps

LangGraph executes in **supersteps**:

- Nodes in the same superstep run **in parallel**
- The next superstep waits for **all** nodes in the current superstep to complete

```
Superstep 1: [arxiv, wikipedia, news]  ← All run simultaneously
Superstep 2: [combine]                  ← Waits for all three to finish
```

### Critical: Reducers for Parallel State Updates

When parallel nodes update the **same state key**, you need a **reducer** to merge results:

```python
from typing import Annotated
import operator

class State(TypedDict):
    # WITHOUT reducer: last write wins (race condition!)
    results_bad: list
    
    # WITH reducer: all results concatenated
    results_good: Annotated[list, operator.add]
```

Common reducers:

- `operator.add` — Concatenate lists
- `add_messages` — Merge message lists (LangGraph built-in)
- Custom function — Any `(old, new) -> merged` logic

---

## Dynamic Fan-Out: The Send API

Static fan-out requires knowing branches at build time. But what if:

- User uploads 5 documents → process each in parallel
- Next user uploads 12 documents → process each in parallel

The number of parallel tasks is **unknown until runtime**. Use `Send`.

### Send Syntax

```python
from langgraph.types import Send

def dispatcher(state) -> list[Send]:
    """Return a list of Send objects to fan out dynamically."""
    tasks = state["pending_tasks"]
    
    return [
        Send("worker_node", {"task": task})  # (target_node, payload)
        for task in tasks
    ]
```

Each `Send` creates an **independent execution path** with its own state slice.

### Full Example: Dynamic Document Processing

```python
from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

class MainState(TypedDict):
    documents: list[str]
    processed_results: Annotated[list, operator.add]

class WorkerState(TypedDict):
    document: str  # Single document for this worker

def dispatcher(state: MainState) -> list[Send]:
    """Fan out: create one worker per document."""
    return [
        Send("process_document", {"document": doc})
        for doc in state["documents"]
    ]

def process_document(state: WorkerState) -> dict:
    """Process a single document."""
    doc = state["document"]
    result = f"Processed: {doc[:20]}..."  # Simulate processing
    return {"processed_results": [result]}

def aggregate(state: MainState) -> dict:
    """All results already merged via reducer."""
    return {"processed_results": state["processed_results"]}

# Build graph
builder = StateGraph(MainState)

builder.add_node("dispatch", dispatcher)
builder.add_node("process_document", process_document)
builder.add_node("aggregate", aggregate)

builder.add_edge(START, "dispatch")
# Note: No edge from dispatch to process_document needed — Send handles it
builder.add_edge("process_document", "aggregate")
builder.add_edge("aggregate", END)

graph = builder.compile()

# Run with variable number of documents
result = graph.invoke({
    "documents": ["Doc A content", "Doc B content", "Doc C content"],
    "processed_results": []
})
print(result["processed_results"])
# ['Processed: Doc A content...', 'Processed: Doc B content...', 'Processed: Doc C content...']
```

### Send Payload: Partial State

The second argument to `Send` is the **state passed to that worker**:

```python
Send("worker", {"task_id": 1, "data": "..."})
```

This becomes the worker node's input state. The worker's output is then **merged back** into the main state using reducers.

### Conditional Fan-Out with Send

Combine routing logic with dynamic parallelism:

```python
def smart_dispatcher(state) -> list[Send]:
    """Route different tasks to different workers."""
    sends = []
    
    for task in state["tasks"]:
        if task["type"] == "text":
            sends.append(Send("text_processor", {"task": task}))
        elif task["type"] == "image":
            sends.append(Send("image_processor", {"task": task}))
        else:
            sends.append(Send("generic_processor", {"task": task}))
    
    return sends
```

---

## Controlling Concurrency

### max_concurrency

Limit how many nodes run simultaneously:

```python
# Only 3 parallel workers at a time
result = graph.invoke(
    {"documents": many_documents},
    config={"max_concurrency": 3}
)
```

Use this when:

- External APIs have rate limits
- Memory/CPU is constrained
- You need predictable resource usage

### Deferred Execution

Wait for **all** parallel branches before continuing, even if some branches have more nodes:

```python
builder.add_node("final_step", final_handler, defer=True)
```

With `defer=True`, `final_step` won't execute until **all pending tasks** are complete, not just its immediate predecessors.

---

## Error Handling in Parallel Execution

### Atomic Supersteps

If **any** node in a superstep fails, the **entire superstep fails**:

```
Superstep: [arxiv ✓, wikipedia ✓, news ✗]
Result: Entire superstep fails, no state updates saved
```

This prevents inconsistent state but requires robust error handling.

### Checkpointing Saves Successful Nodes

With a checkpointer, successful nodes within a failed superstep are **saved internally**. When you retry, only failed branches re-execute:

```python
from langgraph.checkpoint.memory import MemorySaver

graph = builder.compile(checkpointer=MemorySaver())

# If news fails, arxiv and wikipedia results are saved
# On retry, only news re-runs
```

### Retry Policy

Configure automatic retries for flaky operations:

```python
from langgraph.types import RetryPolicy

builder.add_node(
    "flaky_api_call",
    call_flaky_api,
    retry=RetryPolicy(max_attempts=3, backoff_factor=2.0)
)
```

---

## Map-Reduce Pattern

Send enables classic map-reduce:

```python
class MapReduceState(TypedDict):
    items: list[str]                              # Input items
    mapped_results: Annotated[list, operator.add] # Intermediate
    final_result: str                             # Reduced output

def map_dispatcher(state) -> list[Send]:
    """Map: distribute items to workers."""
    return [Send("mapper", {"item": item}) for item in state["items"]]

def mapper(state) -> dict:
    """Process single item."""
    result = state["item"].upper()  # Example transformation
    return {"mapped_results": [result]}

def reducer(state) -> dict:
    """Reduce: combine all mapped results."""
    combined = " | ".join(state["mapped_results"])
    return {"final_result": combined}
```

---

## Static vs Dynamic: Decision Guide

|Scenario|Use|
|---|---|
|Fixed number of parallel branches|Static fan-out (multiple `add_edge`)|
|Branches known at build time|Static fan-out|
|Number of tasks varies at runtime|Dynamic fan-out (`Send`)|
|Different payloads per branch|Dynamic fan-out (`Send`)|
|Simple fan-out to same nodes|Either works; static is simpler|

---

## Key Takeaways

1. **Static fan-out** — Multiple `add_edge` from one node; branches fixed at build time
2. **Dynamic fan-out** — `Send` API; branches determined at runtime
3. **Reducers are mandatory** — Parallel nodes updating same key need merge logic
4. **Supersteps are atomic** — One failure fails the whole superstep
5. **Checkpointing helps** — Successful branches saved, only failures retry
6. **Control concurrency** — Use `max_concurrency` for rate limits and resource management

---

**Next:** Note 4 covers Subgraphs — encapsulating complex sub-workflows as reusable components.

_Sources: LangGraph docs (docs.langchain.com/oss/python/langgraph/use-graph-api), LangGraph Send API reference_