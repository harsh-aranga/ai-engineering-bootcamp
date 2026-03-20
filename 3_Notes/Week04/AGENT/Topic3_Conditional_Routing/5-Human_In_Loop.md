# Human-in-the-Loop: interrupt() and Resumption (Expanded)

## What is interrupt()?

`interrupt()` is a function that **pauses graph execution**, surfaces a value to the caller, and **waits for human input** before resuming. Think of it as Python's `input()` but for production systems — it works across processes, machines, and time.

```python
from langgraph.types import interrupt

def my_node(state):
    # Execution pauses here
    user_response = interrupt("Do you approve this action?")
    
    # Execution resumes here when human provides input
    if user_response == "yes":
        return {"status": "approved"}
    return {"status": "rejected"}
```

## Why interrupt() Over interrupt_before/interrupt_after?

LangGraph has two interrupt mechanisms:

|Mechanism|When Introduced|Flexibility|Use Case|
|---|---|---|---|
|`interrupt_before` / `interrupt_after`|Earlier|Low — pauses at node boundaries|Simple approval gates|
|`interrupt()` function|Later (recommended)|High — pause anywhere in node|Complex workflows, multiple pauses, conditional interrupts|

**Use `interrupt()` for new code.** It's more expressive and handles complex scenarios.

## Requirements for interrupt() to Work

### 1. Checkpointer Required

`interrupt()` saves state to resume later. Without a checkpointer, there's nowhere to save:

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

# In-memory (development/testing)
graph = builder.compile(checkpointer=MemorySaver())

# SQLite (persistent across restarts)
graph = builder.compile(checkpointer=SqliteSaver.from_conn_string("checkpoints.db"))

# PostgreSQL (production)
# from langgraph.checkpoint.postgres import PostgresSaver
# graph = builder.compile(checkpointer=PostgresSaver(...))
```

### 2. Thread ID Required

Each conversation/session needs a unique `thread_id` to track its checkpoint:

```python
config = {"configurable": {"thread_id": "user-123-session-456"}}

# First invoke — runs until interrupt
result = graph.invoke({"query": "Delete all files"}, config=config)

# Resume with same thread_id
result = graph.invoke(Command(resume="approved"), config=config)
```

## Basic interrupt() Pattern

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

class State(TypedDict):
    action: str
    approved: bool
    result: str

def propose_action(state: State) -> dict:
    return {"action": "Delete 50 files from /tmp"}

def get_approval(state: State) -> dict:
    """Pause for human approval."""
    
    # This pauses execution and surfaces the message
    response = interrupt(f"Approve action: {state['action']}? (yes/no)")
    
    # When resumed, response contains the human's input
    return {"approved": response.lower() == "yes"}

def execute_action(state: State) -> dict:
    if state["approved"]:
        return {"result": f"Executed: {state['action']}"}
    return {"result": "Action cancelled by user"}

# Build graph
builder = StateGraph(State)
builder.add_node("propose", propose_action)
builder.add_node("approve", get_approval)
builder.add_node("execute", execute_action)

builder.add_edge(START, "propose")
builder.add_edge("propose", "approve")
builder.add_edge("approve", "execute")
builder.add_edge("execute", END)

graph = builder.compile(checkpointer=MemorySaver())

# ─── Execution Flow ───
config = {"configurable": {"thread_id": "thread-1"}}

# Step 1: Run until interrupt
result = graph.invoke({"action": "", "approved": False, "result": ""}, config)
print(result)
# {'__interrupt__': (Interrupt(value='Approve action: Delete 50 files from /tmp? (yes/no)', ...),)}

# Step 2: Resume with human input
result = graph.invoke(Command(resume="yes"), config)
print(result)
# {'action': 'Delete 50 files from /tmp', 'approved': True, 'result': 'Executed: Delete 50 files from /tmp'}
```

## Resuming with Command(resume=...)

When a graph is interrupted, resume it by invoking with `Command(resume=value)`:

```python
from langgraph.types import Command

# Simple string response
graph.invoke(Command(resume="yes"), config)

# Structured response
graph.invoke(Command(resume={"approved": True, "comment": "Looks good"}), config)

# Resume with edited data
graph.invoke(Command(resume={
    "action": "approve",
    "modified_params": {"target": "/tmp/safe-folder"}  # Human edited the params
}), config)
```

The `resume` value becomes the **return value of the `interrupt()` call** inside the node.

## Structured Interrupt Payloads

Pass structured data to `interrupt()` to give humans context:

```python
def review_tool_call(state: State) -> dict:
    tool_call = state["pending_tool_call"]
    
    # Surface structured info for human review
    response = interrupt({
        "message": "Review this tool call before execution",
        "tool_name": tool_call["name"],
        "arguments": tool_call["args"],
        "risk_level": "high" if "delete" in tool_call["name"] else "low",
        "options": ["approve", "reject", "modify"]
    })
    
    if response["action"] == "approve":
        return {"execute_tool": True}
    elif response["action"] == "modify":
        return {"pending_tool_call": response["modified_call"], "execute_tool": True}
    else:
        return {"execute_tool": False}
```

## Multiple Interrupts in One Node

A node can have multiple `interrupt()` calls. LangGraph tracks them by **index order**:

```python
def collect_user_info(state: State) -> dict:
    # First interrupt
    name = interrupt("What is your name?")
    
    # Second interrupt (after first is resumed)
    age = interrupt("What is your age?")
    
    # Third interrupt (after second is resumed)
    city = interrupt("What city do you live in?")
    
    return {"name": name, "age": age, "city": city}
```

**Critical rule:** Interrupt calls must happen in the **same order** every time the node executes. Don't conditionally skip interrupts:

```python
# ❌ BAD: Conditional interrupt — order changes between executions
def bad_node(state):
    name = interrupt("Name?")
    if state["needs_age"]:
        age = interrupt("Age?")  # Sometimes skipped!
    city = interrupt("City?")
    return {...}

# ✅ GOOD: Consistent order every time
def good_node(state):
    name = interrupt("Name?")
    age = interrupt("Age?")  # Always called
    city = interrupt("City?")
    return {...}
```

## Resumption Lifecycle

Understanding what happens under the hood:

```
1. graph.invoke(input, config)
   → Node runs until interrupt()
   → State saved to checkpoint
   → Returns {'__interrupt__': (Interrupt(value=...), ...)}

2. graph.invoke(Command(resume="user_input"), config)
   → Checkpoint loaded
   → Node re-executes from beginning
   → interrupt() returns "user_input" immediately (from resume list)
   → Node continues past interrupt()
   → If another interrupt() exists, pause again
   → Otherwise, proceed to next node
```

**Key insight:** The node **re-runs from the start** when resumed. Each `interrupt()` checks if there's a matching resume value by index.

## Dynamic Interrupts (Conditional Pause)

Sometimes you only want to interrupt under certain conditions:

```python
def maybe_interrupt(state: State) -> dict:
    risk_score = calculate_risk(state["action"])
    
    if risk_score > 0.8:
        # High risk — require approval
        response = interrupt({
            "message": "High-risk action detected",
            "risk_score": risk_score,
            "action": state["action"]
        })
        if response != "approved":
            return {"cancelled": True}
    
    # Low risk or approved — proceed
    return {"cancelled": False}
```

**Note:** This is fine because the interrupt either happens or it doesn't — we're not changing the order of multiple interrupts.

## Tool Call Approval Pattern

Common pattern: pause before executing tool calls for human review:

```python
from langgraph.types import interrupt, Command

def review_tool_calls(state: State) -> dict:
    """Review pending tool calls before execution."""
    tool_calls = state["messages"][-1].tool_calls
    
    if not tool_calls:
        return {}
    
    # Surface tool calls for review
    response = interrupt({
        "message": "Review these tool calls:",
        "tools": [
            {"name": tc["name"], "args": tc["args"]}
            for tc in tool_calls
        ]
    })
    
    if response["action"] == "approve":
        return {"approved_tools": tool_calls}
    elif response["action"] == "reject":
        # Skip tool execution entirely
        return Command(goto="generate_response")  # Jump to response node
    elif response["action"] == "edit":
        # Use modified tool calls
        return {"approved_tools": response["modified_tools"]}
```

## Input Validation Pattern

Use interrupt loops to validate human input:

```python
def get_valid_age(state: State) -> dict:
    """Keep asking until valid age provided."""
    
    prompt = "What is your age?"
    
    while True:
        response = interrupt(prompt)
        
        try:
            age = int(response)
            if 0 < age < 150:
                return {"age": age}
            prompt = f"'{response}' is not a realistic age. Please enter a valid age:"
        except ValueError:
            prompt = f"'{response}' is not a number. Please enter your age as a number:"
```

Each iteration through the loop triggers a new interrupt. The human keeps getting prompted until they provide valid input.

## Combining interrupt() with Command Routing

After an interrupt, you can use `Command` to route dynamically:

```python
from langgraph.types import interrupt, Command
from typing import Literal

def approval_gate(state: State) -> Command[Literal["execute", "revise", "cancel"]]:
    response = interrupt({
        "message": "Review proposed action",
        "action": state["proposed_action"]
    })
    
    if response == "approve":
        return Command(update={"approved": True}, goto="execute")
    elif response == "revise":
        return Command(update={"needs_revision": True}, goto="revise")
    else:
        return Command(update={"cancelled": True}, goto="cancel")
```

## Detecting Interrupted State

Check if a graph is currently interrupted:

```python
# After invoking
result = graph.invoke(input, config)

if "__interrupt__" in result:
    # Graph is paused, waiting for human input
    interrupt_info = result["__interrupt__"]
    print(f"Interrupted with: {interrupt_info[0].value}")
else:
    # Graph completed normally
    print("Execution complete")
```

## Accessing Interrupt State

Inspect the current state of an interrupted graph:

```python
# Get current state (works mid-interrupt)
state = graph.get_state(config)

print(state.values)      # Current state values
print(state.next)        # Next node(s) to execute
print(state.tasks)       # Pending tasks including interrupt info

# Check for interrupts
for task in state.tasks:
    if task.interrupts:
        for intr in task.interrupts:
            print(f"Interrupt value: {intr.value}")
```

## Full Example: Document Review Workflow

```python
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

class ReviewState(TypedDict):
    document: str
    ai_summary: str
    human_feedback: str
    final_decision: str
    revision_count: int

def generate_summary(state: ReviewState) -> dict:
    # Simulate AI summarization
    summary = f"Summary of: {state['document'][:50]}..."
    return {"ai_summary": summary}

def human_review(state: ReviewState) -> Command[Literal["finalize", "revise"]]:
    """Pause for human review of AI summary."""
    
    response = interrupt({
        "type": "review_request",
        "document": state["document"],
        "ai_summary": state["ai_summary"],
        "revision_count": state["revision_count"],
        "options": ["approve", "reject", "request_changes"]
    })
    
    if response["decision"] == "approve":
        return Command(
            update={"human_feedback": "Approved", "final_decision": "approved"},
            goto="finalize"
        )
    elif response["decision"] == "reject":
        return Command(
            update={"human_feedback": response.get("reason", "Rejected"), "final_decision": "rejected"},
            goto="finalize"
        )
    else:
        # Request changes — go back to revision
        return Command(
            update={
                "human_feedback": response.get("feedback", ""),
                "revision_count": state["revision_count"] + 1
            },
            goto="revise"
        )

def revise_summary(state: ReviewState) -> dict:
    """Revise summary based on feedback."""
    revised = f"{state['ai_summary']} [Revised based on: {state['human_feedback']}]"
    return {"ai_summary": revised}

def finalize(state: ReviewState) -> dict:
    return {"final_decision": state["final_decision"]}

# Build graph
builder = StateGraph(ReviewState)
builder.add_node("summarize", generate_summary)
builder.add_node("review", human_review, ends=["finalize", "revise"])
builder.add_node("revise", revise_summary)
builder.add_node("finalize", finalize)

builder.add_edge(START, "summarize")
builder.add_edge("summarize", "review")
builder.add_edge("revise", "review")  # Loop back for re-review
builder.add_edge("finalize", END)

graph = builder.compile(checkpointer=MemorySaver())

# ─── Usage ───
config = {"configurable": {"thread_id": "review-123"}}

# Start review
result = graph.invoke({
    "document": "This is a long document about AI safety...",
    "ai_summary": "",
    "human_feedback": "",
    "final_decision": "",
    "revision_count": 0
}, config)
# Returns interrupt with review request

# Human approves
result = graph.invoke(
    Command(resume={"decision": "approve"}),
    config
)
print(result["final_decision"])  # "approved"
```

## Key Takeaways

1. **`interrupt()` pauses anywhere** — More flexible than `interrupt_before/after`
2. **Checkpointer required** — State must persist across pause/resume
3. **Thread ID required** — Identifies which conversation to resume
4. **Resume with `Command(resume=value)`** — Value becomes interrupt's return
5. **Node re-executes on resume** — Interrupts matched by index order
6. **Keep interrupt order consistent** — Don't conditionally skip interrupts
7. **Combine with Command for routing** — Dynamic paths after human input
8. **Structured payloads** — Give humans rich context for decisions

---

**Next:** Note 6 covers Testing Complex Graphs — unit tests, routing verification, and mocking LLM calls.

_Sources: LangGraph docs (docs.langchain.com/oss/python/langgraph/interrupts), LangGraph interrupt how-to guides, LangGraph changelog_