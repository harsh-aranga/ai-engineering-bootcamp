# Note 4: Custom Multi-Agent Workflows (Without Libraries)

> **Week 6 Agent Track — Days 1-2**  
> **Focus:** Building custom multi-agent systems when `langgraph-supervisor` and `langgraph-swarm` aren't enough

---

## When Libraries Aren't Enough

The `langgraph-supervisor` and `langgraph-swarm` libraries handle common patterns well. But production systems often need:

- **Hybrid architectures:** Supervisor for some agents, peer handoffs for others
- **Custom routing logic:** Beyond "LLM decides" — business rules, user preferences, load balancing
- **Hierarchical teams:** Supervisors managing other supervisors (subgraph composition)
- **Network topologies:** Any agent can route to any other (AutoGen-style collaboration)
- **Fine-grained state control:** Different state schemas for different agents, transformation between them

For these cases, you build the graph yourself using LangGraph's core primitives.

---

## The Building Blocks

### StateGraph: The Foundation

Every LangGraph multi-agent system starts with a `StateGraph`:

```python
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# Define shared state
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: str  # Custom field for routing

# Create the graph
builder = StateGraph(AgentState)
```

### Nodes: Agent Functions

Each agent is a node — a function that receives state and returns updates:

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

llm = ChatOpenAI(model="gpt-4o")

# Define agent tools
def search_web(query: str) -> str:
    """Search the web."""
    return f"Results for: {query}"

def calculate(expression: str) -> str:
    """Calculate a math expression."""
    return str(eval(expression))

# Create agents
research_agent = create_react_agent(llm, tools=[search_web])
math_agent = create_react_agent(llm, tools=[calculate])

# Wrap as node functions
def research_node(state: AgentState) -> dict:
    result = research_agent.invoke(state)
    return {"messages": result["messages"]}

def math_node(state: AgentState) -> dict:
    result = math_agent.invoke(state)
    return {"messages": result["messages"]}

# Add nodes to graph
builder.add_node("researcher", research_node)
builder.add_node("mathematician", math_node)
```

### Edges: Control Flow

Edges define how agents connect. Two types:

**Normal Edges (Deterministic):**

```python
# Always go from START to router
builder.add_edge(START, "router")

# Always go from researcher back to router
builder.add_edge("researcher", "router")
```

**Conditional Edges (Dynamic):**

```python
def route_based_on_state(state: AgentState) -> str:
    """Decide next node based on state."""
    last_message = state["messages"][-1].content
    if "FINAL ANSWER" in last_message:
        return END
    elif "math" in last_message.lower():
        return "mathematician"
    else:
        return "researcher"

builder.add_conditional_edges(
    "router",  # Source node
    route_based_on_state,  # Routing function
    ["researcher", "mathematician", END]  # Possible destinations
)
```

---

## The `Command` Primitive: Combined Updates + Routing

`Command` is LangGraph's power tool for multi-agent systems. It lets a node **both** update state **and** decide where to go next — in a single return.

### Basic Command Usage

**Reference:** LangGraph Command documentation, LangChain blog (December 2024)

```python
from typing import Literal
from langgraph.types import Command
from langgraph.graph import MessagesState, END

def agent_node(state: MessagesState) -> Command[Literal["other_agent", END]]:
    # Do work...
    response = llm.invoke(state["messages"])
    
    # Decide where to go next
    if "DONE" in response.content:
        next_node = END
    else:
        next_node = "other_agent"
    
    # Return BOTH state update AND routing decision
    return Command(
        goto=next_node,                    # Control flow
        update={"messages": [response]}   # State update
    )
```

### Command Parameters

```python
Command(
    goto="node_name",           # Which node to execute next (or END)
    update={"key": "value"},    # State updates to apply
    graph=Command.PARENT,       # Optional: navigate in parent graph (for subgraphs)
)
```

### Why Command Matters

Without `Command`, you need separate:

1. Node function (updates state)
2. Conditional edge (decides routing)

```python
# WITHOUT Command — two separate pieces:

def my_node(state):
    return {"messages": [response]}  # State update only

def my_router(state):
    return "next_node"  # Routing only

builder.add_node("my_node", my_node)
builder.add_conditional_edges("my_node", my_router, [...])
```

With `Command`, it's unified:

```python
# WITH Command — unified in one place:

def my_node(state) -> Command[Literal["next_node", END]]:
    return Command(
        goto="next_node",
        update={"messages": [response]}
    )

builder.add_node("my_node", my_node)
# No conditional edge needed — routing is inside the node
```

This is cleaner and keeps routing logic co-located with the agent that makes the decision.

---

## Subgraphs and `Command.PARENT`

When agents are themselves subgraphs (graphs within graphs), `Command.PARENT` enables cross-graph navigation.

### The Scenario

```
Parent Graph
├── alice_subgraph (its own StateGraph)
│   ├── node_a
│   └── node_b  ← wants to hand off to bob_subgraph
└── bob_subgraph (its own StateGraph)
    ├── node_c
    └── node_d
```

A node inside `alice_subgraph` wants to hand off to `bob_subgraph`. But from inside Alice, Bob doesn't exist — he's a sibling in the parent graph.

### Solution: `Command.PARENT`

```python
def node_inside_alice(state) -> Command:
    # Do Alice's work...
    
    if should_hand_off_to_bob:
        return Command(
            goto="bob_subgraph",      # Bob is a node in the PARENT graph
            update={"messages": [...], "active_agent": "bob"},
            graph=Command.PARENT,     # Navigate in parent, not current graph
        )
    else:
        return Command(
            goto="next_node_in_alice",  # Stay in current subgraph
            update={"messages": [...]}
            # No graph= means stay in current graph
        )
```

### Building Hierarchical Teams

```python
from langgraph.graph import StateGraph, MessagesState, START, END

# --- Research Team (subgraph) ---
research_builder = StateGraph(MessagesState)
research_builder.add_node("search", search_node)
research_builder.add_node("scrape", scrape_node)
research_builder.add_edge(START, "search")
research_builder.add_edge("search", "scrape")
research_builder.add_edge("scrape", END)
research_team = research_builder.compile()

# --- Writing Team (subgraph) ---
writing_builder = StateGraph(MessagesState)
writing_builder.add_node("draft", draft_node)
writing_builder.add_node("edit", edit_node)
writing_builder.add_edge(START, "draft")
writing_builder.add_edge("draft", "edit")
writing_builder.add_edge("edit", END)
writing_team = writing_builder.compile()

# --- Top-Level Supervisor ---
def supervisor_node(state) -> Command[Literal["research_team", "writing_team", END]]:
    # LLM decides which team to invoke
    decision = llm.with_structured_output(Router).invoke(...)
    
    if decision["next"] == "FINISH":
        return Command(goto=END)
    
    return Command(
        goto=decision["next"],  # "research_team" or "writing_team"
        update={"next": decision["next"]}
    )

# --- Parent Graph ---
parent_builder = StateGraph(MessagesState)
parent_builder.add_node("supervisor", supervisor_node)
parent_builder.add_node("research_team", research_team)  # Subgraph as node
parent_builder.add_node("writing_team", writing_team)    # Subgraph as node

parent_builder.add_edge(START, "supervisor")
parent_builder.add_edge("research_team", "supervisor")  # Report back
parent_builder.add_edge("writing_team", "supervisor")   # Report back

app = parent_builder.compile()
```

---

## Pattern: Network Architecture (AutoGen Style)

In the network pattern, any agent can route to any other. There's no fixed hierarchy — agents collaborate freely.

**Inspired by:** AutoGen paper (Wu et al.) — "Enabling Next-Gen LLM Applications via Multi-Agent Conversation"

### Implementation

```python
from typing import Literal
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent

llm = ChatOpenAI(model="gpt-4o")

