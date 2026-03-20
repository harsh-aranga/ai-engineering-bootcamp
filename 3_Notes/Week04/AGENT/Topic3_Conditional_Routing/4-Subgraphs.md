# Subgraphs: Encapsulating Complex Sub-Workflows

## What is a Subgraph?

A **subgraph** is a compiled graph used as a node inside another graph. The inner graph has its own nodes, edges, and potentially its own state schema — but from the parent's perspective, it's just another node.

```
Parent Graph
┌─────────────────────────────────────────┐
│  [start] → [node_a] → [subgraph] → [end]│
│                           │             │
│                    ┌──────┴──────┐      │
│                    │ Inner Graph │      │
│                    │ [s1]→[s2]→[s3]│    │
│                    └─────────────┘      │
└─────────────────────────────────────────┘
```

## Why Use Subgraphs?

|Benefit|Description|
|---|---|
|**Modularity**|Break complex graphs into manageable pieces|
|**Reusability**|Use the same subgraph in multiple parent graphs|
|**Encapsulation**|Hide internal complexity; parent only sees input/output|
|**Team separation**|Different teams work on different subgraphs independently|
|**State isolation**|Subgraph can have private state keys invisible to parent|

## Two Integration Scenarios

### Scenario 1: Shared State Schema

Parent and subgraph share at least some state keys. The subgraph can be added **directly as a node**.

```python
from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, START, END

# Shared state key: both graphs use "messages"
class SharedState(TypedDict):
    messages: Annotated[list, operator.add]
    context: str

# ─── Build Subgraph ───
def subgraph_node_1(state: SharedState) -> dict:
    return {"messages": ["Subgraph step 1"]}

def subgraph_node_2(state: SharedState) -> dict:
    return {"messages": ["Subgraph step 2"]}

subgraph_builder = StateGraph(SharedState)
subgraph_builder.add_node("sub_step_1", subgraph_node_1)
subgraph_builder.add_node("sub_step_2", subgraph_node_2)
subgraph_builder.add_edge(START, "sub_step_1")
subgraph_builder.add_edge("sub_step_1", "sub_step_2")
subgraph_builder.add_edge("sub_step_2", END)

subgraph = subgraph_builder.compile()

# ─── Build Parent Graph ───
def parent_node(state: SharedState) -> dict:
    return {"messages": ["Parent processing"], "context": "initialized"}

parent_builder = StateGraph(SharedState)
parent_builder.add_node("parent_step", parent_node)
parent_builder.add_node("agent_subgraph", subgraph)  # Subgraph as node

parent_builder.add_edge(START, "parent_step")
parent_builder.add_edge("parent_step", "agent_subgraph")
parent_builder.add_edge("agent_subgraph", END)

parent_graph = parent_builder.compile()

# Run
result = parent_graph.invoke({"messages": [], "context": ""})
print(result["messages"])
# ['Parent processing', 'Subgraph step 1', 'Subgraph step 2']
```

**Key point:** State flows directly — parent passes state to subgraph, subgraph updates merge back automatically.

### Scenario 2: Different State Schemas

Parent and subgraph have **no shared keys**. You must wrap the subgraph in a node function that **transforms state at boundaries**.

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

# ─── Subgraph with DIFFERENT schema ───
class AnalysisState(TypedDict):
    input_text: str      # Subgraph-only key
    findings: list       # Subgraph-only key
    score: float         # Subgraph-only key

def analyze(state: AnalysisState) -> dict:
    text = state["input_text"]
    return {"findings": [f"Found {len(text)} characters"]}

def score_analysis(state: AnalysisState) -> dict:
    return {"score": len(state["findings"]) * 0.1}

analysis_builder = StateGraph(AnalysisState)
analysis_builder.add_node("analyze", analyze)
analysis_builder.add_node("score", score_analysis)
analysis_builder.add_edge(START, "analyze")
analysis_builder.add_edge("analyze", "score")
analysis_builder.add_edge("score", END)

analysis_subgraph = analysis_builder.compile()

# ─── Parent with DIFFERENT schema ───
class ParentState(TypedDict):
    query: str
    analysis_result: dict

