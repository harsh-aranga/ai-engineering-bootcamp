# ReAct Pattern and How LangGraph Implements It

## Quick Recap: The ReAct Pattern

You already know ReAct (Reasoning + Acting) — the iterative loop where an LLM:

1. **Thinks** — Reasons about what to do next
2. **Acts** — Calls a tool
3. **Observes** — Sees the result
4. Repeats until done

The original ReAct used explicit "Thought/Action/Observation" prompting. Modern implementations use **function calling** to implement the same loop — the LLM emits structured tool calls instead of free-form "Action:" text.

---

## From Raw Loop to Graph: The Translation

In Week 3, you built the raw agent loop:

```python
# Your raw Week 3 loop (pseudocode)
while True:
    response = llm.invoke(messages)
    if not response.tool_calls:
        break  # Done
    results = execute_tools(response.tool_calls)
    messages.append(response)
    messages.extend(results)
```

LangGraph expresses **the same logic** as a graph:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│    START                                                    │
│      │                                                      │
│      ▼                                                      │
│  ┌───────────┐     tool_calls?      ┌───────────┐          │
│  │   Agent   │────────YES──────────▶│   Tools   │          │
│  │   Node    │                      │   Node    │          │
│  └───────────┘                      └───────────┘          │
│      │                                    │                 │
│      │ NO                                 │                 │
│      ▼                                    │                 │
│     END ◀─────────────────────────────────┘                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**The translation:**

|Raw Code|LangGraph|
|---|---|
|`llm.invoke(messages)`|Agent node|
|`execute_tools(...)`|Tools node|
|`if not tool_calls: break`|Conditional edge to END|
|`while True` loop|Edge from Tools → Agent|

---

## LangGraph's Core Abstraction: Graph as Control Flow

LangGraph models workflows as **directed graphs**:

- **Nodes**: Functions that do work (call LLM, execute tools, process data)
- **Edges**: Paths between nodes (unconditional or conditional)
- **State**: Data that flows through the graph, updated by each node

The key insight: **Your control flow becomes visible and debuggable.**

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition

# Define the graph
builder = StateGraph(MessagesState)

# Add nodes
builder.add_node("agent", call_llm)          # The "think" step
builder.add_node("tools", ToolNode(tools))   # The "act" step

# Add edges
builder.add_edge(START, "agent")             # Entry point
builder.add_conditional_edges(
    "agent",
    tools_condition,                          # Routes based on tool_calls
)
builder.add_edge("tools", "agent")           # Loop back

graph = builder.compile()
```

**Referenced doc:** [LangGraph Graph API Overview](https://docs.langchain.com/oss/python/langgraph/graph-api)

---

## The Three-Step Loop in LangGraph

### Step 1: Agent Node (Reasoning)

The agent node calls the LLM with the current conversation state:

```python
def call_llm(state: MessagesState):
    """Agent node: LLM decides what to do next."""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}
```

The LLM either:

- Returns a response with `tool_calls` → Continue to tools node
- Returns a response without `tool_calls` → End the loop

### Step 2: Conditional Edge (Routing)

LangGraph provides `tools_condition` — a prebuilt function that checks the last message:

```python
from langgraph.prebuilt import tools_condition

# tools_condition returns:
# - "tools" if the last message has tool_calls
# - END if no tool_calls
```

Under the hood, it's doing exactly what your `if not response.tool_calls: break` did.

### Step 3: Tools Node (Acting + Observing)

`ToolNode` executes all requested tools and returns results as `ToolMessage` objects:

```python
from langgraph.prebuilt import ToolNode

tool_node = ToolNode([search, calculator, save_note])

# When invoked with a message containing tool_calls:
# 1. Extracts tool_calls from the last AIMessage
# 2. Executes each tool (in parallel by default)
# 3. Returns ToolMessage objects to append to state
```

### Step 4: Loop Back

The edge `tools → agent` sends the tool results back to the LLM for the next reasoning step. The loop continues until `tools_condition` routes to END.

---

## Why Graph > Raw Loop?

Your Week 3 raw loop works. Why bother with LangGraph?

### 1. **Visibility**

```python
# Visualize the graph
graph.get_graph().draw_mermaid()
```

You can literally see your control flow. Debugging a graph is easier than debugging a while loop with nested conditionals.

### 2. **Persistence (Checkpointing)**

LangGraph can save state between iterations:

```python
from langgraph.checkpoint.memory import MemorySaver

graph = builder.compile(checkpointer=MemorySaver())

