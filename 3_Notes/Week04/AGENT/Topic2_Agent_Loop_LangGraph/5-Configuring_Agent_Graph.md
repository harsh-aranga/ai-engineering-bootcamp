# Building and Configuring the Agent Loop Graph

## The Four Phases of Graph Construction

Building a LangGraph agent follows a predictable pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   1. DEFINE STATE                                           │
│      ↓                                                      │
│   2. BUILD GRAPH                                            │
│      • Create StateGraph                                    │
│      • Add nodes                                            │
│      • Add edges (regular + conditional)                    │
│      ↓                                                      │
│   3. COMPILE                                                │
│      • Add checkpointer (optional)                          │
│      • Add interrupt points (optional)                      │
│      • Set recursion limit (optional)                       │
│      ↓                                                      │
│   4. INVOKE                                                 │
│      • Pass initial state                                   │
│      • Pass config (thread_id, etc.)                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Define State

State is the shared data structure that flows through the graph. Every node reads from it and writes to it.

### Using MessagesState (Recommended for Agents)

```python
from langgraph.graph import MessagesState

# MessagesState is pre-built with:
# - messages: Annotated[list[AnyMessage], add_messages]
# Use it directly for most agent use cases
```

### Custom State

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Add custom fields as needed
    iteration_count: int
    user_id: str
```

### Extended MessagesState

```python
from langgraph.graph import MessagesState

class ExtendedState(MessagesState):
    """Extend MessagesState with additional fields."""
    tool_call_count: int
    last_tool_used: str
```

---

## Phase 2: Build the Graph

### Step 2a: Create StateGraph

```python
from langgraph.graph import StateGraph, MessagesState

# Option 1: Using prebuilt MessagesState
builder = StateGraph(MessagesState)

# Option 2: Using custom state
builder = StateGraph(AgentState)
```

### Step 2b: Add Nodes

Nodes are functions that receive state and return state updates.

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode

# Define LLM
llm = ChatOpenAI(model="gpt-4o-mini")
tools = [calculator, search]
llm_with_tools = llm.bind_tools(tools)

# Agent node
def agent_node(state: MessagesState):
    """Call the LLM."""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

# Add nodes to graph
builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
```

**Node naming rules:**

- Use descriptive, lowercase names
- Reserved names: `"__start__"`, `"__end__"` (use `START` and `END` constants instead)

### Step 2c: Add Edges

#### Regular Edges (Fixed Transitions)

```python
from langgraph.graph import START, END

# From START to agent
builder.add_edge(START, "agent")

# From tools back to agent
builder.add_edge("tools", "agent")
```

#### Conditional Edges (Dynamic Routing)

```python
from langgraph.prebuilt import tools_condition

# Route based on whether LLM wants to use tools
builder.add_conditional_edges(
    "agent",           # Source node
    tools_condition,   # Routing function
    # Optional: explicit mapping
    {
        "tools": "tools",  # If returns "tools" → go to "tools" node
        END: END,          # If returns END → terminate
    }
)
```

#### Set Entry Point (Alternative Syntax)

```python
# These are equivalent:
builder.add_edge(START, "agent")
builder.set_entry_point("agent")
```

#### Set Finish Point

```python
# Mark a node as terminal (goes to END after execution)
builder.set_finish_point("final_response")

# Equivalent to:
builder.add_edge("final_response", END)
```

---

## Phase 3: Compile

Compiling transforms the builder into an executable graph.

### Basic Compile

```python
graph = builder.compile()
```

### Compile with Checkpointer

A checkpointer enables persistence, memory, and human-in-the-loop.

```python
from langgraph.checkpoint.memory import MemorySaver

# In-memory checkpointer (for development)
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)
```

#### Checkpointer Options

|Checkpointer|Use Case|Persistence|
|---|---|---|
|`MemorySaver`|Development, testing|Lost on restart|
|`SqliteSaver`|Local apps, prototypes|Persists to file|
|`PostgresSaver`|Production|Persists to database|

```python
# SQLite (local persistence)
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
graph = builder.compile(checkpointer=checkpointer)

# PostgreSQL (production)
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string("postgresql://user:pass@localhost/db") as checkpointer:
    checkpointer.setup()  # Create tables (run once)
    graph = builder.compile(checkpointer=checkpointer)
```

### Compile with Interrupt Points

Interrupt points pause execution for human review.

```python
graph = builder.compile(
    checkpointer=checkpointer,  # Required for interrupts
    interrupt_before=["tools"],  # Pause BEFORE tools node
    # OR
    interrupt_after=["agent"],   # Pause AFTER agent node
)
```

