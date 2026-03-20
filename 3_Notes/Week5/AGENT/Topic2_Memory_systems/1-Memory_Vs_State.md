# Memory vs State: Short-Term and Long-Term

## The Core Distinction

When building agents, two related but distinct concepts emerge: **state** and **memory**. Conflating them leads to architectural confusion.

**State** answers: "What are we doing right now?"

- Current conversation messages
- Intermediate values during graph execution
- Tool results from the current session
- Scope: **within a single thread/session**

**Memory** answers: "What do we remember from before?"

- User preferences learned over time
- Facts extracted from past conversations
- Patterns from previous interactions
- Scope: **across threads/sessions**

Think of it this way: state is your working memory during a phone call; memory is what you recall about this person from previous calls.

---

## LangGraph's Two Primitives

LangGraph cleanly separates these concerns with two distinct interfaces:

### Checkpointer → State (Short-Term)

The checkpointer saves **graph state** at every super-step. This enables:

- Resume after interruption (human-in-the-loop)
- Time travel debugging
- Fault tolerance

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph

# Checkpointer handles state persistence
checkpointer = InMemorySaver()

graph = workflow.compile(checkpointer=checkpointer)

# State is scoped to a thread_id
config = {"configurable": {"thread_id": "user_123_session_456"}}
result = graph.invoke({"messages": [...]}, config)
```

Key point: **checkpointers are thread-scoped**. Thread A's state is completely isolated from Thread B's state. When the thread ends, the state is still there (you can resume), but it doesn't "leak" to other threads.

Production checkpointers:

- `InMemorySaver` — development only, lost on restart
- `SqliteSaver` — local persistence
- `PostgresSaver` — production-grade
- `RedisSaver` — high-performance

### Store → Memory (Long-Term)

The store saves **cross-thread information**. This enables:

- User preferences across sessions
- Learned facts about entities
- Semantic search over past interactions

```python
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import InMemorySaver

# Store handles long-term memory
store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": "openai:text-embedding-3-small",
    }
)

# Checkpointer handles state
checkpointer = InMemorySaver()

# Compile with both
graph = workflow.compile(checkpointer=checkpointer, store=store)
```

Store operations use **namespaces** (like folders) to organize memories:

```python
# Store a memory (namespace = user_id + memory_type)
store.put(
    namespace=("user_123", "preferences"),
    key="theme",
    value={"preference": "dark_mode"}
)

# Retrieve across any thread
store.get(namespace=("user_123", "preferences"), key="theme")

# Search semantically (if index configured)
store.search(
    namespace=("user_123", "facts"),
    query="What programming languages does the user know?"
)
```

**Critical insight:** With checkpointers alone, you cannot share information across threads. That's why Store exists.

---

## OpenAI's Approach: Responses API

OpenAI's Responses API (March 2025) replaced Chat Completions as the recommended API. It offers two modes for conversation management:

### Stateless Mode: Manual History Management

You manage the conversation history yourself:

```python
from openai import OpenAI
client = OpenAI()

history = [{"role": "user", "content": "tell me a joke"}]

response = client.responses.create(
    model="gpt-4.1",
    input=history,
    store=True,
)

# You append to history manually
history.append({"role": "assistant", "content": response.output_text})
history.append({"role": "user", "content": "explain why it's funny"})

response2 = client.responses.create(
    model="gpt-4.1",
    input=history,
)
```

This is equivalent to what you did with Chat Completions: you own the message array.

### Stateful Mode: previous_response_id

OpenAI maintains the conversation state server-side:

```python
response = client.responses.create(
    model="gpt-4.1",
    input="tell me a joke",
)

# Chain responses without managing history
response2 = client.responses.create(
    model="gpt-4.1",
    input=[{"role": "user", "content": "explain why it's funny"}],
    previous_response_id=response.id,  # OpenAI handles the context
)
```

Benefits:

- OpenAI preserves reasoning tokens across turns (critical for o3/o4-mini)
- No need to manage message arrays
- Can retrieve full history via `client.responses.retrieve(response_id)`

### Conversations API (Thread-Like)

For longer-running conversations:

```python
# Create a durable conversation object
conversation = client.conversations.create()

# Use it across multiple responses
response = client.responses.create(
    model="gpt-4.1",
    input=[{"role": "user", "content": "What are the 5 Ds of dodgeball?"}],
    conversation=conversation.id,  # Thread-like persistence
)
```

**Important:** `previous_response_id` and `conversation` are mutually exclusive. You use one or the other.

**Long-term memory?** OpenAI doesn't provide a built-in Store equivalent. For cross-conversation memory, you need external storage (vector DB, custom solution, or frameworks like LangGraph).

---

## Anthropic's Approach: Stateless + Memory Tool

The Claude API (Messages endpoint) is fundamentally **stateless**. Every request must include the full conversation:

```python
from anthropic import Anthropic
client = Anthropic()