# Helper: Check if agent wants to finish
def get_next_node(last_message: BaseMessage, default_peer: str) -> str:
    if "FINAL ANSWER" in last_message.content:
        return END
    return default_peer

# Shared system prompt pattern
def make_system_prompt(specialty: str) -> str:
    return (
        "You are a helpful AI assistant, collaborating with other assistants. "
        f"Your specialty: {specialty}. "
        "Use your tools to progress toward answering the question. "
        "If you can't fully answer, that's OK — another assistant will help. "
        "When you have the final answer, prefix it with FINAL ANSWER."
    )

# Create specialized agents
research_agent = create_react_agent(
    llm, 
    tools=[web_search],
    prompt=make_system_prompt("research and information gathering")
)

chart_agent = create_react_agent(
    llm,
    tools=[create_chart],
    prompt=make_system_prompt("data visualization and charts")
)

# Network nodes — each can route to peers
def research_node(state: MessagesState) -> Command[Literal["chart_generator", END]]:
    result = research_agent.invoke(state)
    last_message = result["messages"][-1]
    
    # Tag the message with agent name
    last_message = HumanMessage(
        content=last_message.content,
        name="researcher"
    )
    
    goto = get_next_node(last_message, "chart_generator")
    
    return Command(
        update={"messages": result["messages"]},
        goto=goto
    )

def chart_node(state: MessagesState) -> Command[Literal["researcher", END]]:
    result = chart_agent.invoke(state)
    last_message = result["messages"][-1]
    
    last_message = HumanMessage(
        content=last_message.content,
        name="chart_generator"
    )
    
    goto = get_next_node(last_message, "researcher")
    
    return Command(
        update={"messages": result["messages"]},
        goto=goto
    )

# Build the network
workflow = StateGraph(MessagesState)
workflow.add_node("researcher", research_node)
workflow.add_node("chart_generator", chart_node)
workflow.add_edge(START, "researcher")  # Start with researcher

graph = workflow.compile()
```

### Key Properties of Network Pattern

1. **No supervisor:** Agents route to each other directly
2. **Peer collaboration:** Any agent can invoke any other
3. **Self-termination:** Agents signal completion with "FINAL ANSWER"
4. **Shared context:** All messages visible to all agents

---

## Pattern: Hybrid Supervisor + Peer Collaboration

Sometimes you want a supervisor for high-level routing but peer collaboration within a team.

### Architecture

```
                    ┌─────────────────┐
                    │   SUPERVISOR    │
                    │  (routes tasks) │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                                 ▼
     ┌─────────────────────────────┐   ┌─────────────┐
     │       RESEARCH TEAM         │   │    MATH     │
     │  ┌─────────┐  ┌─────────┐   │   │   AGENT     │
     │  │ Search  │◄►│ Analyze │   │   │ (standalone)│
     │  └─────────┘  └─────────┘   │   └─────────────┘
     │   (peer collaboration)       │
     └─────────────────────────────┘
```

### Implementation

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
from typing import Literal

# --- Research Team: Peer Collaboration Subgraph ---
def search_node(state) -> Command[Literal["analyzer", END]]:
    result = search_agent.invoke(state)
    # Decide: need analysis, or done?
    if needs_analysis(result):
        return Command(goto="analyzer", update={"messages": result["messages"]})
    else:
        return Command(goto=END, update={"messages": result["messages"]})

def analyze_node(state) -> Command[Literal["searcher", END]]:
    result = analyze_agent.invoke(state)
    # Decide: need more search, or done?
    if needs_more_search(result):
        return Command(goto="searcher", update={"messages": result["messages"]})
    else:
        return Command(goto=END, update={"messages": result["messages"]})

research_team_builder = StateGraph(MessagesState)
research_team_builder.add_node("searcher", search_node)
research_team_builder.add_node("analyzer", analyze_node)
research_team_builder.add_edge(START, "searcher")
research_team = research_team_builder.compile()

# --- Math Agent: Standalone ---
def math_node(state) -> dict:
    result = math_agent.invoke(state)
    return {"messages": result["messages"]}

# --- Supervisor ---
def supervisor_node(state) -> Command[Literal["research_team", "math_agent", END]]:
    decision = supervisor_llm.with_structured_output(Router).invoke(state["messages"])
    
    if decision["next"] == "FINISH":
        return Command(goto=END)
    
    return Command(goto=decision["next"])

# --- Parent Graph ---
parent = StateGraph(MessagesState)
parent.add_node("supervisor", supervisor_node)
parent.add_node("research_team", research_team)  # Peer collaboration subgraph
parent.add_node("math_agent", math_node)         # Standalone agent

parent.add_edge(START, "supervisor")
parent.add_edge("research_team", "supervisor")  # Report back
parent.add_edge("math_agent", "supervisor")     # Report back

app = parent.compile()
```

