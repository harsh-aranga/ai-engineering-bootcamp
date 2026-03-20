# LangGraph: Why Graphs, Mental Model, and When to Use

## The Problem with Raw Agent Loops

In Week 3, you built agents with raw code — a `while` loop that called the LLM, parsed tool calls, executed tools, and fed results back. It worked. But it had problems:

```python
# Week 3 approach (pseudocode)
while not done:
    response = llm.call(messages)
    if response.has_tool_calls:
        for tool_call in response.tool_calls:
            result = execute_tool(tool_call)
            messages.append(result)
    else:
        done = True
```

**What breaks as complexity grows:**

|Problem|What Happens|
|---|---|
|Adding tools|Every new tool requires touching the loop logic|
|Branching|`if/elif/else` chains become unreadable|
|State tracking|Ad-hoc variables scattered everywhere|
|Debugging|"What happened at step 7?" — good luck|
|Human-in-the-loop|Where do you pause? How do you resume?|
|Retries/failures|Manual exception handling, no checkpointing|
|Multi-agent|Spaghetti coordination between loops|

The raw loop doesn't scale. You need structure.

---

## Why Graphs?

LangGraph models agent workflows as **directed graphs**. This isn't arbitrary — graphs are the natural representation for complex, stateful flows.

### What a Graph Gives You

```
┌─────────────────────────────────────────────────────────────┐
│                       GRAPH STRUCTURE                        │
│                                                              │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐             │
│   │  START  │─────▶│ Node A  │─────▶│ Node B  │             │
│   └─────────┘      └─────────┘      └────┬────┘             │
│                                          │                   │
│                         ┌────────────────┼────────────────┐  │
│                         ▼                ▼                ▼  │
│                    ┌─────────┐      ┌─────────┐     ┌─────┐ │
│                    │ Node C  │      │ Node D  │     │ END │ │
│                    └─────────┘      └─────────┘     └─────┘ │
│                                                              │
│   Nodes = Actions (functions, LLM calls, tool execution)    │
│   Edges = Transitions (what happens next)                   │
│   State = Shared data flowing through the graph             │
└─────────────────────────────────────────────────────────────┘
```

**Graphs naturally express:**

- **Branching**: Conditional edges route to different nodes
- **Loops/Cycles**: Node A → Node B → Node A (until condition met)
- **Parallelism**: Multiple nodes can execute concurrently
- **Composition**: Subgraphs can be nested inside nodes

### The Mental Model

Think of a graph as a **state machine** for your agent:

1. **State** = The shared blackboard that all nodes read from and write to
2. **Nodes** = Individual processing steps (functions that transform state)
3. **Edges** = Rules for which node runs next
4. **Execution** = State flows through nodes, getting modified at each step

```
State enters → Node processes → State exits (modified) → Next node
```

This is fundamentally different from a while loop. Instead of one monolithic function managing everything, you have:

- **Separation of concerns**: Each node does one thing
- **Explicit flow**: You can _see_ the structure
- **Declarative structure**: Define _what_ connects to _what_, not _how_ to manage it

---

## LangGraph's Core Abstractions

LangGraph provides these primitives:

|Concept|What It Is|Analogy|
|---|---|---|
|`StateGraph`|The graph definition|The blueprint|
|`State`|TypedDict flowing through nodes|The shared blackboard|
|`Node`|A function that receives state, returns updates|A processing step|
|`Edge`|Connection between nodes|The wiring|
|`Conditional Edge`|Edge that branches based on state|The router|
|`START` / `END`|Special nodes marking entry/exit|The boundaries|
|`compile()`|Turns definition into runnable graph|Build step|

### Minimal Example

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

# 1. Define your state schema
class State(TypedDict):
    message: str
    steps: list[str]

# 2. Define nodes (functions that take state, return updates)
def step_one(state: State) -> dict:
    return {
        "message": state["message"] + " -> processed by step_one",
        "steps": state["steps"] + ["step_one"]
    }

def step_two(state: State) -> dict:
    return {
        "message": state["message"] + " -> processed by step_two",
        "steps": state["steps"] + ["step_two"]
    }

# 3. Build the graph
graph = StateGraph(State)
graph.add_node("step_one", step_one)
graph.add_node("step_two", step_two)

# 4. Connect nodes with edges
graph.add_edge(START, "step_one")
graph.add_edge("step_one", "step_two")
graph.add_edge("step_two", END)

# 5. Compile and run
app = graph.compile()
result = app.invoke({"message": "hello", "steps": []})

print(result)
# {'message': 'hello -> processed by step_one -> processed by step_two', 
#  'steps': ['step_one', 'step_two']}
```

**What just happened:**

1. State `{"message": "hello", "steps": []}` entered at START
2. Flowed to `step_one`, which modified it
3. Flowed to `step_two`, which modified it further
4. Exited at END with final state

---

## What LangGraph Provides (Beyond Structure)

LangGraph isn't just a graph abstraction. It solves production problems:

### 1. Durable Execution (Checkpointing)

State is automatically saved after each node. If your agent fails at step 5, you can resume from step 5 — not restart from scratch.

```python
from langgraph.checkpoint.memory import MemorySaver

# Add checkpointing
app = graph.compile(checkpointer=MemorySaver())

# Run with a thread ID
config = {"configurable": {"thread_id": "conversation-123"}}
result = app.invoke(initial_state, config)

# Later: resume from where you left off
result = app.invoke(new_input, config)  # Continues, doesn't restart
```

### 2. Human-in-the-Loop

Pause execution, wait for human approval, resume.

```python
# Interrupt before a specific node
app = graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["sensitive_action"]
)

