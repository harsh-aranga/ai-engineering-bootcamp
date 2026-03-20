# Note 3: Resumption with `Command`

## The Resume Problem

After an interrupt pauses execution (covered in Note 2), you need to:

1. Provide the human's response back to the graph
2. Continue execution from where it stopped
3. Optionally modify state before continuing

LangGraph provides three mechanisms for this, each solving a different aspect of the problem.

---

## Mechanism 1: `Command(resume=...)`

This is the modern, recommended way to resume after an `interrupt()` call.

### Basic Usage

```python
from langgraph.types import Command

# Graph paused at interrupt()
result = graph.invoke({"messages": [...]}, config)
# result["__interrupt__"] shows what we're waiting for

# Resume with human's response
final = graph.invoke(Command(resume={"approved": True}), config)
```

The value passed to `resume=` becomes the **return value** of the `interrupt()` call inside the node:

```python
def approval_node(state):
    # This pauses execution
    human_response = interrupt({"question": "Approve this action?"})
    
    # When resumed with Command(resume={"approved": True}),
    # human_response = {"approved": True}
    
    if human_response.get("approved"):
        return {"status": "approved"}
    return {"status": "rejected"}
```

### The Resume Value Can Be Anything JSON-Serializable

```python
# Simple boolean
Command(resume=True)

# String
Command(resume="approve")

# Structured data
Command(resume={
    "decision": "approve",
    "edited_to": "john@example.com",
    "note": "Changed recipient per manager request"
})

# List
Command(resume=["query1", "query2", "query3"])
```

Design your `interrupt()` payload to tell the human what format of response you expect. Design your resume value to match that expectation.

---

## Mechanism 2: `graph.invoke(None, config)` for Static Breakpoints

For static breakpoints (`interrupt_before`, `interrupt_after`), you resume by invoking with `None`:

```python
# Graph compiled with interrupt_before=["tools"]
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["tools"]
)

# First invoke — runs until breakpoint
result = graph.invoke(input, config)

# Resume — just continue, no new input needed
result = graph.invoke(None, config)
```

`None` means "I'm not providing new input, just continue from the checkpoint."

**Important:** This only works for static breakpoints. For `interrupt()`, you must use `Command(resume=...)`.

---

## Mechanism 3: `graph.update_state()` for Modifying State Before Resume

Sometimes the human doesn't just approve/reject — they need to change the state itself. Use `update_state()` before resuming:

```python
# Graph paused
result = graph.invoke(input, config)

# Human reviews and wants to modify the proposed action
graph.update_state(
    config,
    {
        "proposed_action": {
            "tool": "send_email",
            "to": "corrected@example.com",  # Human corrected this
            "body": "Updated message"
        }
    }
)

# Now resume
result = graph.invoke(None, config)  # For static breakpoints
# OR
result = graph.invoke(Command(resume={"proceed": True}), config)  # For interrupt()
```

### When to Use `update_state()` vs. `Command(resume=...)`

|Scenario|Use|
|---|---|
|Human provides simple approval/rejection|`Command(resume=True/False)`|
|Human provides response that the node will process|`Command(resume={...})`|
|Human needs to change state fields directly|`update_state()` then resume|
|Human wants to edit the pending action|Either works — design choice|

**Design consideration:** If your node expects to receive and process human input, use `Command(resume=...)`. If your node just checks state and proceeds, use `update_state()`.

---

## Combining `Command` with Routing: `goto`

`Command` can do more than just resume — it can also route to a different node:

```python
from langgraph.types import Command
from typing import Literal

def human_decision_node(state) -> Command[Literal["approved_path", "rejected_path"]]:
    decision = interrupt({
        "question": "Approve this action?",
        "details": state["proposed_action"]
    })
    
    if decision.get("approved"):
        return Command(
            goto="approved_path",
            update={"decision": "approved", "reviewer_note": decision.get("note")}
        )
    else:
        return Command(
            goto="rejected_path", 
            update={"decision": "rejected", "rejection_reason": decision.get("reason")}
        )
```

**`Command` fields:**

- `resume` — value to return from `interrupt()` (used when invoking the graph)
- `goto` — next node to execute (used when returning from a node)
- `update` — state updates to apply (used when returning from a node)

**Important distinction:**

