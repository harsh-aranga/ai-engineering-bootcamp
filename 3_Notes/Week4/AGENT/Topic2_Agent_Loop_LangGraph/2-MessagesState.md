# MessagesState: Prebuilt Conversation State

## The Problem MessagesState Solves

Every conversational agent needs to track messages. In your Week 3 raw agent, you manually managed a list:

```python
messages = []
messages.append(HumanMessage(content="What's 15% of 230?"))
response = llm.invoke(messages)
messages.append(response)
# ... and so on
```

This works, but LangGraph needs to know **how** to update state when multiple nodes return values. If two nodes both return `{"messages": [...]}`, should LangGraph:

- Replace the old list with the new one?
- Append the new messages?
- Merge by message ID?

**Reducers** answer this question. `MessagesState` is LangGraph's prebuilt state with a smart reducer already configured.

---

## What is MessagesState?

`MessagesState` is a `TypedDict` with a single key `messages` that uses the `add_messages` reducer:

```python
from langgraph.graph import MessagesState

# This is essentially what MessagesState looks like internally:
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

**Key points:**

- `messages` is a list of `AnyMessage` (HumanMessage, AIMessage, ToolMessage, SystemMessage, etc.)
- `add_messages` is the **reducer function** that controls how updates are merged
- `Annotated[..., add_messages]` tells LangGraph to use this reducer for the `messages` key

---

## Understanding Reducers

### What's a Reducer?

A reducer is a pure function that takes two values and combines them:

```python
def reducer(current_value, new_value) -> merged_value:
    # Combine current and new into merged
    return merged_value
```

LangGraph applies reducers automatically when nodes return state updates.

### Without a Reducer: Replacement

If you don't specify a reducer, LangGraph **replaces** the old value:

```python
class State(TypedDict):
    count: int  # No reducer — new value replaces old

# Node 1 returns: {"count": 5}
# Node 2 returns: {"count": 10}
# Final state: {"count": 10}  ← Node 2's value replaced Node 1's
```

### With a Reducer: Custom Merge Logic

With `operator.add` as a reducer:

```python
from typing import Annotated
import operator

class State(TypedDict):
    count: Annotated[int, operator.add]  # Addition reducer

# Node 1 returns: {"count": 5}
# Node 2 returns: {"count": 10}
# Final state: {"count": 15}  ← Values were added
```

### The add_messages Reducer

`add_messages` does smart merging for message lists:

1. **Appends** new messages to the list
2. **Updates** existing messages by ID (if IDs match)
3. **Removes** messages when you send `RemoveMessage`

```python
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage

# Existing state
current = [HumanMessage(content="Hi", id="1")]

# Node returns new message
new = [AIMessage(content="Hello!", id="2")]

# add_messages merges them
result = add_messages(current, new)
# Result: [HumanMessage(..., id="1"), AIMessage(..., id="2")]
```

---

## Using MessagesState in a Graph

### Basic Usage

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_core.messages import HumanMessage

def my_node(state: MessagesState):
    # Access messages from state
    messages = state["messages"]
    
    # Do something...
    response = llm.invoke(messages)
    
    # Return update — add_messages will append this
    return {"messages": [response]}

# Build graph with MessagesState
builder = StateGraph(MessagesState)
builder.add_node("my_node", my_node)
builder.add_edge(START, "my_node")
builder.add_edge("my_node", END)

graph = builder.compile()

# Invoke with initial message
result = graph.invoke({"messages": [HumanMessage(content="Hello")]})
```

### What Happens Under the Hood

1. You invoke with `{"messages": [HumanMessage(content="Hello")]}`
2. `my_node` receives state with that message
3. `my_node` returns `{"messages": [response]}`
4. LangGraph applies `add_messages` reducer: `add_messages([HumanMessage(...)], [response])`
5. Final state has both messages appended

---

## Extending MessagesState

For real agents, you need more than just messages. Subclass `MessagesState`:

```python
from langgraph.graph import MessagesState
from typing import Annotated
import operator

class AgentState(MessagesState):
    # Inherited: messages with add_messages reducer
    
    # Add your own fields
    iteration_count: int  # No reducer — replaced on update
    documents: Annotated[list[str], operator.add]  # Append reducer
    final_answer: str | None
```

Now your nodes can track additional state:

```python
def agent_node(state: AgentState):
    response = llm.invoke(state["messages"])
    return {
        "messages": [response],
        "iteration_count": state.get("iteration_count", 0) + 1
    }
```

---

## Message Types in the State

The `messages` list can contain any LangChain message type:

|Type|Purpose|Example|
|---|---|---|
|`HumanMessage`|User input|`HumanMessage(content="What's the weather?")`|
|`AIMessage`|LLM response|`AIMessage(content="Let me check...", tool_calls=[...])`|
|`ToolMessage`|Tool execution result|`ToolMessage(content="72°F", tool_call_id="abc123")`|
|`SystemMessage`|System instructions|`SystemMessage(content="You are a helpful assistant")`|

All message types have an `id` field that `add_messages` uses for deduplication and updates.

---

## Message ID Handling

### Automatic ID Assignment

LangChain messages get auto-generated IDs if you don't provide one:

```python
msg = HumanMessage(content="Hello")
print(msg.id)  # Something like "a67e53c3-5dcf-4ddc-83f5-309b72ac61f4"
```

### Update by ID

If you return a message with the same ID as an existing one, `add_messages` **updates** instead of appending:

```python
# Existing state has:
# [AIMessage(content="Original", id="ai-1")]

# Node returns:
{"messages": [AIMessage(content="Updated!", id="ai-1")]}

# Result — message is updated, not duplicated:
# [AIMessage(content="Updated!", id="ai-1")]
```

This is useful for correcting or modifying earlier messages.

---

## Removing Messages

Use `RemoveMessage` to delete messages from state:

```python
from langchain_core.messages import RemoveMessage

def cleanup_node(state: MessagesState):
    # Remove all but the last 3 messages
    messages_to_remove = [
        RemoveMessage(id=m.id) 
        for m in state["messages"][:-3]
    ]
    return {"messages": messages_to_remove}
```

`add_messages` recognizes `RemoveMessage` and removes the matching ID from the list.

### Remove All Messages

Use the special constant `REMOVE_ALL_MESSAGES`:

```python
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langchain_core.messages import RemoveMessage

def clear_history(state: MessagesState):
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}
```

**Note:** Some prebuilt components like `ToolNode` expect at least one message, so clearing everything can cause issues.

---

## Why Not Just Use a List?

You might ask: "Why not just use `messages: list` and manage it myself?"

|Manual List|MessagesState + add_messages|
|---|---|
|You track appending manually|Automatic append|
|You handle deduplication|Automatic by ID|
|You implement message removal|Built-in `RemoveMessage`|
|No integration with checkpointing|Works with LangGraph persistence|
|You serialize/deserialize|Automatic message serialization|

The reducer pattern also enables **parallel execution**: if two nodes run simultaneously and both return messages, `add_messages` safely merges them without race conditions.

---

## Common Patterns

### Pattern 1: Agent with System Prompt

```python
from langchain_core.messages import SystemMessage

def agent_node(state: MessagesState):
    # Prepend system message when calling LLM
    system = SystemMessage(content="You are a helpful assistant.")
    response = llm.invoke([system] + state["messages"])
    return {"messages": [response]}
```

**Note:** The system message isn't stored in state — it's added at call time. This keeps state clean.

### Pattern 2: Tracking Tool Results

When using `ToolNode`, tool results are automatically added as `ToolMessage`:

```python
# Before tools node:
# state["messages"] = [HumanMessage(...), AIMessage(..., tool_calls=[...])]

# After tools node:
# state["messages"] = [HumanMessage(...), AIMessage(...), ToolMessage(...), ToolMessage(...)]
```

Each `ToolMessage` has a `tool_call_id` linking it back to the corresponding tool call.

### Pattern 3: Trimming for Context Window

Long conversations overflow context windows. Add a trimming node:

```python
def trim_messages(state: MessagesState):
    messages = state["messages"]
    
    # Keep system message (if any) + last N messages
    if len(messages) > 20:
        # Keep first (system) and last 19
        trimmed = messages[:1] + messages[-19:]
        # Remove the ones we're dropping
        to_remove = [RemoveMessage(id=m.id) for m in messages[1:-19]]
        return {"messages": to_remove}
    
    return {}  # No change needed
```

---

## MessagesState vs Custom State

### Use MessagesState When:

- Building a conversational agent
- The primary state is message history
- You want minimal boilerplate

### Use Custom State When:

- You need additional fields beyond messages
- You want different reducers for different fields
- You need complex state structures

### Subclassing Example

```python
from langgraph.graph import MessagesState
from typing import Annotated
import operator

class ResearchAgentState(MessagesState):
    # messages: inherited from MessagesState
    
    # Research-specific fields
    documents: Annotated[list[str], operator.add]  # Accumulate docs
    current_topic: str  # Replace on update
    search_count: int
    is_complete: bool
```

---

## MessageGraph (Deprecated)

You might see older code using `MessageGraph`:

```python
from langgraph.graph import MessageGraph  # DEPRECATED

graph = MessageGraph()
graph.add_node("agent", call_llm)
# ...
```

**Don't use this.** As of LangGraph 1.0, `MessageGraph` is deprecated. Use `StateGraph(MessagesState)` instead:

```python
from langgraph.graph import StateGraph, MessagesState

builder = StateGraph(MessagesState)  # Use this
```

---

## Quick Reference

### Import

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import (
    HumanMessage, 
    AIMessage, 
    ToolMessage, 
    SystemMessage,
    RemoveMessage
)
```

### Node Pattern

```python
def my_node(state: MessagesState) -> dict:
    # Read messages
    messages = state["messages"]
    
    # Process...
    
    # Return update (add_messages will append)
    return {"messages": [new_message]}
```

### Extend for Custom Fields

```python
class MyState(MessagesState):
    my_field: str
    my_list: Annotated[list[str], operator.add]
```

---

## Key Takeaways

1. **MessagesState is a TypedDict** with `messages: Annotated[list[AnyMessage], add_messages]`
    
2. **add_messages is the reducer** that controls how message updates are merged (append, update by ID, or remove)
    
3. **Reducers prevent data loss** — without them, node returns would overwrite each other
    
4. **Extend MessagesState** when you need additional fields beyond messages
    
5. **Message IDs matter** — they enable updating/removing specific messages
    
6. **MessageGraph is deprecated** — use `StateGraph(MessagesState)` instead
    

---

## References

- [LangGraph Graph API Overview](https://docs.langchain.com/oss/python/langgraph/graph-api) — State schemas and reducers
- [LangGraph Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart) — MessagesState usage
- [LangGraph message.py source](https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/graph/message.py) — add_messages implementation
- [How to delete messages](https://langchain-ai.github.io/langgraphjs/how-tos/delete-messages/) — RemoveMessage patterns