# Now you can:
# - Resume from any point
# - Time-travel debug
# - Handle interrupts gracefully
```

Your raw loop loses everything if it crashes mid-execution.

### 3. **Human-in-the-Loop**

Add breakpoints before tool execution:

```python
graph = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["tools"]  # Pause before executing tools
)
```

With a raw loop, you'd have to build this yourself.

### 4. **Extensibility**

Adding a new step (like validation, logging, or reflection) means adding a node:

```python
builder.add_node("validate", validate_response)
builder.add_edge("agent", "validate")
builder.add_conditional_edges("validate", ...)
```

In raw code, you're nesting more conditionals into your while loop.

### 5. **Streaming**

LangGraph provides streaming of intermediate steps out of the box:

```python
for event in graph.stream({"messages": [HumanMessage(content="...")]}):
    print(event)
```

---

## Execution Model: Super-Steps (Pregel)

LangGraph is inspired by Google's **Pregel** system. Execution happens in discrete "super-steps":

1. All active nodes execute (potentially in parallel)
2. They send messages (state updates) to downstream nodes
3. Downstream nodes become active
4. Repeat until no more messages

For a ReAct agent:

- **Super-step 1**: Agent node runs → outputs AIMessage (with or without tool_calls)
- **Super-step 2**: If tool_calls exist, Tools node runs → outputs ToolMessages
- **Super-step 3**: Agent node runs again → ...
- **Final**: Agent outputs without tool_calls → END

This model allows parallel tool execution by default — if the LLM requests 3 tools, `ToolNode` runs them concurrently.

---

## Minimal Complete Example

### OpenAI Version

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition

# Define tools
@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

@tool
def get_time() -> str:
    """Get the current time."""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")

tools = [calculator, get_time]

# LLM with tools bound
llm = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)

# Agent node
def call_llm(state: MessagesState):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# Build the graph
builder = StateGraph(MessagesState)
builder.add_node("agent", call_llm)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

graph = builder.compile()

# Run it
result = graph.invoke({
    "messages": [HumanMessage(content="What's 15% of 230? Also, what time is it?")]
})

for msg in result["messages"]:
    print(f"{msg.type}: {msg.content}")
```

### Anthropic Version

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition

# Define tools (same as above)
@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

@tool
def get_time() -> str:
    """Get the current time."""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")

tools = [calculator, get_time]

# Anthropic LLM with tools bound
llm = ChatAnthropic(model="claude-sonnet-4-20250514").bind_tools(tools)

# Agent node
def call_llm(state: MessagesState):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

# Build the graph (identical structure)
builder = StateGraph(MessagesState)
builder.add_node("agent", call_llm)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

graph = builder.compile()

# Run it
result = graph.invoke({
    "messages": [HumanMessage(content="What's 15% of 230? Also, what time is it?")]
})
```

**Key point:** The graph structure is identical for both providers. Only the LLM instantiation differs.

---

## What LangGraph Gives You "For Free"

|Feature|Raw Loop|LangGraph|
|---|---|---|
|Basic agent loop|You build it|✅ Built-in pattern|
|Parallel tool execution|You build it|✅ `ToolNode` default|
|State management|You track manually|✅ `MessagesState` + reducers|
|Checkpointing|You build it|✅ `MemorySaver` etc.|
|Visualization|Not possible|✅ `graph.get_graph().draw_mermaid()`|
|Streaming|You build it|✅ `graph.stream()`|
|Human-in-the-loop|You build it|✅ `interrupt_before`|
|Error handling|Try/except everywhere|✅ `handle_tool_errors`|

---

## Key Takeaways

1. **Same logic, different representation**: LangGraph's ReAct agent does exactly what your Week 3 loop did — it just expresses control flow as a graph instead of while/if.
    
2. **Graph = debuggable control flow**: You can visualize, checkpoint, and interrupt at any node. A while loop gives you none of this.
    
3. **Three core components**: Agent node (LLM), Tools node (`ToolNode`), conditional edge (`tools_condition`).
    
4. **Provider-agnostic**: The graph structure doesn't change between OpenAI and Anthropic — only the LLM binding does.
    
5. **Pregel model**: Execution happens in super-steps. Parallel tool calls are automatic.
    

---

## References

- [LangGraph Graph API Overview](https://docs.langchain.com/oss/python/langgraph/graph-api) — Official docs on StateGraph, MessagesState
- [LangGraph ReAct Agent Tutorial](https://ai.google.dev/gemini-api/docs/langgraph-example) — Step-by-step walkthrough
- [LangGraph Prebuilt Components](https://www.baihezi.com/mirrors/langgraph/reference/prebuilt/index.html) — ToolNode, tools_condition reference
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph) — Source and examples