def call_analysis_subgraph(state: ParentState) -> dict:
    """Wrapper node: transforms state at boundaries."""
    
    # Transform parent state → subgraph state
    subgraph_input = {
        "input_text": state["query"],
        "findings": [],
        "score": 0.0
    }
    
    # Invoke subgraph
    subgraph_output = analysis_subgraph.invoke(subgraph_input)
    
    # Transform subgraph output → parent state
    return {
        "analysis_result": {
            "findings": subgraph_output["findings"],
            "score": subgraph_output["score"]
        }
    }

parent_builder = StateGraph(ParentState)
parent_builder.add_node("run_analysis", call_analysis_subgraph)
parent_builder.add_edge(START, "run_analysis")
parent_builder.add_edge("run_analysis", END)

parent_graph = parent_builder.compile()

# Run
result = parent_graph.invoke({"query": "Analyze this document", "analysis_result": {}})
print(result["analysis_result"])
# {'findings': ['Found 21 characters'], 'score': 0.1}
```

**Key point:** The wrapper function handles state mapping in both directions.

## State Isolation: Private Subgraph Keys

Even with shared schemas, subgraph can have **private keys** that don't leak to parent:

```python
class SubgraphState(TypedDict):
    messages: list       # Shared with parent
    internal_buffer: str # Private to subgraph

class ParentState(TypedDict):
    messages: list       # Shared
    # No internal_buffer — parent never sees it
```

When subgraph completes, only **overlapping keys** surface to parent. Private keys stay internal.

## Checkpointing and Subgraphs

### Parent Checkpointer Required

For subgraph persistence features to work (interrupts, state inspection, memory), the **parent graph must have a checkpointer**:

```python
from langgraph.checkpoint.memory import MemorySaver

# Subgraph inherits parent's checkpointer
parent_graph = parent_builder.compile(checkpointer=MemorySaver())
```

### Subgraph with checkpointer=True

For subgraphs that need their own checkpointing (common in multi-agent systems):

```python
# Subgraph with its own checkpointing
agent_subgraph = agent_builder.compile(checkpointer=True)

# Add to parent
parent_builder.add_node("agent", agent_subgraph)
```

This enables:

- Interrupts within the subgraph
- State inspection at subgraph level
- Durable execution across subgraph invocations

## Streaming from Subgraphs

To see streaming output from inside subgraphs, use `subgraphs=True`:

```python
# Without subgraphs=True: only see parent-level updates
for chunk in parent_graph.stream({"messages": []}, stream_mode="updates"):
    print(chunk)
# {'parent_step': {...}}
# {'agent_subgraph': {...}}  ← Just the final output

# With subgraphs=True: see inside subgraph execution
for namespace, chunk in parent_graph.stream(
    {"messages": []}, 
    stream_mode="updates",
    subgraphs=True
):
    depth = len(namespace)
    prefix = "  " * depth
    print(f"{prefix}[{'/'.join(namespace) or 'root'}] {chunk}")
# [root] {'parent_step': {...}}
# [agent_subgraph] {'sub_step_1': {...}}
# [agent_subgraph] {'sub_step_2': {...}}
```

## Navigating Between Subgraphs with Command

A subgraph can route to a **sibling subgraph** (another node in the parent) using `Command` with `graph=Command.PARENT`:

```python
from langgraph.types import Command

def subgraph_node(state) -> Command:
    if state["needs_handoff"]:
        # Navigate to a different subgraph in the parent
        return Command(
            update={"handoff_reason": "Need specialist"},
            goto="specialist_subgraph",
            graph=Command.PARENT  # Escape to parent level
        )
    return Command(goto=END)
```

This enables **multi-agent handoffs** where Agent A can hand off to Agent B through the parent orchestrator.

## Visualizing Subgraphs

Use `xray` parameter to see inside subgraphs:

```python
from IPython.display import Image, display

# xray=0: Subgraphs shown as single nodes
display(Image(parent_graph.get_graph(xray=0).draw_mermaid_png()))

# xray=1: Expand one level of subgraphs
display(Image(parent_graph.get_graph(xray=1).draw_mermaid_png()))