**Note:** `interrupt_before` and `interrupt_after` require a checkpointer.

### Compile with Debug Mode

```python
graph = builder.compile(debug=True)
```

---

## Phase 4: Invoke

### Basic Invocation

```python
from langchain_core.messages import HumanMessage

result = graph.invoke({
    "messages": [HumanMessage(content="What's 15% of 230?")]
})

# Access final messages
for msg in result["messages"]:
    print(f"{msg.type}: {msg.content}")
```

### Invocation with Config

Config provides runtime settings like thread ID.

```python
config = {
    "configurable": {
        "thread_id": "user-123-session-1"
    }
}

result = graph.invoke(
    {"messages": [HumanMessage(content="Hello")]},
    config=config
)
```

**`thread_id` is required when using a checkpointer.** It identifies which conversation to continue.

### Invocation with Recursion Limit

```python
config = {
    "configurable": {"thread_id": "thread-1"},
    "recursion_limit": 50  # Default is 25
}

result = graph.invoke(input_state, config=config)
```

The recursion limit prevents infinite loops. Each "super-step" (node execution) counts as one recursion.

---

## Complete Example: Building a ReAct Agent

### OpenAI Version

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

# 1. Define tools
@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: 72°F, sunny"

tools = [calculator, get_weather]

# 2. Set up LLM
llm = ChatOpenAI(model="gpt-4o-mini")
llm_with_tools = llm.bind_tools(tools)

# 3. Define agent node
def agent_node(state: MessagesState):
    system = SystemMessage(content="You are a helpful assistant with access to tools.")
    messages = [system] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# 4. Build graph
builder = StateGraph(MessagesState)

builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

# 5. Compile with checkpointer
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# 6. Invoke
config = {"configurable": {"thread_id": "session-1"}}

result = graph.invoke(
    {"messages": [HumanMessage(content="What's 15% of 230?")]},
    config=config
)

print(result["messages"][-1].content)
```

### Anthropic Version

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

# 1. Define tools (same as above)
@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: 72°F, sunny"

tools = [calculator, get_weather]

# 2. Set up LLM (only this line changes)
llm = ChatAnthropic(model="claude-sonnet-4-20250514")
llm_with_tools = llm.bind_tools(tools)

# 3. Define agent node (identical)
def agent_node(state: MessagesState):
    system = SystemMessage(content="You are a helpful assistant with access to tools.")
    messages = [system] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# 4. Build graph (identical)
builder = StateGraph(MessagesState)

builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

# 5. Compile (identical)
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# 6. Invoke (identical)
config = {"configurable": {"thread_id": "session-1"}}

result = graph.invoke(
    {"messages": [HumanMessage(content="What's 15% of 230?")]},
    config=config
)
```

**The graph structure is identical** — only the LLM instantiation differs.

---

## Compile Options Reference

|Option|Type|Purpose|
|---|---|---|
|`checkpointer`|`BaseCheckpointSaver`|Enables persistence, memory, HITL|
|`interrupt_before`|`list[str]`|Pause before these nodes|
|`interrupt_after`|`list[str]`|Pause after these nodes|
|`debug`|`bool`|Enable debug logging|

## Config Options Reference

|Config Key|Where|Purpose|
|---|---|---|
|`thread_id`|`configurable`|Identifies conversation thread|
|`checkpoint_id`|`configurable`|Resume from specific checkpoint|
|`recursion_limit`|Top-level|Max iterations (default: 25)|

---

## Visualizing the Graph

```python
# Get Mermaid diagram as text
print(graph.get_graph().draw_mermaid())

# Render as PNG (requires additional dependencies)
from IPython.display import Image
Image(graph.get_graph().draw_mermaid_png())
```

Output:

```mermaid
graph TD
    __start__ --> agent
    agent -->|tool_calls| tools
    agent -->|no tool_calls| __end__
    tools --> agent
```

---

## Working with Checkpoints

### Continuing a Conversation

```python
config = {"configurable": {"thread_id": "session-1"}}

# First message
graph.invoke({"messages": [HumanMessage(content="My name is Harsh")]}, config)

# Continue same thread — agent remembers the name
graph.invoke({"messages": [HumanMessage(content="What's my name?")]}, config)
```

### Inspecting State

```python
# Get current state
state = graph.get_state(config)
print(state.values)  # Current state values
print(state.next)    # Next node(s) to execute

# Get state history
for snapshot in graph.get_state_history(config):
    print(snapshot.checkpoint_id, snapshot.values)
```