# Graph pauses at "sensitive_action"
# Human reviews, modifies state if needed
# Graph resumes with Command(resume=...)
```

### 3. Streaming

Token-by-token streaming, step-by-step updates, custom event streams.

```python
for event in app.stream(initial_state):
    print(event)  # See each node's output as it happens
```

### 4. Observability (LangSmith Integration)

Trace every step, every input/output, every token. Debug exactly what went wrong.

### 5. Memory

- **Short-term**: Conversation history within a thread
- **Long-term**: Cross-session persistence

---

## When to Use LangGraph vs. Raw Code

This is the critical decision. Not every agent needs a framework.

### Use Raw Code When:

|Scenario|Why Raw Works|
|---|---|
|Simple tool-calling loop|One while loop, 2-3 tools, no branching|
|Prototype / proof-of-concept|Speed matters more than structure|
|Single LLM call + 1-2 tools|Framework overhead exceeds value|
|Learning fundamentals|Understand what frameworks abstract away|

**Rule of thumb**: If your agent fits in <100 lines and has no branching, raw code is fine.

### Use LangGraph When:

|Scenario|Why LangGraph Wins|
|---|---|
|Complex branching|Conditional edges are cleaner than nested if/else|
|Cycles/loops|Agent retries, reflects, iterates until done|
|Human-in-the-loop|Built-in interrupt/resume patterns|
|Long-running agents|Checkpointing prevents lost work|
|Multi-agent systems|Graph structure makes coordination explicit|
|Production deployment|Streaming, observability, fault tolerance|
|Team collaboration|Visualizable graphs are easier to discuss|

**Rule of thumb**: If you're adding your third `if` statement to the loop, or if you need any persistence/human-in-loop, switch to LangGraph.

### The Complexity Threshold

```
┌─────────────────────────────────────────────────────────────┐
│                   FRAMEWORK DECISION POINT                   │
│                                                              │
│   Complexity ─────────────────────────────────────────────▶ │
│                                                              │
│   [Simple]              [Threshold]              [Complex]   │
│                              │                               │
│   Raw while loop             │         LangGraph             │
│   - 1-3 tools               │         - 4+ tools            │
│   - No branching            │         - Conditional flows    │
│   - No persistence          │         - Checkpointing        │
│   - No human review         │         - Human-in-loop        │
│   - Quick prototype         │         - Production system    │
│                              │                               │
│   ◀───── "Just works" ─────▶│◀───── "Needs structure" ─────▶│
└─────────────────────────────────────────────────────────────┘
```

---

## LangGraph vs. Other Frameworks

Quick comparison for context (you'll focus on LangGraph, but awareness helps):

|Framework|Philosophy|Best For|
|---|---|---|
|**LangGraph**|Low-level, explicit graph control|Custom, complex workflows with full control|
|**CrewAI**|High-level, role-based agents|Quick multi-agent prototypes, "team" metaphors|
|**OpenAI Agents SDK**|Minimal, code-first|Simple agents in OpenAI ecosystem|
|**AutoGen**|Conversational multi-agent|Agents that "chat" with each other|

**LangGraph's positioning**: Maximum control, minimum magic. You define everything explicitly. This is harder to learn but easier to debug.

---

## The Graph Mental Model for Agents

Here's how a typical agent maps to a graph:

### ReAct Agent as a Graph

```
┌───────────────────────────────────────────────────────────────┐
│                     ReAct AGENT GRAPH                         │
│                                                               │
│   ┌─────────┐      ┌─────────────┐                           │
│   │  START  │─────▶│   Agent     │◀──────────────────┐       │
│   └─────────┘      │   (LLM)     │                   │       │
│                    └──────┬──────┘                   │       │
│                           │                          │       │
│                    ┌──────┴──────┐                   │       │
│                    ▼             ▼                   │       │
│              [has tools?]   [no tools]               │       │
│                    │             │                   │       │
│                    ▼             ▼                   │       │
│              ┌──────────┐   ┌─────────┐             │       │
│              │  Tools   │   │   END   │             │       │
│              │ (execute)│   └─────────┘             │       │
│              └─────┬────┘                           │       │
│                    │                                │       │
│                    └────────────────────────────────┘       │
│                         (loop back with results)             │
└───────────────────────────────────────────────────────────────┘
```

**The cycle**: Agent thinks → Decides to use tools → Tools execute → Results go back to agent → Agent thinks again → Eventually outputs final answer.

This is exactly what your Week 3 while loop did — but now it's explicit, visualizable, checkpointable, and debuggable.

---

## Key Takeaways

1. **Graphs are the natural structure** for complex, stateful, branching workflows
2. **LangGraph provides production primitives** — checkpointing, streaming, human-in-loop — not just graph syntax
3. **State flows through nodes** — each node reads state, returns updates, state merges
4. **Start with raw code for simple agents**, switch to LangGraph when complexity demands it
5. **LangGraph is low-level by design** — explicit control, not magic abstractions
6. **The mental model**: State machine where nodes are steps, edges are transitions, and state is the shared context

---

## What's Next

Now that you understand _why_ graphs and _when_ to use LangGraph, the next notes cover:

- `StateGraph` and compilation mechanics
- State schema with `TypedDict`
- Reducers (how state updates work)
- Nodes and edges in detail
- Execution model (message passing, super-steps)
- Graph visualization

---

_Sources: LangGraph documentation (langchain-ai.github.io/langgraph), LangChain blog posts on agent frameworks (April 2025, November 2025), framework comparison analyses (2025-2026)_