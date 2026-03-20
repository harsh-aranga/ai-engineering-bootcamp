# Note 2: Pausing Execution — Breakpoints and `interrupt()`

## The Core Problem: How Do You Stop a Running Graph?

When a LangGraph workflow executes, it flows from node to node automatically. To implement human-in-the-loop, you need a way to:

1. **Stop** execution at a specific point
2. **Save** the current state so execution can resume later
3. **Surface** information to the human about why you stopped

LangGraph provides two mechanisms for this: **static breakpoints** (compile-time) and **dynamic interrupts** (runtime). They solve the same fundamental problem but with different trade-offs.

---

## Mechanism 1: Static Breakpoints (`interrupt_before` / `interrupt_after`)

Static breakpoints are declared when you compile the graph. They always fire at the same places — before or after specific nodes.

### How It Works

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# Define your graph as usual
builder = StateGraph(State)
builder.add_node("agent", agent_node)
builder.add_node("tools", tools_node)
builder.add_edge(START, "agent")
builder.add_edge("agent", "tools")
builder.add_edge("tools", END)

# Compile WITH breakpoints
checkpointer = MemorySaver()
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["tools"],      # Pause BEFORE tools node runs
    interrupt_after=["agent"],       # Pause AFTER agent node completes
)
```

**Key points:**

- `interrupt_before=["tools"]` — graph pauses _before_ the `tools` node executes
- `interrupt_after=["agent"]` — graph pauses _after_ the `agent` node completes
- You can use `"*"` to pause before/after _every_ node (useful for debugging)

### Execution Flow with Static Breakpoints

```
graph.invoke(inputs, config) 
    │
    ▼
[START] ──► [agent] ──► PAUSE (interrupt_after)
                            │
                            ▼
                      State saved to checkpointer
                      Control returns to caller
                            │
                            ▼
graph.invoke(None, config)  ◄── Resume with None (no new input)
    │
    ▼
PAUSE (interrupt_before) ──► [tools] ──► [END]
    │
    ▼
State saved again
Control returns to caller
    │
    ▼
graph.invoke(None, config)  ◄── Resume again
    │
    ▼
[tools] executes ──► [END]
```

### When the Graph Pauses

When a breakpoint fires, `graph.invoke()` returns immediately with the current state. The returned state dictionary contains a special `__interrupt__` key (in older versions) or you can inspect `graph.get_state(config)` to see where execution stopped.

```python
config = {"configurable": {"thread_id": "my-thread"}}

# First invocation — runs until first breakpoint
result = graph.invoke({"messages": [HumanMessage("Do something")]}, config)

# Check what's pending
state = graph.get_state(config)
print(state.next)  # ('tools',) — shows which node is waiting to run
```

### Resuming After a Static Breakpoint

To continue, invoke the graph with `None` as input:

```python
# Human reviews state, decides to proceed
# Resume by invoking with None
result = graph.invoke(None, config)
```

The `None` tells LangGraph: "I'm not providing new input, just continue from where you stopped."

### Modifying State Before Resuming

If you need to change state before continuing (e.g., reject a tool call, modify parameters):

```python
# Update the state
graph.update_state(config, {"messages": modified_messages})

# Then resume
result = graph.invoke(None, config)
```

### Static Breakpoint Limitations

1. **No conditional pausing** — breakpoints _always_ fire at the specified nodes
2. **No custom payload** — you can't send additional information about _why_ you paused
3. **Coarse-grained** — you can only pause at node boundaries, not mid-node

---

## Mechanism 2: Dynamic Interrupts (`interrupt()`)

The `interrupt()` function is the modern, flexible way to pause execution. It can be called anywhere inside a node and supports conditional logic.

### How It Works

```python
from langgraph.types import interrupt