### When to Use Hybrid

- **Heterogeneous teams:** Some tasks need tight collaboration, others don't
- **Encapsulation:** Hide team complexity from supervisor
- **Different routing needs:** Supervisor routes between teams; teams self-organize internally

---

## Pattern: Explicit Workflow (Fixed Sequence)

Sometimes you don't want LLM routing — you want a fixed sequence.

### Implementation

```python
from langgraph.graph import StateGraph, MessagesState, START, END

# Fixed workflow: research → write → review → publish
workflow = StateGraph(MessagesState)

workflow.add_node("research", research_node)
workflow.add_node("write", write_node)
workflow.add_node("review", review_node)
workflow.add_node("publish", publish_node)

# Fixed edges — no LLM decisions
workflow.add_edge(START, "research")
workflow.add_edge("research", "write")
workflow.add_edge("write", "review")
workflow.add_edge("review", "publish")
workflow.add_edge("publish", END)

app = workflow.compile()
```

### Conditional Exit Points

You can have fixed sequence with conditional exits:

```python
def review_node(state) -> Command[Literal["publish", "write"]]:
    result = review_agent.invoke(state)
    
    # Quality gate
    if quality_score(result) >= 0.8:
        return Command(goto="publish", update={"messages": result["messages"]})
    else:
        return Command(
            goto="write",  # Send back for revision
            update={
                "messages": result["messages"],
                "revision_feedback": extract_feedback(result)
            }
        )
```

---

## State Transformation Between Agents

Different agents may need different state schemas. Use wrapper functions to transform state.

### The Problem

```python
# Research agent expects: {"messages": [...], "search_queries": [...]}
# Writing agent expects: {"messages": [...], "outline": {...}}
# Parent graph has: {"messages": [...], "task": "..."}
```

### The Solution: Wrapper Functions

```python
from langgraph_swarm import SwarmState

class ResearchState(TypedDict):
    research_messages: Annotated[list, add_messages]
    search_queries: list[str]

class WritingState(TypedDict):
    writing_messages: Annotated[list, add_messages]
    outline: dict

# Research agent with its own state
research_agent = StateGraph(ResearchState)
# ... build the agent ...
research_compiled = research_agent.compile()

# Wrapper: Parent state → Research state → Parent state
def call_research(state: SwarmState) -> dict:
    # Transform input
    research_input = {
        "research_messages": state["messages"],
        "search_queries": extract_queries(state["messages"][-1])
    }
    
    # Invoke agent
    result = research_compiled.invoke(research_input)
    
    # Transform output
    return {
        "messages": result["research_messages"],
        # Optionally add summary, not raw internal state
    }

# Add wrapper as node in parent graph
parent.add_node("research", call_research)
```

This pattern:

- Isolates agent internals from the parent graph
- Controls exactly what crosses boundaries
- Enables agents with incompatible schemas to work together

---

## Visualization

Custom graphs still support visualization:

```python
from IPython.display import Image, display

# Compile the graph
app = workflow.compile()

# Visualize
try:
    display(Image(app.get_graph().draw_mermaid_png()))
except Exception:
    # Requires graphviz and additional dependencies
    print("Install graphviz for visualization")
```