### Resuming After Interrupt

```python
# Graph compiled with interrupt_before=["tools"]
result = graph.invoke(
    {"messages": [HumanMessage(content="Calculate 15% of 230")]},
    config=config
)

# Graph pauses before tools — inspect what tools will be called
state = graph.get_state(config)
print(state.values["messages"][-1].tool_calls)

# Resume execution (pass None as input)
result = graph.invoke(None, config=config)
```

### Time Travel (Resume from Earlier State)

```python
# Get history
history = list(graph.get_state_history(config))

# Resume from a specific checkpoint
old_config = {
    "configurable": {
        "thread_id": "session-1",
        "checkpoint_id": history[2].checkpoint_id  # Go back 2 steps
    }
}

# Continue from that point
result = graph.invoke(
    {"messages": [HumanMessage(content="Let's try a different approach")]},
    old_config
)
```

---

## Common Patterns

### Pattern 1: Custom Routing Logic

```python
def custom_router(state: MessagesState) -> str:
    """Custom routing with iteration limit."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # Check iteration count
    if len(messages) > 20:
        return "summarize"  # Too many iterations
    
    # Check for tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return END

builder.add_conditional_edges(
    "agent",
    custom_router,
    {
        "tools": "tools",
        "summarize": "summarize",
        END: END
    }
)
```

### Pattern 2: Multiple Entry Points

```python
def route_input(state: MessagesState) -> str:
    """Route based on input type."""
    first_msg = state["messages"][0].content.lower()
    if "urgent" in first_msg:
        return "priority_agent"
    return "standard_agent"

builder.add_conditional_edges(
    START,
    route_input,
    {
        "priority_agent": "priority_agent",
        "standard_agent": "standard_agent"
    }
)
```

### Pattern 3: Adding Preprocessing

```python
def preprocess(state: MessagesState):
    """Add system context before agent."""
    # Add timestamp, user context, etc.
    return {"messages": state["messages"]}  # Or add metadata

builder.add_node("preprocess", preprocess)
builder.add_edge(START, "preprocess")
builder.add_edge("preprocess", "agent")
```

---

## Error Handling

### Graph Recursion Error

```python
# Error: "Recursion limit of 25 reached without hitting a stop condition"

# Solution: Increase limit
config = {"recursion_limit": 50, "configurable": {"thread_id": "1"}}

# Or fix the logic — ensure there's a path to END
```

### Missing Thread ID

```python
# Error when using checkpointer without thread_id

# Solution: Always include thread_id in config
config = {"configurable": {"thread_id": "unique-id"}}
```

### Interrupt Without Checkpointer

```python
# Error: interrupt_before/after without checkpointer

# Solution: Add checkpointer
graph = builder.compile(
    checkpointer=MemorySaver(),  # Required
    interrupt_before=["tools"]
)
```

---

## Quick Reference

### Minimal Agent Setup

```python
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

builder = StateGraph(MessagesState)
builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

graph = builder.compile()
```

### With Persistence

```python
from langgraph.checkpoint.memory import MemorySaver

graph = builder.compile(checkpointer=MemorySaver())

config = {"configurable": {"thread_id": "session-1"}}
result = graph.invoke(input_state, config)
```

### With Human-in-the-Loop

```python
graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["tools"]
)
```

---

## Key Takeaways

1. **Four phases:** Define state → Build graph → Compile → Invoke
    
2. **Compile transforms builder to executable** — always required before invoking
    
3. **Checkpointer enables:** persistence, memory across sessions, human-in-the-loop, time travel
    
4. **`thread_id` is required** when using a checkpointer
    
5. **`recursion_limit`** prevents infinite loops (default: 25)
    
6. **`interrupt_before`/`interrupt_after`** pause for human review (requires checkpointer)
    
7. **Graph structure is provider-agnostic** — swap LLMs without changing graph code
    

---

## References

- [LangGraph Graph API Overview](https://docs.langchain.com/oss/python/langgraph/graph-api) — Core concepts
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — Checkpointers and threads
- [LangGraph Interrupts](https://docs.langchain.com/oss/javascript/langgraph/interrupts) — Human-in-the-loop patterns
- [LangGraph Graphs Reference](https://www.baihezi.com/mirrors/langgraph/reference/graphs/index.html) — API reference
- [Checkpoints Reference](https://reference.langchain.com/python/langgraph/checkpoints) — Checkpointer implementations