def approval_node(state: State):
    # Do some work...
    proposed_action = state["proposed_action"]
    
    # Pause and surface information to the human
    human_response = interrupt({
        "action": "send_email",
        "to": proposed_action["recipient"],
        "subject": proposed_action["subject"],
        "message": "Approve sending this email?"
    })
    
    # When resumed, human_response contains whatever was passed via Command(resume=...)
    if human_response.get("approved"):
        return {"status": "approved"}
    else:
        return {"status": "rejected"}
```

**Key points:**

- `interrupt(payload)` pauses execution and returns control to the caller
- The `payload` (must be JSON-serializable) is surfaced to the caller via `__interrupt__`
- When resumed with `Command(resume=value)`, the `interrupt()` call returns `value`

### The Interrupt Payload

The payload you pass to `interrupt()` becomes visible to the caller:

```python
result = graph.invoke({"messages": [...]}, config)

# The interrupt payload surfaces here
print(result["__interrupt__"])
# [Interrupt(value={'action': 'send_email', 'to': '...', 'message': '...'}, id='abc123')]
```

The payload structure is entirely up to you. Common fields:

- `action` — what the agent wants to do
- `args` — the parameters for that action
- `reason` — why the agent chose this action
- `instructions` — what kind of human response is expected

### Resuming After `interrupt()`

Use `Command(resume=...)` to provide the human's response:

```python
from langgraph.types import Command

# Human approves
result = graph.invoke(Command(resume={"approved": True}), config)

# Or human rejects
result = graph.invoke(Command(resume={"approved": False}), config)

# Or human provides edited values
result = graph.invoke(
    Command(resume={"approved": True, "to": "different@email.com"}), 
    config
)
```

### Conditional Interrupts

Unlike static breakpoints, `interrupt()` can be conditional:

```python
def action_node(state: State):
    action = state["proposed_action"]
    
    # Only pause for high-risk actions
    if action["risk_level"] == "high":
        decision = interrupt({
            "action": action,
            "message": "High-risk action requires approval"
        })
        if not decision.get("approved"):
            return {"status": "rejected"}
    
    # Low-risk actions proceed automatically
    execute_action(action)
    return {"status": "completed"}
```

### `interrupt()` Inside Tools

You can place `interrupt()` directly inside tool functions:

```python
from langchain_core.tools import tool
from langgraph.types import interrupt

@tool
def send_email(to: str, subject: str, body: str):
    """Send an email to a recipient."""
    
    # Pause for human approval before actually sending
    response = interrupt({
        "tool": "send_email",
        "args": {"to": to, "subject": subject, "body": body},
        "message": "Approve sending this email?"
    })
    
    if response.get("action") == "approve":
        # Human might have edited the args
        final_to = response.get("to", to)
        final_subject = response.get("subject", subject)
        final_body = response.get("body", body)
        
        # Actually send
        return f"Email sent to {final_to}"
    
    return "Email cancelled by user"
```

This pattern makes the tool itself approval-gated, regardless of which node calls it.

---

## Comparing the Two Mechanisms

|Aspect|Static Breakpoints|`interrupt()`|
|---|---|---|
|**When defined**|Compile time|Runtime|
|**Granularity**|Node boundaries only|Anywhere in code|
|**Conditional**|No (always fires)|Yes|
|**Custom payload**|No|Yes (any JSON-serializable value)|
|**Resume method**|`graph.invoke(None, config)`|`graph.invoke(Command(resume=...), config)`|
|**Use case**|Debugging, step-through|Production HITL|

### Decision Guide

**Use static breakpoints when:**

- Debugging graph execution step-by-step
- You want to pause at the same place every time
- You're building a development/testing harness
- You don't need to pass information about _why_ you paused

**Use `interrupt()` when:**

- Building production human-in-the-loop
- Pausing should be conditional on state
- You need to surface structured information for the human to review
- The human's response will be used in the node's logic

### Using Both Together

You can combine them. Static breakpoints provide coarse-grained control at node boundaries; `interrupt()` provides fine-grained control within nodes.

```python
# Static breakpoint before tools node (always pauses)
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["tools"]
)

# Plus interrupt() inside a specific tool for conditional approval
@tool
def dangerous_operation(params: dict):
    if params["risk"] > 0.8:
        interrupt({"message": "Extra approval needed for high-risk operation"})
    # ...
```

---

## The Checkpointer Requirement

Both mechanisms require a checkpointer. Without one, there's nowhere to save state, so resumption is impossible.

```python
# This will fail at runtime if an interrupt is triggered:
graph = builder.compile()  # No checkpointer!
graph.invoke(...)  # Hits interrupt() → RuntimeError
```

### Checkpointer Options

|Checkpointer|Use Case|Persistence|
|---|---|---|
|`MemorySaver`|Development, testing|In-memory only (lost on restart)|
|`SqliteSaver`|Local development, single-process|SQLite file|
|`PostgresSaver`|Production|PostgreSQL database|
|`AsyncPostgresSaver`|Production (async)|PostgreSQL database|
|`DynamoDBSaver`|AWS production|DynamoDB + S3 for large states|

**Production rule:** Use `MemorySaver` only for development. Any real HITL system needs a persistent checkpointer because:

1. The human might take hours/days to respond
2. Your server might restart while waiting
3. Multiple server instances might need to access the same state

```python
# Development
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()

# Production
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
```

---

## The `__interrupt__` Structure

When execution pauses, the interrupt information is surfaced in the result:

```python
result = graph.invoke(input, config)

if "__interrupt__" in result:
    for interrupt_info in result["__interrupt__"]:
        print(interrupt_info.value)  # The payload you passed to interrupt()
        print(interrupt_info.id)     # Unique ID for this interrupt
```

The structure:

```python
Interrupt(
    value={...},          # Your payload from interrupt(payload)
    id="abc123...",       # Unique identifier
    resumable=True,       # Can this be resumed?
    ns=["node_name:..."], # Namespace info
    when="during"         # When the interrupt occurred
)
```

For static breakpoints, the `__interrupt__` list may be empty, but `graph.get_state(config).next` tells you which node is waiting.

---

## Thread IDs: The Resume Handle

The `thread_id` in the config is your handle for resuming:

```python
config = {"configurable": {"thread_id": "conversation-123"}}

# First invoke — creates checkpoint under this thread_id
result = graph.invoke(input, config)

# ... time passes, maybe server restarts ...

# Same thread_id resumes from where we left off
result = graph.invoke(Command(resume=True), config)
```

**Rules:**

- Same `thread_id` → resumes existing execution
- New `thread_id` → starts fresh execution
- Thread ID can be any string (user ID, session ID, conversation ID)

---

## Multiple Interrupts in Parallel Branches

If your graph has parallel branches that both call `interrupt()`, they pause simultaneously. When resuming, you need to provide responses for each:

```python
# Two parallel nodes both interrupted
result = graph.invoke(input, config)
# result["__interrupt__"] contains TWO Interrupt objects

# Resume by mapping interrupt IDs to responses
graph.invoke(
    Command(resume={
        "interrupt-id-1": {"approved": True},
        "interrupt-id-2": {"approved": False}
    }),
    config
)
```

This is an advanced pattern — most systems process one interrupt at a time.

---

## Key Takeaways

1. **Static breakpoints** (`interrupt_before`, `interrupt_after`) are compile-time, always fire, and are best for debugging or simple step-through workflows.
    
2. **`interrupt()`** is runtime, conditional, and supports custom payloads. It's the right choice for production HITL.
    
3. **Both require a checkpointer.** No checkpointer = no resumption.
    
4. **The interrupt payload** (passed to `interrupt()`) surfaces via `__interrupt__` in the result. Design it to contain everything the human needs to make a decision.
    
5. **Thread ID is your resume handle.** Same thread ID continues execution; new thread ID starts fresh.
    
6. **Static breakpoints resume with `None`; `interrupt()` resumes with `Command(resume=...)`.**
    

---

## What's Next

This note covered _how_ to pause execution. The next note covers:

- **Note 3:** How to resume — `Command`, `update_state()`, and structured resume payloads