- `Command(resume=...)` is passed to `graph.invoke()` from outside
- `Command(goto=..., update=...)` is returned from a node function inside the graph

---

## Structured Resume Payloads: The Approve/Edit/Reject Pattern

A common pattern is to support three response types:

```python
def tool_approval_node(state):
    tool_call = state["pending_tool_call"]
    
    response = interrupt({
        "type": "tool_approval",
        "tool": tool_call["name"],
        "args": tool_call["args"],
        "instructions": "Respond with {type: 'approve'|'edit'|'reject', ...}"
    })
    
    if response["type"] == "approve":
        # Execute as-is
        return execute_tool(tool_call)
    
    elif response["type"] == "edit":
        # Execute with modified args
        edited_call = {**tool_call, "args": response["edited_args"]}
        return execute_tool(edited_call)
    
    elif response["type"] == "reject":
        # Don't execute, return rejection
        return {
            "tool_result": None,
            "status": "rejected",
            "reason": response.get("reason", "User rejected")
        }
```

Corresponding resume calls:

```python
# Approve
graph.invoke(Command(resume={"type": "approve"}), config)

# Edit
graph.invoke(Command(resume={
    "type": "edit",
    "edited_args": {"to": "different@email.com", "body": "Modified message"}
}), config)

# Reject
graph.invoke(Command(resume={
    "type": "reject",
    "reason": "This email shouldn't be sent to external addresses"
}), config)
```

---

## Multiple Parallel Interrupts

When parallel branches both call `interrupt()`, you need to resume all of them. LangGraph v0.4+ supports mapping interrupt IDs to resume values:

```python
# Graph with parallel branches that both interrupt
result = graph.invoke(input, config)

# result["__interrupt__"] contains multiple Interrupt objects
# [
#   Interrupt(value="Question A", id="abc123"),
#   Interrupt(value="Question B", id="def456")
# ]

# Resume by mapping IDs to values
graph.invoke(
    Command(resume={
        "abc123": "Answer to A",
        "def456": "Answer to B"
    }),
    config
)
```

### Extracting Interrupt IDs

```python
result = graph.invoke(input, config)

if "__interrupt__" in result:
    for intr in result["__interrupt__"]:
        print(f"ID: {intr.id}")
        print(f"Payload: {intr.value}")
```

### Known Issues with Parallel Interrupts

As of late 2025, there are known bugs with parallel interrupts:

- Issue #6626: Parallel tools in the same `ToolNode` can generate identical IDs
- Issue #6533: Resume values can be misrouted between parallel tools
- Issue #6624: `ToolNode` doesn't collect all interrupts from parallel execution

**Practical workaround:** If you need multiple approval-gated tools, put them in separate nodes rather than relying on parallel execution within a single `ToolNode`.

---

## The Node Re-execution Behavior

**Critical to understand:** When you resume after `interrupt()`, the node restarts from the beginning.

```python
def my_node(state):
    print("Node starting")  # This prints AGAIN on resume
    
    do_some_work()  # This runs AGAIN on resume
    
    response = interrupt("Need approval")  # On resume, this returns the resume value
    
    do_more_work()  # This only runs after resume
    
    return {"result": response}
```

**Timeline:**

1. First invoke → "Node starting" prints → `do_some_work()` runs → `interrupt()` pauses
2. Resume with `Command(resume=...)` → "Node starting" prints AGAIN → `do_some_work()` runs AGAIN → `interrupt()` returns resume value → `do_more_work()` runs → node completes

This is the "double execution" problem. The `interrupt()` call itself doesn't pause mid-function — it raises an exception that saves state. On resume, the entire node function runs again, but this time `interrupt()` returns immediately with the stored resume value instead of pausing.

**Implications:**

- Side effects before `interrupt()` happen twice
- Expensive computations before `interrupt()` run twice
- Non-idempotent operations before `interrupt()` can cause problems

**Solutions:**

1. Put side effects/expensive work AFTER `interrupt()`, not before
2. Store intermediate results in state so you can skip recomputation
3. Make operations idempotent (same result if run multiple times)

```python
def my_node(state):
    # Check if we already did the expensive work
    if state.get("expensive_result") is None:
        result = expensive_computation()
        # Note: This update won't persist across the interrupt!
        # You'd need to restructure to a multi-node approach
    
    response = interrupt("Approve?")
    
    # Safe to do work here — only runs once
    return {"final": response}
```

**Better pattern:** Split into multiple nodes:

```python
def compute_node(state):
    result = expensive_computation()
    return {"expensive_result": result}

def approval_node(state):
    response = interrupt({
        "computed": state["expensive_result"],
        "question": "Approve this result?"
    })
    return {"approved": response.get("approved")}

# Wire them: compute_node → approval_node
```

Now the expensive computation only happens once.

---

## Resume Configuration Requirements

When resuming, you need the same `thread_id` that was used for the original invoke:

```python
config = {"configurable": {"thread_id": "my-thread-123"}}

# Original invoke
result = graph.invoke(input, config)

# Later... maybe even after server restart
# Same thread_id resumes the same execution
result = graph.invoke(Command(resume=True), config)
```

For `interrupt()`, that's typically all you need. The checkpointer knows where execution paused.

If you're using `update_state()` or need to target a specific checkpoint:

```python
# Get current state
state = graph.get_state(config)

# state.config contains the exact checkpoint config
# {"configurable": {"thread_id": "...", "checkpoint_id": "...", "checkpoint_ns": "..."}}

# For update_state, use the config from state
graph.update_state(state.config, {"field": "new_value"})
```

---

## Complete Resume Flow Example

Putting it all together:

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from typing import TypedDict, Optional

class State(TypedDict):
    query: str
    proposed_email: Optional[dict]
    result: Optional[str]

def draft_email(state: State):
    # Agent drafts an email based on query
    email = {
        "to": "customer@example.com",
        "subject": f"Re: {state['query']}",
        "body": f"Thank you for your inquiry about {state['query']}..."
    }
    return {"proposed_email": email}

def human_review(state: State):
    email = state["proposed_email"]
    
    # Pause for human review
    response = interrupt({
        "type": "email_review",
        "email": email,
        "instructions": "Respond with {action: 'send'|'edit'|'cancel', ...}"
    })
    
    if response["action"] == "send":
        # Send as-is
        send_email(email)
        return {"result": f"Email sent to {email['to']}"}
    
    elif response["action"] == "edit":
        # Send with edits
        edited = {**email, **response.get("edits", {})}
        send_email(edited)
        return {"result": f"Edited email sent to {edited['to']}"}
    
    else:  # cancel
        return {"result": "Email cancelled"}

def send_email(email):
    print(f"Sending email to {email['to']}: {email['subject']}")

# Build graph
builder = StateGraph(State)
builder.add_node("draft", draft_email)
builder.add_node("review", human_review)
builder.add_edge(START, "draft")
builder.add_edge("draft", "review")
builder.add_edge("review", END)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# --- Execution ---

config = {"configurable": {"thread_id": "email-thread-1"}}

# Step 1: Start the workflow
result = graph.invoke({"query": "pricing information"}, config)

# Graph paused at interrupt()
print(result["__interrupt__"])
# [Interrupt(value={'type': 'email_review', 'email': {...}, ...})]

# Step 2: Human reviews and decides to edit
final = graph.invoke(
    Command(resume={
        "action": "edit",
        "edits": {"to": "vip-customer@example.com"}
    }),
    config
)

print(final["result"])
# "Edited email sent to vip-customer@example.com"
```

---

## Key Takeaways

1. **`Command(resume=...)` is the modern resume mechanism** for `interrupt()`. The resume value becomes the return value of `interrupt()` inside the node.
    
2. **`graph.invoke(None, config)` is for static breakpoints** (`interrupt_before`, `interrupt_after`). It means "continue without new input."
    
3. **`update_state()` modifies state before resuming.** Use it when the human needs to change state fields directly, not just provide a response.
    
4. **`Command` has three uses:**
    
    - `Command(resume=...)` — passed to `invoke()` to resume
    - `Command(goto=...)` — returned from node to route dynamically
    - `Command(update=...)` — returned from node to update state
5. **Nodes re-execute from the beginning on resume.** Design accordingly — put side effects after `interrupt()`, or split into multiple nodes.
    
6. **For parallel interrupts, map interrupt IDs to resume values.** But be aware of known bugs — consider sequential nodes instead.
    

---

## What's Next

This note covered _how_ to resume execution. The next note covers:

- **Note 4:** What information to show humans at the interrupt (UX design)