For `Command`-based routing to show correctly in visualization, use type hints:

```python
# Type hints tell LangGraph the possible destinations
def my_node(state) -> Command[Literal["node_a", "node_b", END]]:
    ...
```

Without type hints, the visualization won't show edges from this node.

---

## Common Custom Workflow Pitfalls

### 1. Missing Type Hints on Command

```python
# BAD: No type hints — visualization breaks, no compile-time checks
def my_node(state):
    return Command(goto="other_node", update={...})

# GOOD: Type hints specify possible destinations
def my_node(state) -> Command[Literal["other_node", "another_node", END]]:
    return Command(goto="other_node", update={...})
```

### 2. Forgetting `Command.PARENT` in Subgraphs

```python
# BAD: Tries to route to sibling subgraph without Command.PARENT
def node_in_alice(state):
    return Command(goto="bob")  # "bob" doesn't exist in Alice's graph!

# GOOD: Navigate to parent graph first
def node_in_alice(state):
    return Command(
        goto="bob",
        graph=Command.PARENT  # Now looks for "bob" in parent
    )
```

### 3. Inconsistent State Schemas

```python
# BAD: Subgraph returns state keys parent doesn't expect
def subgraph_node(state):
    return {"internal_key": value}  # Parent doesn't have "internal_key"!

# GOOD: Return only keys in shared schema
def subgraph_node(state):
    return {"messages": [...]}  # "messages" exists in parent schema
```

### 4. Infinite Loops Without Exit Conditions

```python
# BAD: Can loop forever between A and B
def node_a(state) -> Command[Literal["node_b"]]:
    return Command(goto="node_b", update={...})

def node_b(state) -> Command[Literal["node_a"]]:
    return Command(goto="node_a", update={...})

# GOOD: Always have an exit condition
def node_a(state) -> Command[Literal["node_b", END]]:
    if done_condition(state):
        return Command(goto=END, update={...})
    return Command(goto="node_b", update={...})
```

---

## When to Use Custom vs. Libraries

### Use Libraries (`langgraph-supervisor`, `langgraph-swarm`) When:

- Your pattern matches supervisor or swarm exactly
- You want quick setup with sensible defaults
- You don't need custom routing logic
- You're learning the patterns

### Build Custom When:

- You need hybrid architectures (supervisor + peer)
- Routing requires business logic beyond LLM decisions
- You have hierarchical teams (supervisors of supervisors)
- Agents need different state schemas
- You want full control over message history management
- You need custom visualization or debugging hooks

---

## Key Takeaways

1. **`StateGraph` is the foundation:** Nodes are agent functions, edges define flow.
    
2. **`Command` unifies routing + state:** Return `Command(goto=..., update={...})` to do both in one place.
    
3. **`Command.PARENT` enables hierarchies:** Subgraphs can route to siblings in the parent graph.
    
4. **Type hints matter:** `Command[Literal["a", "b", END]]` enables visualization and validation.
    
5. **Wrappers transform state:** Use wrapper functions when agents have different schemas.
    
6. **Patterns compose:** You can mix supervisor, peer, and fixed-sequence patterns in one system.
    
7. **The library patterns are just starting points:** Production systems often need customization.
    

---

## What's Next

- **Note 5:** Handoffs Deep Dive — state update mechanics, message passing strategies, custom handoff implementations

---

## References

**Documentation referenced for this note:**

- LangChain Blog: "Command: A new tool for multi-agent architectures" (December 2024)
- LangGraph Tutorials: Multi-agent network, Hierarchical agent teams
- LangGraph How-tos: Combine control flow and state updates with Command
- LangChain OpenTutorial: Multi-Agent Structures

**Key API elements:**

- `StateGraph` — graph builder
- `Command` — combined state update + routing
- `Command.PARENT` — navigate in parent graph from subgraph
- `add_edge()` — fixed edges
- `add_conditional_edges()` — dynamic routing (alternative to Command)
- `create_react_agent()` — prebuilt ReAct agent