# xray=2: Expand two levels (nested subgraphs)
display(Image(parent_graph.get_graph(xray=2).draw_mermaid_png()))
```

## When to Use Subgraphs vs When to Skip

### Use Subgraphs When:

- **Reusability**: Same workflow used in multiple contexts
- **Team boundaries**: Different teams own different parts
- **State isolation**: Need private state invisible to parent
- **Complexity management**: Parent graph getting unwieldy
- **Multi-agent systems**: Each agent is a subgraph with own logic

### Skip Subgraphs When:

- **Simple linear flow**: Just a few nodes, no reuse needed
- **Tight coupling**: All nodes need access to all state
- **Early development**: Premature abstraction adds complexity
- **Single-use workflow**: No reuse benefit

## Common Pitfall: Reducer Conflicts

If parent and subgraph both have reducers on the same key, updates can get applied **twice**:

```python
# Both define reducer for "path"
class ParentState(TypedDict):
    path: Annotated[list, operator.add]

class SubgraphState(TypedDict):
    path: Annotated[list, operator.add]

# Subgraph returns {"path": ["step1"]}
# Reducer applies in subgraph: path = [..., "step1"]
# Parent receives update, reducer applies again: path = [..., "step1", "step1"]
```

**Solutions:**

1. Use unique IDs in list items to deduplicate
2. Use different key names
3. Wrap subgraph in function that controls what surfaces to parent

## Full Example: Multi-Agent with Subgraphs

```python
from typing import TypedDict, Annotated, Literal
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

# Shared state for all agents
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    current_agent: str

# ─── Research Agent Subgraph ───
def research_search(state: AgentState) -> dict:
    return {"messages": ["[Research] Searching..."]}

def research_summarize(state: AgentState) -> dict:
    return {"messages": ["[Research] Summary complete"]}

research_builder = StateGraph(AgentState)
research_builder.add_node("search", research_search)
research_builder.add_node("summarize", research_summarize)
research_builder.add_edge(START, "search")
research_builder.add_edge("search", "summarize")
research_builder.add_edge("summarize", END)
research_agent = research_builder.compile()

# ─── Writer Agent Subgraph ───
def writer_draft(state: AgentState) -> dict:
    return {"messages": ["[Writer] Drafting..."]}

def writer_polish(state: AgentState) -> dict:
    return {"messages": ["[Writer] Polishing..."]}

writer_builder = StateGraph(AgentState)
writer_builder.add_node("draft", writer_draft)
writer_builder.add_node("polish", writer_polish)
writer_builder.add_edge(START, "draft")
writer_builder.add_edge("draft", "polish")
writer_builder.add_edge("polish", END)
writer_agent = writer_builder.compile()

# ─── Orchestrator (Parent) ───
def route_to_agent(state: AgentState) -> str:
    # Simple routing logic
    last_message = state["messages"][-1] if state["messages"] else ""
    if "research" in last_message.lower():
        return "research_agent"
    elif "write" in last_message.lower():
        return "writer_agent"
    return "research_agent"  # Default

orchestrator = StateGraph(AgentState)
orchestrator.add_node("research_agent", research_agent)
orchestrator.add_node("writer_agent", writer_agent)

orchestrator.add_conditional_edges(START, route_to_agent, {
    "research_agent": "research_agent",
    "writer_agent": "writer_agent"
})
orchestrator.add_edge("research_agent", "writer_agent")
orchestrator.add_edge("writer_agent", END)

app = orchestrator.compile()

# Run
result = app.invoke({
    "messages": ["Please research and write about AI"],
    "current_agent": ""
})
print(result["messages"])
```

## Key Takeaways

1. **Subgraph = compiled graph as a node** — Encapsulates complex workflows
2. **Shared schema → add directly** — No transformation needed
3. **Different schema → wrapper function** — Transform state at boundaries
4. **Private keys stay private** — Only overlapping keys surface to parent
5. **Parent checkpointer required** — For persistence features to work
6. **`subgraphs=True` for streaming** — See inside subgraph execution
7. **`Command.PARENT` for handoffs** — Navigate between sibling subgraphs

---

**Next:** Note 5 covers Human-in-the-Loop with `interrupt()` and resumption patterns.

_Sources: LangGraph docs (docs.langchain.com/oss/python/langgraph/use-subgraphs), LangGraph subgraph how-to guides_