# You manage the message history
messages = [
    {"role": "user", "content": "My name is Harsh"},
    {"role": "assistant", "content": "Nice to meet you, Harsh!"},
    {"role": "user", "content": "What's my name?"},
]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=messages,
)
```

### Memory Tool (Beta, September 2025)

Anthropic introduced a **client-side memory tool** that Claude can use to read/write files:

```python
response = client.beta.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=8096,
    tools=[{"type": "memory_20250818", "name": "memory"}],
    betas=["context-management-2025-06-27"],
    messages=messages,
)

# Claude makes tool calls like:
# - memory.write("/memories/user_preferences.json", {...})
# - memory.read("/memories/user_preferences.json")
```

**Key difference from OpenAI:** The memory tool is client-side. You implement the file system handlers. This gives you full control over storage location and format.

### Context Compaction (Beta)

For long conversations approaching context limits, Anthropic offers server-side summarization:

```python
# When context grows large, older turns get compacted
# This happens automatically with the context-management beta
```

Compaction summarizes older content while preserving recent context. The memory tool can save important information before compaction clears it.

---

## The Mental Model

|Concept|LangGraph|OpenAI|Anthropic|
|---|---|---|---|
|**State (within session)**|Checkpointer|`previous_response_id` or `conversation`|Manual message array|
|**Memory (across sessions)**|Store|External (you build it)|Memory Tool (client-side)|
|**Scoping**|`thread_id` + namespaces|Response ID chain|Namespaces in memory files|
|**Server-side storage**|Yes (configurable backend)|Yes (30-day retention)|No (client controls storage)|

---

## When State Is Enough vs When You Need Memory

**Checkpointer/State is sufficient when:**

- Single conversation that may span multiple invocations
- Human-in-the-loop requiring pause/resume
- Error recovery within a session
- Time-travel debugging

**Store/Memory is required when:**

- User returns days later and expects agent to remember them
- Preferences should persist across conversations
- Agent learns facts that apply beyond current session
- Multi-agent systems need shared knowledge

---

## Production Patterns

### Pattern 1: State Only (Simple Chatbot)

```python
# Sufficient for: Support bot where each ticket is independent
checkpointer = PostgresSaver(conn_string)
graph = workflow.compile(checkpointer=checkpointer)

# Each ticket gets a thread_id, state persists within ticket
config = {"configurable": {"thread_id": f"ticket_{ticket_id}"}}
```

### Pattern 2: State + Memory (Personalized Assistant)

```python
# Required for: Assistant that remembers user preferences
checkpointer = PostgresSaver(conn_string)
store = PostgresStore(conn_string, index={...})

graph = workflow.compile(checkpointer=checkpointer, store=store)

# State scoped to session, memory scoped to user
config = {"configurable": {
    "thread_id": f"user_{user_id}_session_{session_id}",
    "user_id": user_id,  # For memory namespace
}}
```

### Pattern 3: Memory Without State (Stateless with Context)

```python
# For: High-volume, low-latency scenarios where you don't need pause/resume
# Just use Store to inject relevant context at start of each request

memories = store.search(("user_123", "facts"), query=user_message)
context = format_memories_as_context(memories)

# Inject into system prompt
messages = [
    {"role": "system", "content": f"User context:\n{context}"},
    {"role": "user", "content": user_message},
]
```

---

## Key Takeaways

1. **State ≠ Memory.** State is session-scoped; memory is cross-session.
    
2. **LangGraph separates them cleanly.** Checkpointer for state, Store for memory. Use both when needed.
    
3. **OpenAI's Responses API handles state server-side** via `previous_response_id` or Conversations API. Memory is your responsibility.
    
4. **Anthropic is stateless by design.** The Memory Tool provides a standardized interface for client-controlled persistence.
    
5. **The right choice depends on your use case.** Simple chatbot? State only. Personal assistant? Both. High-throughput stateless? Memory injection at request time.
    

---

## References

- LangGraph Persistence Docs: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph Memory Docs: https://docs.langchain.com/oss/python/langgraph/memory
- OpenAI Conversation State: https://developers.openai.com/api/docs/guides/conversation-state/
- OpenAI Responses API Migration: https://developers.openai.com/api/docs/guides/migrate-to-responses
- Anthropic Memory Tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool