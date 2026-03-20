# LangMem — The Memory Toolkit

## What LangMem Is

LangMem is a specialized library from LangChain that provides **batteries-included memory management** for AI agents. It handles three core concerns:

1. **Extraction:** Pull important information from conversations
2. **Optimization:** Improve agent prompts based on feedback
3. **Storage Integration:** Persist memories to LangGraph's Store

In previous notes, we built memory systems manually—windowing, summarization, entity extraction, semantic search. LangMem wraps these patterns into reusable primitives with sensible defaults.

**When to use LangMem vs roll your own:**

- Use LangMem when you want proven patterns without reinventing
- Roll your own when you need custom extraction logic, non-LangGraph storage, or fine-grained control

---

## Architecture: Two Layers

LangMem operates at two levels:

### Layer 1: Core API (Stateless)

Functions that transform memory without side effects. Works with **any** storage system.

|Function|Purpose|
|---|---|
|`create_memory_manager`|Extract memories from conversations (you handle storage)|
|`create_prompt_optimizer`|Improve prompts based on feedback|

### Layer 2: LangGraph Integration (Stateful)

Components that integrate with LangGraph's `BaseStore` for automatic persistence.

|Function|Purpose|
|---|---|
|`create_memory_store_manager`|Extract + auto-persist to LangGraph Store|
|`create_manage_memory_tool`|Agent-callable tool to store memories|
|`create_search_memory_tool`|Agent-callable tool to search memories|

---

## Core Primitive: `create_memory_manager`

Extracts memories from conversations. **You control storage.**

```python
from langmem import create_memory_manager

manager = create_memory_manager(
    "anthropic:claude-sonnet-4-6",
    instructions="Extract user preferences and facts",
    enable_inserts=True,    # Allow creating new memories
    enable_deletes=True,    # Allow removing outdated memories
)

# Process a conversation
conversation = [
    {"role": "user", "content": "Alice manages the ML team and mentors Bob."}
]

memories = manager.invoke({"messages": conversation})
# Returns: list of ExtractedMemory objects

# Process follow-up with existing memories for reconciliation
conversation2 = [
    {"role": "user", "content": "Bob now leads the ML team."}
]

updated = manager.invoke({
    "messages": conversation2,
    "existing": memories  # Pass existing for UPDATE/DELETE decisions
})
```

**Key features:**

- **Memory enrichment:** Pass `existing` memories so the LLM can reconcile (update outdated, delete conflicting)
- **Schema customization:** Use Pydantic models for structured extraction
- **Storage-agnostic:** Returns extracted memories; you `put()` them wherever you want

### Custom Schemas

```python
from pydantic import BaseModel

class UserPreference(BaseModel):
    category: str
    preference: str
    confidence: float

manager = create_memory_manager(
    "anthropic:claude-sonnet-4-6",
    schemas=[UserPreference],  # Extract this structure
    instructions="Extract user preferences with confidence scores"
)
```

---

## Store Integration: `create_memory_store_manager`

Same as `create_memory_manager`, but **auto-persists to LangGraph Store**.

```python
from langmem import create_memory_store_manager
from langgraph.store.memory import InMemoryStore
from langgraph.func import entrypoint

store = InMemoryStore(
    index={"dims": 1536, "embed": "openai:text-embedding-3-small"}
)

manager = create_memory_store_manager(
    "anthropic:claude-sonnet-4-6",
    namespace=("memories", "{user_id}"),  # Dynamic namespace
)

@entrypoint(store=store)
async def chat(message: str):
    response = llm.invoke(message)
    
    # Extract and persist automatically
    await manager.ainvoke({
        "messages": [{"role": "user", "content": message}, response]
    })
    
    return response

# Invoke with user context
config = {"configurable": {"user_id": "user_123"}}
await chat.ainvoke("I prefer dark mode in all apps", config=config)

# Memories are now in store at ("memories", "user_123")
```

**Key difference from `create_memory_manager`:**

- Automatically calls `store.put()` and `store.delete()`
- Handles namespace resolution
- Integrates with LangGraph's runtime

---

## Agent Tools: Hot Path Memory

The **hot path** means the agent decides what to remember during the conversation. LangMem provides two tools:

### `create_manage_memory_tool`

Lets the agent store, update, or delete memories:

```python
from langmem import create_manage_memory_tool
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore

store = InMemoryStore(
    index={"dims": 1536, "embed": "openai:text-embedding-3-small"}
)

manage_tool = create_manage_memory_tool(
    namespace=("memories", "{langgraph_user_id}"),
    instructions="Store user preferences and important facts.",
    actions_permitted=["create", "update", "delete"],
)

agent = create_react_agent(
    "anthropic:claude-sonnet-4-6",
    tools=[manage_tool],
    store=store,
)

# User says something memorable
agent.invoke(
    {"messages": [{"role": "user", "content": "Remember I prefer dark mode."}]},
    config={"configurable": {"langgraph_user_id": "user_123"}}
)
# Agent decides to call manage_tool → stores the preference
```

**Tool signature exposed to the agent:**

```python
def manage_memory(
    content: str | None = None,      # Content for new/updated memory
    id: str | None = None,           # ID of existing memory to update/delete
    action: Literal["create", "update", "delete"] = "create",
) -> str: ...
```

### `create_search_memory_tool`

Lets the agent retrieve memories:

```python
from langmem import create_search_memory_tool

search_tool = create_search_memory_tool(
    namespace=("memories", "{langgraph_user_id}"),
)

agent = create_react_agent(
    "anthropic:claude-sonnet-4-6",
    tools=[manage_tool, search_tool],
    store=store,
)

# User asks a question
agent.invoke(
    {"messages": [{"role": "user", "content": "What are my display preferences?"}]},
    config={"configurable": {"langgraph_user_id": "user_123"}}
)
# Agent calls search_tool("display preferences") → retrieves "prefers dark mode"
```

### Hot Path Trade-offs

|Advantage|Disadvantage|
|---|---|
|Immediate memory updates|Adds latency to every turn|
|Agent controls what's stored|Consumes tool calls (context space)|
|Transparent to the user|Agent might over/under-extract|

---

## Background Memory: Deferred Processing

The **background path** extracts memories after the conversation, without blocking the user.

### `ReflectionExecutor`

Wraps a memory manager for deferred, debounced execution:

```python
from langmem import create_memory_store_manager, ReflectionExecutor
from langgraph.store.memory import InMemoryStore
from langgraph.func import entrypoint
from langchain.chat_models import init_chat_model

store = InMemoryStore(
    index={"dims": 1536, "embed": "openai:text-embedding-3-small"}
)

llm = init_chat_model("anthropic:claude-sonnet-4-6")

# Create the memory manager
memory_manager = create_memory_store_manager(
    "anthropic:claude-sonnet-4-6",
    namespace=("memories", "{user_id}"),
)

# Wrap in ReflectionExecutor for background processing
executor = ReflectionExecutor(memory_manager, store=store)

@entrypoint(store=store)
async def chat(message: str):
    response = await llm.ainvoke(message)
    
    to_process = {
        "messages": [{"role": "user", "content": message}, response]
    }
    
    # Schedule for background processing
    # Wait 30 seconds before processing
    # If more messages arrive, cancel previous and reschedule
    executor.submit(to_process, after_seconds=30)
    
    return response  # Return immediately, no latency hit
```

### How `ReflectionExecutor` Works

```
User sends message 1 → Response sent immediately
                       Schedule extraction in 30 seconds
                       
User sends message 2 → Response sent immediately
(within 30 seconds)    Cancel previous schedule
                       Schedule extraction in 30 seconds (with all messages)
                       
30 seconds of silence → Execute extraction on full conversation
                       Store memories to Store
```

**Benefits:**

- No latency impact on user responses
- Processes complete conversation context (not fragments)
- Debounces redundant work during active conversations
- Handles consolidation better (sees full picture)

### Background vs Hot Path Decision Matrix

|Factor|Hot Path|Background|
|---|---|---|
|Latency|Higher (extraction per turn)|None (async)|
|Context quality|Partial (mid-conversation)|Full (after conversation)|
|User control|Explicit ("remember this")|Implicit (automatic)|
|Token cost|Per turn|Per conversation|
|Complexity|Lower|Requires async infrastructure|

**Recommendation:** Use background for most semantic/episodic memory. Use hot path when the user explicitly wants to store something ("Remember that...").

---

## Prompt Optimization

LangMem can improve agent prompts based on conversation feedback. This is **procedural memory**—the agent learns _how_ to behave.

### `create_prompt_optimizer`

```python
from langmem import create_prompt_optimizer

optimizer = create_prompt_optimizer(
    "anthropic:claude-sonnet-4-6",
    kind="gradient",  # or "metaprompt" or "prompt_memory"
    config={
        "max_reflection_steps": 3,
        "min_reflection_steps": 1,
    }
)

# Conversations with feedback (trajectory + annotation)
trajectories = [
    (
        # Conversation
        [
            {"role": "user", "content": "Explain quantum computing"},
            {"role": "assistant", "content": "Quantum computing uses..."},
        ],
        # Feedback (optional)
        {"score": 0.6, "comment": "Too brief, needs examples"},
    ),
    (
        [
            {"role": "user", "content": "What's machine learning?"},
            {"role": "assistant", "content": "ML is a field of AI that..."},
        ],
        {"revised": "ML is a field of AI that enables computers to learn..."}
    ),
]

# Optimize the prompt
original_prompt = "You are a helpful AI assistant."
improved_prompt = optimizer.invoke({
    "trajectories": trajectories,
    "prompt": original_prompt,
})

print(improved_prompt)
# "You are a helpful AI assistant. When explaining technical concepts:
#  1. Provide detailed explanations with concrete examples
#  2. Structure your response with clear sections
#  ..."
```

### Optimization Algorithms

|Algorithm|How It Works|LLM Calls|Best For|
|---|---|---|---|
|`prompt_memory`|Single LLM call with simple metaprompt|1|Quick iteration|
|`gradient`|Separate calls for critique → proposal|2-10|Balanced quality/cost|
|`metaprompt`|Reflection + "thinking time" before proposal|Variable|Highest quality|

### Multi-Prompt Optimization

For multi-agent systems with multiple prompts:

```python
from langmem import create_multi_prompt_optimizer

optimizer = create_multi_prompt_optimizer(
    "anthropic:claude-sonnet-4-6",
    kind="gradient",
)

prompts = [
    {"name": "researcher", "prompt": "You research topics thoroughly."},
    {"name": "writer", "prompt": "You write clear reports."},
]

improved = optimizer.invoke({
    "trajectories": trajectories,
    "prompts": prompts,
})
# Returns list of improved prompts
```

---

## Complete Example: Agent with Full Memory Stack

```python
from langmem import (
    create_manage_memory_tool,
    create_search_memory_tool,
    create_memory_store_manager,
    ReflectionExecutor,
)
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore
from langgraph.func import entrypoint

# Store with semantic search
store = InMemoryStore(
    index={"dims": 1536, "embed": "openai:text-embedding-3-small"}
)

# Hot path tools (agent-controlled)
manage_tool = create_manage_memory_tool(
    namespace=("memories", "{langgraph_user_id}"),
    instructions="Store preferences the user explicitly asks you to remember.",
)

search_tool = create_search_memory_tool(
    namespace=("memories", "{langgraph_user_id}"),
)

# Background extraction (automatic)
memory_manager = create_memory_store_manager(
    "anthropic:claude-sonnet-4-6",
    namespace=("memories", "{langgraph_user_id}"),
)
executor = ReflectionExecutor(memory_manager, store=store)

# Create agent
agent = create_react_agent(
    "anthropic:claude-sonnet-4-6",
    tools=[manage_tool, search_tool],
    store=store,
)

# Wrapper that adds background extraction
@entrypoint(store=store)
async def chat_with_memory(messages: list):
    response = await agent.ainvoke({"messages": messages})
    
    # Schedule background extraction (debounced)
    executor.submit(
        {"messages": response["messages"]},
        after_seconds=60,  # Wait 1 minute of inactivity
    )
    
    return response

# Usage
config = {"configurable": {"langgraph_user_id": "user_123"}}

# Explicit memory request → hot path
await chat_with_memory.ainvoke(
    {"messages": [{"role": "user", "content": "Remember I'm allergic to peanuts"}]},
    config=config,
)
# Agent uses manage_tool → immediate storage

# Normal conversation → background extraction
await chat_with_memory.ainvoke(
    {"messages": [{"role": "user", "content": "I just got promoted at work!"}]},
    config=config,
)
# No immediate storage, but ReflectionExecutor will extract later
```

---

## When to Use LangMem vs Roll Your Own

### Use LangMem When:

|Scenario|Why|
|---|---|
|Standard memory needs|Proven patterns, less code|
|LangGraph integration|Native Store support|
|Quick prototyping|Get memory working fast|
|Multi-memory-type systems|Handles semantic/episodic/procedural|
|Prompt optimization needed|`create_prompt_optimizer` is powerful|

### Roll Your Own When:

|Scenario|Why|
|---|---|
|Non-LangGraph storage|LangMem's stateful layer assumes BaseStore|
|Custom extraction logic|Your domain needs specialized parsing|
|Performance-critical paths|Direct Store calls may be faster|
|Non-LLM extraction|You want rule-based or NER-only extraction|
|Learning/understanding|Building it yourself teaches more|

### Hybrid Approach

Use LangMem tools but customize specific parts:

```python
# Use LangMem tools for agent interface
from langmem import create_manage_memory_tool

# But customize the extraction with your own schema
class MyCustomMemory(BaseModel):
    category: Literal["fact", "preference", "event"]
    content: str
    confidence: float
    source_turn: int

tool = create_manage_memory_tool(
    namespace=("memories", "{user_id}"),
    schema=MyCustomMemory,
    instructions="Your custom extraction instructions here.",
)
```

---

## Key Takeaways

1. **LangMem = extraction + optimization + storage integration.** It wraps patterns we built manually in earlier notes.
    
2. **Two layers:** Core API (stateless, any storage) and LangGraph integration (stateful, auto-persist).
    
3. **Four main primitives:**
    
    - `create_memory_manager`: Extract (you store)
    - `create_memory_store_manager`: Extract + auto-persist
    - `create_manage_memory_tool` / `create_search_memory_tool`: Agent-callable
4. **Hot path vs background:** Use hot path for explicit user requests. Use background (`ReflectionExecutor`) for automatic extraction without latency.
    
5. **Prompt optimization:** `create_prompt_optimizer` with `gradient`, `metaprompt`, or `prompt_memory` algorithms for procedural memory.
    
6. **When to use it:** Standard needs + LangGraph + quick prototyping. Roll your own for custom storage, non-LLM extraction, or learning.
    

---

## References

- LangMem Documentation: https://langchain-ai.github.io/langmem/
- LangMem GitHub: https://github.com/langchain-ai/langmem
- LangMem SDK Launch Blog: https://blog.langchain.com/langmem-sdk-launch/
- Memory Tools API Reference: https://langchain-ai.github.io/langmem/reference/tools/
- Memory API Reference: https://langchain-ai.github.io/langmem/reference/memory/
- Prompt Optimization Reference: https://langchain-ai.github.io/langmem/reference/prompt_optimization/
- Delayed Processing Guide: https://langchain-ai.github.io/langmem/guides/delayed_processing/
- Background Quickstart: https://langchain-ai.github.io/langmem/background_quickstart/
- Hot Path Quickstart: https://langchain-ai.github.io/langmem/hot_path_quickstart/